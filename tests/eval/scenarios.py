"""
Passe Claude Usability Test Scenarios.

Each scenario tests whether a Claude with Passe context generates
correct tool-use patterns. Scored against expected patterns.

Categories:
- tool_choice: Does Claude pick passe vs mise vs curl?
- dsl_hygiene: Does Claude use heredoc, avoid anti-patterns?
- tab_lifecycle: Does Claude understand tab creation/destruction?
- connection_error: Does Claude diagnose vs give up?
- scout_pattern: Does Claude scout before acting on unknown pages?
- extraction: Does Claude use fetch/extract correctly?
- network: Does Claude use capture/log correctly?
"""

from dataclasses import dataclass, field


@dataclass
class Scenario:
    id: str
    category: str
    prompt: str
    # Patterns that MUST appear in the response (any one = pass)
    expect_any: list[str] = field(default_factory=list)
    # Patterns that MUST NOT appear (any one = fail)
    reject_any: list[str] = field(default_factory=list)
    # Human-readable description of what we're testing
    rationale: str = ""


SCENARIOS: list[Scenario] = [
    # ── tool_choice ──────────────────────────────────────────────
    Scenario(
        id="tc-01",
        category="tool_choice",
        prompt="Get me the content of this article: https://paulgraham.com/superlinear.html",
        expect_any=["passe fetch", "passe run"],
        reject_any=["curl ", "wget ", "WebFetch"],
        rationale="Basic content extraction should use passe, not curl/wget",
    ),
    Scenario(
        id="tc-02",
        category="tool_choice",
        prompt="Can you get the content of this Google Doc? https://docs.google.com/document/d/1abc123/edit",
        expect_any=["mise fetch", "mise"],
        reject_any=["passe fetch", "passe run"],
        rationale="Google Workspace content should use mise, not passe",
    ),
    Scenario(
        id="tc-03",
        category="tool_choice",
        prompt="Screenshot the homepage of https://news.ycombinator.com",
        expect_any=["passe look", "passe run", "screenshot"],
        reject_any=["curl ", "wget "],
        rationale="Screenshots should use passe",
    ),
    Scenario(
        id="tc-04",
        category="tool_choice",
        prompt="What API calls does https://app.example.com make when it loads?",
        expect_any=["passe capture", "passe log"],
        reject_any=["curl ", "network tab"],
        rationale="API discovery should use passe capture or log",
    ),
    Scenario(
        id="tc-05",
        category="tool_choice",
        prompt="Fetch this Gmail thread: https://mail.google.com/mail/u/0/#inbox/abc123",
        expect_any=["mise"],
        reject_any=["passe fetch", "passe run"],
        rationale="Gmail content should use mise, not passe",
    ),

    # ── dsl_hygiene ──────────────────────────────────────────────
    Scenario(
        id="dh-01",
        category="dsl_hygiene",
        prompt=(
            "Go to https://example.com, click the login button, "
            "type 'admin' in the username field, type 'password' in the password field, "
            "press Enter, wait for the dashboard to load, "
            "then screenshot the result."
        ),
        expect_any=["<<'EOF'", "<<EOF", "heredoc", "<<'PASSE'"],
        reject_any=[],
        rationale="7 verbs should use heredoc, not inline -c. "
                  "Expect pattern checks for heredoc presence.",
    ),
    Scenario(
        id="dh-02",
        category="dsl_hygiene",
        prompt="Go to https://example.com and extract the page content",
        expect_any=["passe fetch", "fetch https://example.com"],
        reject_any=["goto.*wait.*extract", "goto.*wait 1.*read", "goto.*wait 0.5.*extract"],
        rationale="goto+extract should be simplified to fetch. No unnecessary wait.",
    ),
    Scenario(
        id="dh-03",
        category="dsl_hygiene",
        prompt="Extract the content from https://example.com and save it to /tmp/content.md",
        expect_any=["passe fetch https://example.com /tmp/content.md",
                     "fetch https://example.com /tmp/content.md"],
        reject_any=["goto.*wait.*extract"],
        rationale="fetch with path argument is the ergonomic form",
    ),

    # ── tab_lifecycle ────────────────────────────────────────────
    Scenario(
        id="tl-01",
        category="tab_lifecycle",
        prompt=(
            "First, screenshot https://example.com. "
            "Then, extract the content of https://other.com."
        ),
        expect_any=["passe run", "passe look.*passe fetch",
                     "passe look.*passe run"],
        reject_any=[],
        rationale="Two separate pages = two separate passe invocations or one script with both. "
                  "Either approach is valid.",
    ),
    Scenario(
        id="tl-02",
        category="tab_lifecycle",
        prompt=(
            "Navigate to https://example.com, take a screenshot, "
            "then tell me the page title."
        ),
        expect_any=["passe run"],
        reject_any=[],
        rationale="All operations on one page should be one passe run, not separate commands",
    ),

    # ── connection_error ─────────────────────────────────────────
    Scenario(
        id="ce-01",
        category="connection_error",
        prompt=(
            "I tried to use passe but got 'Connection refused' on port 9222. "
            "What should I do?"
        ),
        expect_any=["Chrome", "running", "lsof", "9222", "stale",
                     "closed", "sleeping", "--cdp"],
        reject_any=["passe is broken", "passe doesn't work",
                     "try a different tool", "use curl instead"],
        rationale="Connection refused = Chrome issue, not passe issue. Diagnose, don't give up.",
    ),
    Scenario(
        id="ce-02",
        category="connection_error",
        prompt=(
            "I'm on hezza (Linux server). My Mac is closed. "
            "I ran `passe look https://example.com` and got this:\n\n"
            "[passe:connection] endpoint=http://100.66.153.39:9222 reachable=no\n"
            "[passe:connection] reason=Chrome is not reachable at this endpoint\n"
            "[passe:connection] alternatives=Use --cdp localhost:9222 for local headless Chrome; "
            "Check that the remote machine is awake; "
            "Start Chrome with --remote-debugging-port on the remote machine\n\n"
            "Can you still screenshot the page?"
        ),
        expect_any=["--cdp localhost", "headless", "localhost:9222"],
        reject_any=["can't", "unable", "not possible", "won't work",
                     "passe is broken", "try curl"],
        rationale="Given structured diagnostics with alternatives, Claude should "
                  "follow the suggestion and use local headless Chrome",
    ),

    Scenario(
        id="ce-03",
        category="connection_error",
        prompt=(
            "I ran `passe status` and got:\n\n"
            "[passe:status] cdp_endpoint=http://100.66.153.39:9222\n"
            "[passe:status] remote=True\n"
            "[passe:status] reachable=False\n"
            "[passe:status] reason=Cannot connect to Chrome: <urlopen error timed out>\n"
            "[passe:status] alternatives=Check that Chrome is running; "
            "Use --cdp localhost:9222 for local headless Chrome\n\n"
            "I need to screenshot a page. What should I do?"
        ),
        expect_any=["--cdp localhost", "headless", "localhost:9222", "local"],
        reject_any=["passe is broken", "try curl", "use wget"],
        rationale="Given passe status output showing unreachable remote, "
                  "Claude should suggest local headless Chrome.",
    ),
    Scenario(
        id="ce-04",
        category="connection_error",
        prompt=(
            "passe fetch keeps failing with:\n\n"
            "[passe:connection] endpoint=http://100.66.153.39:9222 reachable=no\n"
            "[passe:connection] reason=Cannot connect to Chrome: <urlopen error timed out>\n"
            "[passe:connection] alternatives=Use --cdp localhost:9222 for local headless Chrome; "
            "Check that the remote machine is awake\n\n"
            "I'm on hezza. How do I get this working?"
        ),
        expect_any=["--cdp", "localhost", "local", "headless"],
        reject_any=["can't help", "unable to", "not possible"],
        rationale="Should follow the alternatives in the diagnostic output",
    ),

    # ── scout_pattern ────────────────────────────────────────────
    Scenario(
        id="sp-01",
        category="scout_pattern",
        prompt=(
            "Go to https://unknown-crm.example.com and click the 'New Contact' button"
        ),
        expect_any=["snapshot", "scout", "discover"],
        reject_any=[],
        rationale="Unknown page = scout first with snapshot, then act",
    ),
    Scenario(
        id="sp-02",
        category="scout_pattern",
        prompt="Dismiss the cookie banner on https://spiegel.de",
        expect_any=["snapshot", 'click "'],
        reject_any=[],
        rationale="Cookie banners vary — should scout or try text click, not guess CSS",
    ),

    # ── extraction ───────────────────────────────────────────────
    Scenario(
        id="ex-01",
        category="extraction",
        prompt="Get the content of https://react.dev/reference/react/useState",
        expect_any=["passe fetch"],
        reject_any=["curl"],
        rationale="SPA page — passe fetch handles __NEXT_DATA__ extraction",
    ),
    Scenario(
        id="ex-02",
        category="extraction",
        prompt=(
            "Extract the content from https://developer.apple.com/documentation/swift/array"
        ),
        expect_any=["passe fetch", "apple"],
        reject_any=["curl"],
        rationale="Apple docs auto-detected by passe for JSON endpoint extraction",
    ),

    # ── network ──────────────────────────────────────────────────
    Scenario(
        id="nw-01",
        category="network",
        prompt=(
            "I want to see what API endpoints https://app.example.com calls "
            "when I log in. Can you capture the network traffic?"
        ),
        expect_any=["capture", "--bodies", "jsonl"],
        reject_any=[],
        rationale="API reverse-engineering should use capture with --bodies",
    ),
    Scenario(
        id="nw-02",
        category="network",
        prompt="Monitor all Chrome network traffic for the next hour",
        expect_any=["passe log start", "log start", "daemon"],
        reject_any=[],
        rationale="Continuous monitoring = log daemon, not one-shot capture. "
                  "Mentioning capture in explanation is fine as long as log start is used.",
    ),
]
