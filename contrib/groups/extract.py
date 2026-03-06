#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = [
#     "websockets",
#     "mise-en-space @ file:///Users/modha/Repos/mise-en-space",
# ]
# ///
"""
Google Groups → clean markdown extraction via SSR + batchexecute RPC.

No browser needed after initial cookie grab from Chrome Passe.
Extracts thread listings via pagination RPC, fetches each thread page
via curl, parses AF_initDataCallback SSR data, and cleans with mise.

Usage:
    uv run --script contrib/groups/extract.py <group_url> <output_dir> [--limit N] [--resume]

Examples:
    # Extract all threads
    uv run --script contrib/groups/extract.py \\
        https://groups.google.com/a/itv.com/g/mit-group /tmp/mit-group

    # Extract first 50 threads (for testing)
    uv run --script contrib/groups/extract.py \\
        https://groups.google.com/a/itv.com/g/mit-group /tmp/mit-group --limit 50

    # Resume interrupted extraction
    uv run --script contrib/groups/extract.py \\
        https://groups.google.com/a/itv.com/g/mit-group /tmp/mit-group --resume

Environment:
    PASSE_CDP  CDP endpoint for cookie grab (default http://localhost:9222)
"""

import asyncio
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

# ── Cookie grabber ──────────────────────────────────────

CDP_BASE = os.environ.get('PASSE_CDP', 'http://localhost:9222')


async def grab_cookies(group_url: str) -> str:
    """Grab auth cookies from Chrome Passe via CDP Network.getCookies.

    Navigates to the group URL first to ensure cookies are fresh,
    then extracts all cookies (including HttpOnly) via CDP.
    Returns a cookie header string.
    """
    import websockets

    # Get browser WS URL
    with urllib.request.urlopen(f'{CDP_BASE}/json/version', timeout=5) as resp:
        version = json.loads(resp.read())
    browser_ws = version['webSocketDebuggerUrl']

    # Rewrite localhost if remote CDP
    if not CDP_BASE.startswith('http://localhost'):
        parsed = urllib.parse.urlparse(CDP_BASE)
        browser_ws = browser_ws.replace('localhost', parsed.hostname)
        if parsed.port:
            browser_ws = browser_ws.replace(':9222/', f':{parsed.port}/')

    async with websockets.connect(browser_ws, max_size=50 * 1024 * 1024) as ws:
        msg_id = 0

        async def send(method, params=None):
            nonlocal msg_id
            msg_id += 1
            msg = {'id': msg_id, 'method': method, 'params': params or {}}
            await ws.send(json.dumps(msg))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get('id') == msg_id:
                    return resp

        # Find a tab on groups.google.com, or any tab
        with urllib.request.urlopen(f'{CDP_BASE}/json', timeout=5) as resp:
            pages = json.loads(resp.read())

        groups_page = None
        any_page = None
        for p in pages:
            url = p.get('url', '')
            if 'groups.google.com' in url:
                groups_page = p
                break
            if p.get('type') == 'page' and not url.startswith('chrome://'):
                any_page = any_page or p

        target = groups_page or any_page
        if not target:
            raise RuntimeError('No browser tab available for cookie grab')

        async with websockets.connect(
                target['webSocketDebuggerUrl'],
                max_size=10 * 1024 * 1024) as page_ws:
            page_msg_id = 0

            async def page_send(method, params=None):
                nonlocal page_msg_id
                page_msg_id += 1
                msg = {'id': page_msg_id, 'method': method, 'params': params or {}}
                await page_ws.send(json.dumps(msg))
                while True:
                    resp = json.loads(await page_ws.recv())
                    if resp.get('id') == page_msg_id:
                        return resp

            result = await page_send('Network.getCookies',
                                     {'urls': ['https://groups.google.com']})
            cookies = result.get('result', {}).get('cookies', [])

        if not cookies:
            raise RuntimeError(
                'No cookies found — is Chrome Passe running with Google auth?')

        cookie_str = '; '.join(f"{c['name']}={c['value']}" for c in cookies)
        print(f'[cookies] grabbed {len(cookies)} cookies from Chrome Passe',
              file=sys.stderr, flush=True)
        return cookie_str


