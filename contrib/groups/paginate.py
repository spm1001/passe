#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = ["websockets"]
# ///
"""
Google Groups thread list paginator.

Uses raw CDP WebSocket to maintain a single persistent foreground tab.
Page.bringToFront is required — Google's Closure jsaction handlers
silently ignore clicks on background tabs.

Usage:
    uv run --script contrib/groups/paginate.py <group_url> <output_json> [max_pages]

Environment:
    PASSE_CDP  CDP endpoint (default http://localhost:9222)
"""

import asyncio
import json
import os
import sys
import urllib.request

CDP_BASE = os.environ.get('PASSE_CDP', 'http://localhost:9222')

EXTRACT_JS = r"""
(function() {
  const rows = document.querySelectorAll('.yhgbKd');
  const threads = [];
  rows.forEach(row => {
    const link = row.querySelector('a.ZLl54[href*="/c/"]');
    if (!link) return;
    const href = link.getAttribute('href');
    const threadId = href.match(/\/c\/([^/?]+)/)?.[1];
    if (!threadId) return;
    threads.push({
      thread_id: threadId,
      subject: row.querySelector('.t17a0d')?.textContent?.trim() || '',
      url: new URL(href, window.location.origin).href,
      date: row.querySelector('.tRlaM')?.textContent?.trim() || '',
      participants: row.querySelector('.VWSb7b a.ZLl54')?.textContent?.trim() || ''
    });
  });
  const btn = document.querySelector('[aria-label="Next page"]');
  const hasNext = btn && btn.getAttribute('aria-disabled') !== 'true';
  const m = document.body.innerText.match(/(\d+)[–-](\d+)\s+of\s+(\d+)/);
  return JSON.stringify({threads, has_next: !!hasNext, range: m?.[0] || '', total: m ? +m[3] : 0});
})()
"""

NEXT_POS_JS = r"""
(function() {
  const btn = document.querySelector('[aria-label="Next page"]');
  if (!btn) return 'null';
  const r = btn.getBoundingClientRect();
  return JSON.stringify({x: r.x + r.width/2, y: r.y + r.height/2});
})()
"""


async def main():
    import websockets

    group_url = sys.argv[1]
    output_path = sys.argv[2]
    max_pages = int(sys.argv[3]) if len(sys.argv) > 3 else 50

    # Get browser websocket URL
    with urllib.request.urlopen(f'{CDP_BASE}/json/version', timeout=5) as resp:
        version = json.loads(resp.read())
    browser_ws = version['webSocketDebuggerUrl']
    # Rewrite localhost if remote
    if not CDP_BASE.startswith('http://localhost'):
        from urllib.parse import urlparse
        parsed = urlparse(CDP_BASE)
        browser_ws = browser_ws.replace('localhost', parsed.hostname)
        if parsed.port:
            browser_ws = browser_ws.replace(':9222/', f':{parsed.port}/')

    print(f"Connecting to {browser_ws}", file=sys.stderr)

    async with websockets.connect(browser_ws, max_size=50*1024*1024) as ws:
        msg_id = 0

        async def send_cdp(method, params=None, session_id=None):
            nonlocal msg_id
            msg_id += 1
            msg = {'id': msg_id, 'method': method, 'params': params or {}}
            if session_id:
                msg['sessionId'] = session_id
            await ws.send(json.dumps(msg))
            while True:
                resp = json.loads(await ws.recv())
                if resp.get('id') == msg_id:
                    return resp

        async def evaluate(expression, session_id):
            r = await send_cdp('Runtime.evaluate', {
                'expression': expression,
                'returnByValue': True,
            }, session_id)
            return r.get('result', {}).get('result', {}).get('value', '')

        # Create foreground tab (background: False is critical for jsaction)
        r = await send_cdp('Target.createTarget', {'url': group_url, 'background': False})
        target_id = r['result']['targetId']

        r = await send_cdp('Target.attachToTarget', {'targetId': target_id, 'flatten': True})
        session_id = r['result']['sessionId']

        await send_cdp('Page.enable', {}, session_id)
        await send_cdp('Runtime.enable', {}, session_id)
        await send_cdp('Page.bringToFront', {}, session_id)

        # Wait for initial page load
        await asyncio.sleep(4)

        all_threads = []
        seen = set()

        for page in range(1, max_pages + 1):
            raw = await evaluate(EXTRACT_JS, session_id)
            if not raw:
                print(f"  Page {page}: empty eval, waiting more...", file=sys.stderr)
                await asyncio.sleep(3)
                raw = await evaluate(EXTRACT_JS, session_id)

            data = json.loads(raw) if raw else {'threads': [], 'has_next': False}

            new_count = 0
            for t in data.get('threads', []):
                if t['thread_id'] not in seen:
                    seen.add(t['thread_id'])
                    all_threads.append(t)
                    new_count += 1

            print(f"  Page {page}: +{new_count} (total: {len(all_threads)}) [{data.get('range', '?')}]",
                  file=sys.stderr)

            if not data.get('has_next') or new_count == 0:
                break

            # Click Next button via CDP mouse events
            pos_raw = await evaluate(NEXT_POS_JS, session_id)
            pos = json.loads(pos_raw) if pos_raw and pos_raw != 'null' else None
            if not pos:
                print("  No Next button, stopping.", file=sys.stderr)
                break

            # Retry loop: click and verify the page actually advanced
            prev_range = data.get('range', '')
            for attempt in range(3):
                for evt in ['mousePressed', 'mouseReleased']:
                    await send_cdp('Input.dispatchMouseEvent', {
                        'type': evt, 'x': pos['x'], 'y': pos['y'],
                        'button': 'left', 'clickCount': 1,
                    }, session_id)

                await asyncio.sleep(3)

                # Verify page actually changed
                verify_raw = await evaluate(EXTRACT_JS, session_id)
                verify_data = json.loads(verify_raw) if verify_raw else {}
                new_range = verify_data.get('range', '')
                if new_range != prev_range:
                    break
                print(f"  Page {page}: click attempt {attempt+1} didn't advance, retrying...",
                      file=sys.stderr)
            else:
                print(f"  Page {page}: click failed after 3 attempts, stopping.", file=sys.stderr)
                break

        # Clean up: close the tab
        await send_cdp('Page.navigate', {'url': 'about:blank'}, session_id)
        await asyncio.sleep(0.5)
        await send_cdp('Target.closeTarget', {'targetId': target_id})

    with open(output_path, 'w') as f:
        json.dump({'thread_count': len(all_threads), 'threads': all_threads}, f, indent=2)
    print(f"\nCollected {len(all_threads)} threads → {output_path}", file=sys.stderr)


if __name__ == '__main__':
    asyncio.run(main())
