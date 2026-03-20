# Absorbing skill-chrome-log into passe

Reference doc for the passe-fakuba outcome. Read this before starting any action.

## Source material

skill-chrome-log repo: `github.com/spm1001/skill-chrome-log` (clone it if you don't have it locally). Key files:

| File | Lines | What to read for |
|------|-------|-----------------|
| `scripts/daemon.py` | 604 | Multi-tab CDP capture, request assembly, filtering, body handling, rotation |
| `scripts/chrome_log.py` | 771 | CLI query tools (tail/list/show/clear), daemon management, color formatting |
| `scripts/server.py` | 262 | **Skip** — HTTP dashboard, not being ported |
| `assets/status.html` | 765 | **Skip** — dashboard UI, not being ported |

Passe source is at `src/passe/`. Read `understanding.md` in `.bon/` first for project context.

## JSONL schema (shared between daemon and one-shot capture)

Every line is a self-contained JSON object. All fields except `id`, `ts`, `method`, `url` are optional — query tools must handle absence gracefully.

```json
{
  "id": "F9A2B...",
  "ts": "2026-03-20T16:00:00.123Z",
  "method": "POST",
  "url": "https://api.example.com/v1/data",
  "status": 200,
  "mime": "application/json",
  "resource_type": "XHR",
  "size": 1234,
  "timing_ms": 342,
  "tab": {"id": "ABCD1234", "url": "https://app.example.com/dashboard"},
  "request_headers": {"Host": "api.example.com", "Cookie": "..."},
  "response_headers": {"Content-Type": "application/json", "Set-Cookie": "..."},
  "request_body": "{\"query\": \"...\"}",
  "response_body": "{\"results\": [...]}"
}
```

| Field | Source | Notes |
|-------|--------|-------|
| `id` | CDP `requestId` | Used for `passe log show` prefix matching |
| `ts` | Python `datetime.now(UTC).isoformat()` | ISO 8601 with timezone |
| `method` | `Network.requestWillBeSent` params.request.method | |
| `url` | `Network.requestWillBeSent` params.request.url | |
| `status` | `Network.responseReceived` params.response.status | Absent for failed/cancelled requests |
| `mime` | `Network.responseReceived` params.response.mimeType | |
| `resource_type` | `Network.requestWillBeSent` params.type | XHR, Fetch, Script, Stylesheet, Image, Document, etc. |
| `size` | `Network.loadingFinished` params.encodedDataLength | Bytes on wire |
| `timing_ms` | Computed from requestWillBeSent to loadingFinished | Wall clock, not CDP timing |
| `tab` | From session→target mapping | `id` is CDP targetId, `url` is the page URL at request time |
| `request_headers` | `requestWillBeSent` + `requestWillBeSentExtraInfo` | Merge both — ExtraInfo has Cookie header |
| `response_headers` | `responseReceived` + `responseReceivedExtraInfo` | Merge both — ExtraInfo has Set-Cookie |
| `request_body` | `requestWillBeSent` params.request.postData | POST/PUT/PATCH only, absent otherwise |
| `response_body` | `Network.getResponseBody` result.body | Opt-in (`--bodies`). Max 100KB, truncated with marker. Base64-decoded. Binary → `[binary content]` |

**Design decisions:**
- Snake_case throughout (chrome-log used camelCase for headers — inconsistent with Python conventions)
- No separate `cookies` field — cookies are in headers already. chrome-log extracted them but it's redundant
- `resource_type` added (from CDP, not in chrome-log) — essential for filtering "show me just XHR requests"
- `timing_ms` is wall-clock (chrome-log didn't track timing at all)
- `tab` is an object not a string — gives both the target ID and the page URL

## Where new code goes in the DAG

Passe's import dependency graph is a strict DAG. Circular imports break everything.

```
parser.py                 ← verb sets, parse_script, constants
client.py                 ← CDPClient, WebSocket routing
    ↓
connection.py             ← connect(), discover_chrome() [NEW], Chrome launch
verbs.py                  ← do_* action functions
log_daemon.py    [NEW]    ← own WebSocket handler, uses discover_chrome()
    ↓
runner.py                 ← run_script dispatch loop
log_query.py     [NEW]    ← JSONL reader, filter, format (NO passe imports needed)
    ↓
commands.py               ← cmd_run, cmd_fetch, cmd_look, cmd_capture, cmd_log_* [NEW]
    ↓
cli.py                    ← main(), dispatch, re-exports
```

**Key placement rules:**
- `log_query.py` has ZERO passe imports. It reads JSONL files and formats output. Sits parallel to `runner.py`.
- `log_daemon.py` imports `discover_chrome()` from `connection.py` and that's it. Sits parallel to `verbs.py`. Does NOT import from `client.py` — it has its own WebSocket handler.
- New `cmd_log_*` functions go in `commands.py` (or a new `log_commands.py` parallel to it if commands.py gets too large).
- `cli.py` dispatches `passe log <subcmd>` to the appropriate function.

## Critical: DO NOT extend CDPClient

CDPClient is built for single-tab request-response interaction:
- One `session_id` (the daemon needs N, one per tab)
- `event_waiters` keyed by method name — one waiter per method (the daemon gets the same event from multiple tabs)
- One-shot futures that consume events (the daemon needs continuous streaming)
- Tight coupling to `connect()` lifecycle (start/stop receiver with context manager)

The daemon needs a simpler continuous-stream handler:
- Receives all messages, routes by `sessionId` field
- Correlates network events by `requestId` across multiple CDP events
- No futures, no waiters, no queues — just a dict of in-flight requests that get assembled and flushed to disk

Port chrome-log's `handle_message` pattern (90 lines of event dispatch). It's the right shape.

## Extract `discover_chrome()` from `connect()`

Current `connect()` bundles Chrome discovery with CDPClient creation. The daemon needs discovery but not CDPClient.

**Refactor:** Extract the first half of `connect()` into a standalone function:

```python
async def discover_chrome(cdp_url: str | None = None) -> tuple[str, dict]:
    """Find Chrome and return (ws_url, browser_info).

    Checks override → PASSE_CDP env → localhost:9222.
    Rewrites ws://localhost WebSocket URLs for remote Chrome.
    Does NOT auto-launch Chrome (daemon should not start Chrome).
    """
    base = cdp_url or _cdp_override or os.environ.get("PASSE_CDP") or "http://localhost:9222"
    # ... HTTP call to /json/version ...
    # ... WebSocket URL rewriting for remote ...
    return ws_url, {"version": ..., "remote": ..., "base_url": base}
```

`connect()` then calls `discover_chrome()` internally — no behavior change for existing code. The daemon calls `discover_chrome()` directly, opens its own WebSocket.

**Important:** The daemon should NOT auto-launch Chrome. Unlike `connect()`, which helpfully starts a headless Chrome if none is running, the daemon should fail loudly. A daemon silently starting Chrome is surprising behavior.

## Network.enable buffer sizes

chrome-log passes large buffer params to `Network.enable`:

```python
await send("Network.enable", {
    "maxTotalBufferSize": 100 * 1024 * 1024,    # 100MB
    "maxResourceBufferSize": 50 * 1024 * 1024,   # 50MB
    "maxPostDataSize": 65536,                     # 64KB
})
```

Without these, `Network.getResponseBody` fails silently on large or streaming responses with "No resource with given identifier found" — Chrome evicts the response from its inspector cache before you fetch it.

Passe's existing `ensure_network()` in CDPClient passes no params. This is fine for status code capture (it doesn't fetch bodies) but the daemon and enriched `passe capture` need the large buffers.

## Flattened sessions and sessionId routing

chrome-log uses `Target.attachToTarget(flatten=True)`. This means:
- All events from all tabs arrive on the **single main WebSocket**
- Each event/response has a `sessionId` field identifying which tab it came from
- Commands sent to a specific tab must include `sessionId` in the message

The daemon's message handler must:
1. Check for `sessionId` in incoming messages
2. Route network events to the correct per-tab request store
3. Track session→tab mapping (updated via `Target.targetInfoChanged`)

Without this routing, requests from tab A get mixed with tab B's metadata.

## Daemon process model

**Use `subprocess.Popen`, not `os.fork()`.** Python's `os.fork()` with an active asyncio event loop is undefined behavior — pending futures, file descriptors, and thread state get cloned in broken states.

The daemon should be a separate entry point:

```python
# In log_daemon.py:
def main():
    """Entry point for daemon subprocess."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--cdp", help="CDP endpoint URL")
    parser.add_argument("--log-dir", default="~/.passe/logs")
    args = parser.parse_args()
    asyncio.run(run_daemon(args.cdp, args.log_dir))

if __name__ == "__main__":
    main()
```

```python
# In commands.py (cmd_log_start):
proc = subprocess.Popen(
    [sys.executable, "-m", "passe.log_daemon", "--cdp", cdp_url],
    start_new_session=True,  # detach from parent process group
    stdout=open(log_dir / "daemon.log", "a"),
    stderr=subprocess.STDOUT,
)
# Write state
state = {"pid": proc.pid, "cdp": cdp_url, "started": datetime.now().isoformat()}
(log_dir.parent / "state.json").write_text(json.dumps(state))
```

`start_new_session=True` detaches the daemon so it survives the parent (passe CLI) exiting.

## Reconnection state machine (new code, not a port)

chrome-log's daemon exits on disconnect. The passe daemon must survive tailscale blips.

```
     ┌──────────┐
     │CONNECTING │◄──────────────────────────────┐
     └─────┬─────┘                               │
           │ success                              │
     ┌─────▼─────┐                               │
     │ ATTACHING  │ setAutoAttach + enumerate     │
     │            │ existing tabs + Network.enable│
     └─────┬─────┘ (with large buffers per tab)  │
           │ all tabs attached                    │
     ┌─────▼─────┐                               │
     │ CAPTURING  │ process events, write JSONL   │
     └─────┬─────┘                               │
           │ WebSocket close/error                │
     ┌─────▼──────┐    wait backoff               │
     │DISCONNECTED │───────────────────────────────┘
     └─────┬──────┘    (1s, 2s, 4s, 8s... cap 60s)
           │ max retries exceeded OR SIGTERM
     ┌─────▼─────┐
     │   DEAD     │
     └───────────┘
```

**On reconnection:**
1. Abandon all in-flight (partial) requests — they'll never complete
2. Keep the completed request log (already on disk)
3. Re-discover Chrome via `discover_chrome()` (it may have restarted)
4. Open fresh WebSocket
5. Re-run `Target.setAutoAttach` + `Target.setDiscoverTargets`
6. Re-attach to all existing page targets
7. Re-enable `Network.enable` with large buffers on each session
8. Reset backoff delay to 1s on successful reconnect
9. Log reconnection event to daemon.log

**What triggers disconnection:**
- `websockets.ConnectionClosed` exception in the message loop
- Explicit `SIGTERM` → graceful shutdown (don't reconnect)
- Chrome process dies → reconnect will fail until Chrome restarts

**What to preserve across reconnects:**
- The log file handle (rotate if needed, but keep writing to the same log)
- The CDP endpoint URL (from startup config)
- The backoff state (reset on success)

**What to discard:**
- All per-session state (session IDs, tab mappings)
- In-flight request store (partial requests are garbage after disconnect)
- WebSocket connection object

## Filtering skip-lists (port from chrome-log)

```python
# URL patterns to skip (regex)
SKIP_URL_PATTERNS = [
    r"google-analytics\.com", r"doubleclick\.net",
    r"play\.google\.com/log", r"fonts\.googleapis\.com",
    r"facebook\.com/tr", r"facebook\.net",
    r"sentry\.io", r"hotjar\.com", r"clarity\.ms",
    r"/analytics", r"/tracking", r"/telemetry",
    r"/beacon", r"/pixel", r"/metrics",
]

# File extensions to skip
SKIP_EXTENSIONS = {".css", ".woff", ".woff2", ".svg", ".ico"}

# MIME types to skip
SKIP_MIME_PREFIXES = ("image/", "font/", "audio/", "video/")
SKIP_MIME_EXACT = {"application/octet-stream", "application/pdf", "application/zip"}
```

These should live in `log_daemon.py` (the daemon module) and also be importable by `commands.py` for enriched `passe capture --filter`.

## File layout

```
~/.passe/
├── logs/
│   ├── requests.jsonl       # active log (daemon appends here)
│   ├── requests.jsonl.1     # rotated (100MB trigger)
│   ├── requests.jsonl.2
│   ├── requests.jsonl.3     # oldest, deleted when 4th rotation happens
│   ├── .paused              # presence = daemon suppresses writes
│   └── daemon.log           # daemon stdout/stderr
└── state.json               # {"pid": 1234, "cdp": "http://...", "started": "..."}
```

## Testing strategy

- **log_query.py**: Pure JSONL reading — unit test with fixture files. No mocks needed.
- **log_daemon.py**: Mock the WebSocket. Send canned CDP event sequences (requestWillBeSent → responseReceived → loadingFinished) and verify JSONL output. Use the `FakeWS` pattern from existing passe tests.
- **Reconnection**: Test the state machine by simulating disconnect (close the mock WebSocket) and verifying re-attach sequence.
- **Integration**: Real Chrome on localhost:9222 (headless Chromium on kube). Start daemon, navigate a tab, verify JSONL contains the request.
- **cmd_log_***: Test CLI dispatch and state management. Mock the daemon subprocess.