# ── SSR parser ──────────────────────────────────────────

_AF_PATTERN = re.compile(
    r"AF_initDataCallback\(\{key:\s*'ds:10',\s*"
    r"(?:hash:\s*'\d+',\s*)?"
    r"data:(.*?),\s*sideChannel:\s*\{\}\s*\}\)",
    re.DOTALL,
)


def parse_ssr_data(html: str) -> dict | None:
    """Extract ds:10 AF_initDataCallback data from SSR HTML."""
    m = _AF_PATTERN.search(html)
    if not m:
        return None
    return json.loads(m.group(1).strip())


def extract_tokens(html: str) -> dict:
    """Extract XSRF, session ID, and build label from SSR HTML."""
    xsrf = re.search(r'"SNlM0e":"([^"]+)"', html)
    fsid = re.search(r'"FdrFJe":"([^"]+)"', html)
    bl = re.search(r'"cfb2h":"([^"]+)"', html)
    if not xsrf:
        raise RuntimeError('No XSRF token in page — auth may have expired')
    return {
        'xsrf': xsrf.group(1),
        'fsid': fsid.group(1) if fsid else '',
        'bl': bl.group(1) if bl else '',
    }


# ── Thread listing ──────────────────────────────────────

def parse_thread_entry(t: list) -> dict:
    """Parse a single thread entry from the SSR/RPC data."""
    td = t[0] if isinstance(t[0], list) else t
    timestamp = td[4][0] if isinstance(td[4], list) and td[4] else 0
    author_info = td[9] if len(td) > 9 else []
    author = ''
    if (isinstance(author_info, list) and author_info
            and isinstance(author_info[0], list) and author_info[0]
            and isinstance(author_info[0][0], list) and author_info[0][0]):
        author = author_info[0][0][0] or ''

    return {
        'thread_id': td[1],
        'subject': td[2],
        'snippet': td[3],
        'timestamp': timestamp,
        'author': author,
        'message_count': td[6] if len(td) > 6 else 0,
    }


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    """Prevent urllib from silently following redirects (which hang on auth walls)."""
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(
            newurl, code, f'Redirect {code} → {newurl}', headers, fp)


_opener = urllib.request.build_opener(_NoRedirect)


def fetch_page(url: str, cookies: str) -> str:
    """Fetch a URL with auth cookies. Returns HTML.

    Raises on redirects (302 = auth expired or deleted thread).
    """
    req = urllib.request.Request(url, headers={
        'Cookie': cookies,
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                      'AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/145.0.0.0 Safari/537.36',
    })
    with _opener.open(req, timeout=15) as resp:
        return resp.read().decode()


def list_threads(group_url: str, cookies: str,
                 limit: int | None = None) -> list[dict]:
    """List all threads via SSR page 1 + batchexecute RPC pagination."""
    # Page 1 from SSR
    html = fetch_page(group_url, cookies)
    data = parse_ssr_data(html)
    if not data:
        raise RuntimeError('No SSR data in page — may need re-auth')

    tokens = extract_tokens(html)
    total = data[1]
    token = data[3]

    # Parse group email from the RPC data
    group_id = data[0]
    group_email = group_id[1] if isinstance(group_id, list) and len(group_id) > 1 else None
    if not group_email:
        raise RuntimeError('Could not determine group email from SSR data')

    all_threads = [parse_thread_entry(t) for t in data[2]]
    print(f'[list] page 1 (SSR): {len(data[2])} threads, '
          f'total={total}', file=sys.stderr, flush=True)

    if limit and len(all_threads) >= limit:
        return all_threads[:limit]

    # Paginate via batchexecute RPC
    source_path = urllib.parse.urlparse(group_url).path
    page_num = 1

    while token and (not limit or len(all_threads) < limit):
        page_num += 1
        inner_dq = json.dumps([group_email, 30, token, [], page_num])
        inner_sx = json.dumps([group_email, 3, token, []])
        freq = json.dumps([
            [["Dq0xse", inner_dq, None, "4"],
             ["Sx0Qnf", inner_sx, None, "6"]]
        ])
        body = urllib.parse.urlencode({'f.req': freq, 'at': tokens['xsrf']})

        url = (
            f"https://groups.google.com/_/GroupsFrontendUi/data/batchexecute"
            f"?rpcids=Dq0xse%2CSx0Qnf"
            f"&source-path={urllib.parse.quote(source_path, safe='')}"
            f"&f.sid={tokens['fsid']}"
            f"&bl={tokens['bl']}"
            f"&hl=en-GB&soc-app=696&soc-platform=1&soc-device=1"
            f"&_reqid={250297 + page_num}&rt=c"
        )

        req = urllib.request.Request(url, data=body.encode(), method='POST')
        req.add_header('Cookie', cookies)
        req.add_header('Content-Type',
                       'application/x-www-form-urlencoded;charset=UTF-8')
        req.add_header('User-Agent',
                       'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                       'AppleWebKit/537.36')
        req.add_header('X-Same-Domain', '1')
        req.add_header('Origin', 'https://groups.google.com')
        req.add_header('Referer', 'https://groups.google.com/')

        t0 = time.monotonic()
        with urllib.request.urlopen(req, timeout=30) as resp:
            response = resp.read().decode()
        rpc_ms = round((time.monotonic() - t0) * 1000)

        # Parse response: skip )]}' XSSI prefix
        clean = response
        if ")]}" in clean:
            clean = clean[clean.index(")]}'") + 4:]

        m = re.search(r'\["Dq0xse","(.*?)"(?:,null)', clean, re.DOTALL)
        if not m:
            m = re.search(
                r'\["wrb\.fr","Dq0xse","(.*?)"(?:,null){3}', clean, re.DOTALL)
        if not m:
            print(f'[list] page {page_num}: no Dq0xse in response, stopping',
                  file=sys.stderr, flush=True)
            break

        inner_str = m.group(1).replace('\\"', '"').replace('\\\\', '\\')
        page_data = json.loads(inner_str)
        threads = page_data[2] if len(page_data) > 2 else []
        token = page_data[3] if len(page_data) > 3 else None

        new_threads = [parse_thread_entry(t) for t in threads]
        all_threads.extend(new_threads)

        print(f'[list] page {page_num} (RPC, {rpc_ms}ms): '
              f'+{len(new_threads)}, total: {len(all_threads)}',
              file=sys.stderr, flush=True)

        if not threads:
            break

    if limit:
        all_threads = all_threads[:limit]
    return all_threads


# ── Thread content extraction ───────────────────────────

def extract_thread_messages(html: str) -> dict | None:
    """Parse a thread page's SSR data into structured messages."""
    data = parse_ssr_data(html)
    if not data or len(data) < 3:
        return None

    # data[1] = thread metadata, data[2] = messages array
    meta = data[1]
    subject = meta[2] if len(meta) > 2 else 'Untitled'

    messages = []
    for msg_wrapper in data[2]:
        msg_meta = msg_wrapper[0]
        # Author info is in msg_meta[0][2]
        # which is [[name, avatar, ...], ...]
        author = ''
        msg_info = msg_meta[0] if isinstance(msg_meta[0], list) else []
        if (isinstance(msg_info, list) and len(msg_info) > 2
                and isinstance(msg_info[2], list)):
            author_arr = msg_info[2]
            if author_arr and isinstance(author_arr[0], list):
                author = author_arr[0][0] or ''

        # Timestamp
        timestamp = 0
        if (isinstance(msg_info, list) and len(msg_info) > 1
                and isinstance(msg_info[1], list)):
            content_block = msg_info[1]
            # Find the HTML body — it's in a nested structure
            # msg_meta[0][1] contains [[type, [null, html_body]]]
            pass

        # Body HTML: msg_meta[0][1][2][1][1] based on our investigation
        # But the structure varies. Let's search for HTML content.
        body_html = ''
        body_text = ''
        _find_html_body(msg_meta, body_parts := [])
        if body_parts:
            body_html = body_parts[0]
            # Convert HTML to plain text (basic)
            body_text = _html_to_text(body_html)

        # Date from the message metadata
        date_str = ''
        _find_timestamps(msg_meta, dates := [])
        if dates:
            from datetime import datetime, timezone
            try:
                dt = datetime.fromtimestamp(dates[0], tz=timezone.utc)
                date_str = dt.strftime('%d %b %Y %H:%M')
            except (ValueError, OSError):
                pass

        messages.append({
            'from': author,
            'date': date_str,
            'body': body_text,
            'body_html': body_html,
        })

    return {
        'subject': subject,
        'thread_url': '',  # filled by caller
        'message_count': len(messages),
        'messages': [{'index': i, **m} for i, m in enumerate(messages)],
    }


def _find_html_body(obj, results: list, depth: int = 0):
    """Recursively find HTML body strings in the SSR data structure."""
    if depth > 15:
        return
    if isinstance(obj, str):
        # HTML bodies start with <div or contain HTML tags
        if (obj.startswith('<div') or obj.startswith('<p')
                or obj.startswith('<br') or obj.startswith('<table')
                or ('<div' in obj and len(obj) > 50)):
            results.append(obj)
        return
    if isinstance(obj, list):
        for item in obj:
            _find_html_body(item, results, depth + 1)
            if results:
                return  # take the first one


def _find_timestamps(obj, results: list, depth: int = 0):
    """Find epoch timestamps (10-digit integers) in the data."""
    if depth > 10:
        return
    if isinstance(obj, (int, float)):
        if 1_500_000_000 < obj < 2_000_000_000:
            results.append(int(obj))
        return
    if isinstance(obj, list):
        for item in obj:
            _find_timestamps(item, results, depth + 1)
            if results:
                return


def _html_to_text(html: str) -> str:
    """Basic HTML to plain text conversion."""
    import html as html_module
    text = html
    # Block elements → newlines
    text = re.sub(r'<br\s*/?\s*>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(?:div|p|tr|li|h[1-6])>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<(?:div|p|tr|li|h[1-6])[^>]*>', '\n', text, flags=re.IGNORECASE)
    # Strip all remaining tags
    text = re.sub(r'<[^>]+>', '', text)
    # Decode HTML entities
    text = html_module.unescape(text)
    # Collapse whitespace
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


# ── Cleaning integration ────────────────────────────────

# Import clean_groups_message — avoid mise's package __init__ (broken transitive imports).
# Import talon directly, then clean.py's function.
sys.path.insert(0, '/Users/modha/Repos/mise-en-space')
import importlib
_talon = importlib.import_module('extractors.talon_signature')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from clean import clean_groups_message


def clean_and_format(thread_data: dict) -> str:
    """Clean and format extracted thread data as markdown."""
    subject = thread_data.get('subject', 'Untitled Thread')
    total = thread_data['message_count']
    parts = [f"# {subject}\n"]

    for m in thread_data['messages']:
        i = m['index']
        header = f"[{i+1}/{total}] From: {m['from']} | Date: {m['date']}"
        cleaned = clean_groups_message(m['body'])

        if i > 0:
            parts.append("\n---\n")
        parts.append(f"{header}\n")
        parts.append(cleaned if cleaned else '*(empty)*')
        parts.append("")

    return '\n'.join(parts)


# ── Checkpoint/resume ───────────────────────────────────

def load_checkpoint(output_dir: Path) -> set[str]:
    """Load set of already-extracted thread IDs from checkpoint file."""
    cp = output_dir / '.checkpoint.jsonl'
    done = set()
    if cp.exists():
        with open(cp) as f:
            for line in f:
                entry = json.loads(line)
                done.add(entry['thread_id'])
    return done


def save_checkpoint(output_dir: Path, thread_id: str, subject: str):
    """Append a thread ID to the checkpoint file."""
    cp = output_dir / '.checkpoint.jsonl'
    with open(cp, 'a') as f:
        f.write(json.dumps({'thread_id': thread_id, 'subject': subject}) + '\n')


# ── Main pipeline ───────────────────────────────────────

def make_thread_url(group_url: str, thread_id: str) -> str:
    """Construct thread URL from group URL and thread ID."""
    return f"{group_url.rstrip('/')}/c/{thread_id}"


def sanitize_filename(subject: str, thread_id: str) -> str:
    """Create a safe filename from subject and thread ID."""
    # Keep alphanumeric, spaces, hyphens
    clean = re.sub(r'[^\w\s-]', '', subject)
    clean = re.sub(r'\s+', '-', clean.strip())
    clean = clean[:80]  # truncate
    return f"{clean}_{thread_id}.md" if clean else f"{thread_id}.md"


def main():
    import argparse
    parser = argparse.ArgumentParser(
        description='Extract Google Groups threads to clean markdown')
    parser.add_argument('group_url', help='Google Groups URL')
    parser.add_argument('output_dir', help='Output directory for markdown files')
    parser.add_argument('--limit', type=int, default=None,
                        help='Max threads to extract (for testing)')
    parser.add_argument('--resume', action='store_true',
                        help='Skip already-extracted threads')
    parser.add_argument('--list-only', action='store_true',
                        help='Only list threads, do not fetch content')
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Grab cookies
    print('[extract] grabbing cookies from Chrome Passe...', file=sys.stderr, flush=True)
    cookies = asyncio.run(grab_cookies(args.group_url))

    # Step 2: List all threads
    print('[extract] listing threads...', file=sys.stderr, flush=True)
    t0 = time.monotonic()
    threads = list_threads(args.group_url, cookies, limit=args.limit)
    list_ms = round((time.monotonic() - t0) * 1000)
    print(f'[extract] found {len(threads)} threads in {list_ms}ms',
          file=sys.stderr, flush=True)

    # Save thread listing
    listing_path = output_dir / 'threads.json'
    with open(listing_path, 'w') as f:
        json.dump({'thread_count': len(threads), 'threads': threads}, f, indent=2)
    print(f'[extract] thread listing → {listing_path}', file=sys.stderr, flush=True)

    if args.list_only:
        return

    # Step 3: Fetch and extract each thread
    done = load_checkpoint(output_dir) if args.resume else set()
    if done:
        print(f'[extract] resuming: {len(done)} threads already done',
              file=sys.stderr, flush=True)

    extracted = 0
    skipped = 0
    errors = 0
    consecutive_errors = 0

    for i, thread in enumerate(threads):
        tid = thread['thread_id']
        subject = thread['subject']

        if tid in done:
            skipped += 1
            continue

        thread_url = make_thread_url(args.group_url, tid)
        t0 = time.monotonic()

        try:
            html = fetch_page(thread_url, cookies)
            thread_data = extract_thread_messages(html)

            if not thread_data:
                print(f'[extract] {i+1}/{len(threads)}: no data — {subject[:50]}',
                      file=sys.stderr, flush=True)
                errors += 1
                consecutive_errors += 1
                if consecutive_errors >= 5:
                    print('[extract] 5 consecutive errors — cookies likely expired. '
                          'Re-run to refresh.', file=sys.stderr, flush=True)
                    break
                continue

            thread_data['thread_url'] = thread_url

            # Clean and format
            md = clean_and_format(thread_data)

            # Write output
            filename = sanitize_filename(subject, tid)
            out_path = output_dir / filename
            with open(out_path, 'w') as f:
                f.write(md)

            # Checkpoint
            save_checkpoint(output_dir, tid, subject)
            extracted += 1
            consecutive_errors = 0
            ms = round((time.monotonic() - t0) * 1000)

            print(f'[extract] {i+1}/{len(threads)} ({ms}ms): '
                  f'{thread_data["message_count"]} msgs — {subject[:50]}',
                  file=sys.stderr, flush=True)

        except Exception as e:
            ms = round((time.monotonic() - t0) * 1000)
            print(f'[extract] {i+1}/{len(threads)} ERROR ({ms}ms): '
                  f'{e} — {subject[:50]}', file=sys.stderr, flush=True)
            errors += 1
            consecutive_errors += 1
            if consecutive_errors >= 5:
                print('[extract] 5 consecutive errors — cookies likely expired. '
                      'Re-run to refresh.', file=sys.stderr, flush=True)
                break

    print(f'\n[extract] done: {extracted} extracted, {skipped} skipped, '
          f'{errors} errors', file=sys.stderr, flush=True)


if __name__ == '__main__':
    main()
