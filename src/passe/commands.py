"""CLI subcommands — run, screenshot, eval, devices."""

import json
import os
import sys


def _hints_enabled():
    """Check if stderr hints are enabled (PASSE_HINTS != '0')."""
    return os.environ.get('PASSE_HINTS', '1') != '0'

from passe.connection import connect
from passe.parser import (
    CONTENT_INLINE_THRESHOLD, KNOWN_VERBS, VERB_SUGGESTIONS,
    parse_screenshot_flags, parse_script,
    resolve_fetch_output, split_inline, validate_steps,
)
from passe.runner import run_script
from passe.verbs import do_device, do_eval, do_screenshot


def _emit_summary(summary):
    """Emit a human-readable one-liner to stderr after script execution."""
    steps_n = summary.get('steps', 0)
    ms = summary.get('total_ms', 0)

    if not summary.get('ok'):
        verb = summary.get('verb', '?')
        error = summary.get('error', 'unknown error')
        at = summary.get('failed_at', '?')
        print(f'[passe] failed at step {at} ({verb}): {error}',
              file=sys.stderr)
        return

    step_word = 'step' if steps_n == 1 else 'steps'
    parts = [f'{steps_n} {step_word}', f'{ms:.0f}ms']

    # Inline content (no file written)
    if 'content' in summary:
        wc = summary.get('word_count', 0)
        parts.append(f'{wc} words (inline)')

    files = summary.get('files', [])
    for f in files:
        verb = f.get('verb', '')
        path = f.get('path', '')
        if verb == 'screenshot':
            kb = f.get('kb', 0)
            parts.append(f'{path} ({kb:.0f}KB)')
        elif verb in ('read', 'fetch'):
            wc = f.get('word_count', 0)
            parts.append(f'{path} ({wc} words)')
        elif verb == 'snapshot':
            parts.append(path)
        elif verb == 'capture':
            n = f.get('requests', 0)
            parts.append(f'{path} ({n} requests)')
        else:
            parts.append(path)

    url = summary.get('final_url')
    if url:
        parts.append(url)

    print(f'[passe] done: {", ".join(parts)}', file=sys.stderr)


def _emit_fetch_hint(steps):
    """Emit stderr hint when goto+read (or goto+wait+read) detected.

    Fires once per script — suggests the fetch compound verb.
    """
    if not _hints_enabled():
        return
    hinted_fetch = False
    hinted_wait = False
    for i, (verb, args) in enumerate(steps):
        if hinted_fetch and hinted_wait:
            break
        if verb != 'goto':
            continue
        # Look ahead: goto → [wait*] → read?
        j = i + 1
        saw_wait = False
        while j < len(steps) and steps[j][0] == 'wait':
            saw_wait = True
            j += 1
        if j < len(steps) and steps[j][0] in ('read', 'extract'):
            if not hinted_fetch:
                print('[passe] hint: fetch URL [path] combines '
                      'goto+wait+extract in one step', file=sys.stderr)
                hinted_fetch = True
            if saw_wait and not hinted_wait:
                print('[passe] hint: read auto-waits after goto '
                      '— explicit wait is unnecessary', file=sys.stderr)
                hinted_wait = True


def _emit_inline_hints(steps, inline_text):
    """Emit stderr hints when -c input is overly complex.

    Fires once per category: complex script (>4 verbs or >200 chars)
    and long eval (eval/eval-to arg >120 chars).
    """
    if not _hints_enabled():
        return
    # Hint 1: script complexity
    if len(steps) > 4 or len(inline_text) > 200:
        print('[passe] hint: use heredoc for complex scripts '
              '(5+ verbs or long lines)', file=sys.stderr)

    # Hint 2: long eval expressions
    for verb, args in steps:
        if verb in ('eval', 'eval-to', 'assert') and args:
            expr = args[-1]  # expression is last arg (eval-to: path then expr)
            if len(expr) > 120:
                print('[passe] hint: use eval-file for complex JS '
                      '— avoids minifying to one line', file=sys.stderr)
                break


_FLASH_JS = """(function() {
  var t = setTimeout(function() { window.close(); }, %d);
  ['click', 'keydown', 'scroll', 'mousemove'].forEach(function(e) {
    document.addEventListener(e, function() {
      clearTimeout(t);
      try { document.title = document.title.replace(/ \\[flash \\d+s\\]$/, ''); } catch(e) {}
    }, { once: true });
  });
  try { document.title += ' [flash %ds]'; } catch(e) {}
})()"""


async def cmd_run(source: str, inline: str = None,
                  keep_tab: bool = False, reuse_tab: bool = False,
                  keep_on_fail: bool = True, flash: int = None,
                  foreground: bool = False,
                  device: str = None, dpr: float = None):
    """Run a passe script from file, stdin, or inline."""
    # --reuse-tab implies --keep-tab (don't close someone else's tab)
    if reuse_tab:
        keep_tab = True

    # Parse the script text
    if inline:
        # -c 'verb arg; verb arg' — verb-aware split preserves JS semicolons
        text = split_inline(inline)
    elif source == '-':
        text = sys.stdin.read()
    else:
        with open(source) as f:
            text = f.read()

    steps = parse_script(text)
    if inline and steps:
        _emit_inline_hints(steps, inline)
    if steps:
        _emit_fetch_hint(steps)
    if not steps:
        print(json.dumps({'ok': True, 'steps': 0, 'total_ms': 0}))
        return

    async with connect() as (client, conn_info):
        if reuse_tab:
            # Extract origin from first goto to prefer the right tab
            reuse_origin = None
            for verb, args in steps:
                if verb == 'goto' and args:
                    from urllib.parse import urlparse
                    parsed = urlparse(args[0])
                    reuse_origin = f'{parsed.scheme}://{parsed.netloc}'
                    break
            await client.attach_to_visible_page(origin=reuse_origin)
        else:
            await client.create_tab(foreground=foreground)
        await client.send('Page.enable')
        # Apply device preset before script if --device flag used
        if device:
            await do_device(client, device, dpr_override=dpr)
        script_ok = True
        try:
            summary = await run_script(client, steps)
            summary['cdp'] = conn_info['cdp']
            summary['browser'] = conn_info['browser']
            script_ok = summary.get('ok', True)
            if not script_ok and keep_on_fail and not keep_tab:
                summary['tab_kept'] = True
                print('[passe] script failed — tab kept open. Resume with: '
                      'passe run --reuse-tab -c "..."', file=sys.stderr)
            _emit_summary(summary)
            print(json.dumps(summary))
            sys.exit(0 if script_ok else 1)
        except Exception:
            # run_script itself threw — no summary available
            script_ok = False
            raise
        finally:
            should_keep = keep_tab or (not script_ok and keep_on_fail)
            if should_keep:
                # Determine flash timeout: explicit --flash, or default 30s
                # for keep-on-fail tabs (not for explicit --keep-tab)
                flash_s = flash
                if flash_s is None and not script_ok and keep_on_fail:
                    flash_s = 30
                if flash_s and flash_s > 0 and not reuse_tab:
                    try:
                        await client.send('Runtime.evaluate', {
                            'expression': _FLASH_JS % (flash_s * 1000, flash_s),
                        })
                    except Exception:
                        pass  # best-effort — page may have crashed
            else:
                await client.close_tab()


async def cmd_fetch(url: str, path: str = None,
                    source: str = None, device: str = None, dpr: float = None):
    """Atomic fetch: create tab, goto + auto-wait + read, close tab."""
    import time
    from passe.verbs import do_fetch as do_fetch_verb

    explicit_path = path is not None

    async with connect() as (client, conn_info):
        await client.create_tab()
        await client.send('Page.enable')
        if device:
            await do_device(client, device, dpr_override=dpr)
        try:
            t0 = time.monotonic()
            # Pass path=None when no explicit path — let do_read skip file write
            # We'll decide after seeing the content whether to inline or write
            result = await do_fetch_verb(
                client, url, path if explicit_path else None,
                force_source=source,
            )
            ms = round((time.monotonic() - t0) * 1000, 1)

            md = result.get('markdown', '')
            word_count, resolved_path = resolve_fetch_output(
                md, path if explicit_path else None)

            summary = {
                'ok': True, 'steps': 1, 'total_ms': ms,
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            if result.get('nav_url'):
                summary['final_url'] = result['nav_url']

            if resolved_path is None:
                summary['content'] = md
                summary['word_count'] = word_count
                summary['source'] = result.get('source')
                if result.get('content_type'):
                    summary['content_type'] = result['content_type']
            else:
                file_entry = {
                    'path': resolved_path, 'verb': 'fetch',
                    'source': result.get('source'),
                    'word_count': word_count,
                }
                if result.get('content_type'):
                    file_entry['content_type'] = result['content_type']
                summary['files'] = [file_entry]

            _emit_summary(summary)
            print(json.dumps(summary))
        except Exception as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            summary = {
                'ok': False, 'steps': 1, 'total_ms': ms,
                'verb': 'fetch', 'error': str(exc),
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            _emit_summary(summary)
            print(json.dumps(summary))
            sys.exit(1)
        finally:
            await client.close_tab()


async def cmd_look(url: str, path: str = None,
                   device: str = None, dpr: float = None):
    """Atomic look: create tab, goto + screenshot --fast, close tab."""
    import tempfile
    import time
    from passe.verbs import do_navigate

    async with connect() as (client, conn_info):
        await client.create_tab()
        await client.send('Page.enable')
        if device:
            await do_device(client, device, dpr_override=dpr)
        try:
            t0 = time.monotonic()
            nav = await do_navigate(client, url)
            output = path or os.path.join(tempfile.gettempdir(), 'passe-look.jpg')
            info = await do_screenshot(client, output, viewport_only=True,
                                       fmt='jpeg', quality=70,
                                       optimize_speed=True)
            ms = round((time.monotonic() - t0) * 1000, 1)
            summary = {
                'ok': True, 'steps': 2, 'total_ms': ms,
                'files': [{'path': info['file'], 'verb': 'screenshot',
                           'format': 'jpeg', 'kb': info['kb']}],
                'final_url': nav.get('url', url),
                'status_code': nav.get('status_code'),
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            _emit_summary(summary)
            print(json.dumps(summary))
        except Exception as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            summary = {
                'ok': False, 'steps': 2, 'total_ms': ms,
                'verb': 'look', 'error': str(exc),
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            _emit_summary(summary)
            print(json.dumps(summary))
            sys.exit(1)
        finally:
            await client.close_tab()


async def cmd_check(url: str, contains: str, screenshot_path: str = None,
                    device: str = None, dpr: float = None):
    """Atomic check: goto URL, assert text is present, optional screenshot."""
    import time
    from passe.verbs import do_navigate, do_assert

    async with connect() as (client, conn_info):
        await client.create_tab()
        await client.send('Page.enable')
        if device:
            await do_device(client, device, dpr_override=dpr)
        try:
            t0 = time.monotonic()
            nav = await do_navigate(client, url)
            # Build JS assertion that checks for text in the page body
            escaped = contains.replace('\\', '\\\\').replace("'", "\\'")
            expr = f"document.body.innerText.includes('{escaped}')"
            await do_assert(client, expr)

            files = []
            if screenshot_path:
                info = await do_screenshot(client, screenshot_path,
                                           viewport_only=True, fmt='jpeg',
                                           quality=70, optimize_speed=True)
                files.append({'path': info['file'], 'verb': 'screenshot',
                              'format': 'jpeg', 'kb': info['kb']})

            ms = round((time.monotonic() - t0) * 1000, 1)
            step_count = 2 + (1 if screenshot_path else 0)
            summary = {
                'ok': True, 'steps': step_count, 'total_ms': ms,
                'final_url': nav.get('url', url),
                'status_code': nav.get('status_code'),
                'contains': contains,
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            if files:
                summary['files'] = files
            _emit_summary(summary)
            print(json.dumps(summary))
        except Exception as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            summary = {
                'ok': False, 'steps': 2, 'total_ms': ms,
                'verb': 'check', 'error': str(exc),
                'contains': contains,
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            _emit_summary(summary)
            print(json.dumps(summary))
            sys.exit(1)
        finally:
            await client.close_tab()


async def cmd_capture(url: str, path: str, bodies: bool = False,
                      device: str = None, dpr: float = None):
    """Atomic capture: create tab, enable network, goto + wait-idle, write JSONL."""
    import time
    from passe.runner import _build_capture_summary, _write_capture_jsonl
    from passe.verbs import do_navigate, do_wait_idle

    async with connect() as (client, conn_info):
        await client.create_tab()
        await client.send('Page.enable')
        await client.enable_network()
        if device:
            await do_device(client, device, dpr_override=dpr)
        try:
            t0 = time.monotonic()
            nav = await do_navigate(client, url)
            await do_wait_idle(client, timeout=30)

            requests = client.get_network_requests()
            if bodies:
                import base64 as b64
                for r in requests:
                    if not r.get('completed'):
                        continue
                    try:
                        body_result = await client.send('Network.getResponseBody', {
                            'requestId': r['requestId'],
                        })
                        body_data = body_result.get('result', {})
                        body = body_data.get('body', '')
                        is_base64 = body_data.get('base64Encoded', False)
                        r['body'] = body
                        r['body_base64'] = is_base64
                        r['body_size'] = (len(b64.b64decode(body))
                                          if is_base64 else len(body))
                    except Exception:
                        pass
            _write_capture_jsonl(path, requests)
            cap_summary = _build_capture_summary(requests)
            ms = round((time.monotonic() - t0) * 1000, 1)

            file_entry = {'path': path, 'verb': 'capture'}
            file_entry.update(cap_summary)
            summary = {
                'ok': True, 'steps': 3, 'total_ms': ms,
                'files': [file_entry],
                'final_url': nav.get('url', url),
                'status_code': nav.get('status_code'),
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            _emit_summary(summary)
            print(json.dumps(summary))
        except Exception as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            summary = {
                'ok': False, 'steps': 3, 'total_ms': ms,
                'verb': 'capture', 'error': str(exc),
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
            }
            _emit_summary(summary)
            print(json.dumps(summary))
            sys.exit(1)
        finally:
            await client.close_tab()


def cmd_explain(source: str, inline: str = None):
    """Dry-run: parse and validate a script without executing it."""
    # Parse input (same as cmd_run)
    if inline is not None:
        text = split_inline(inline)
    elif source == '-':
        text = sys.stdin.read()
    else:
        with open(source) as f:
            text = f.read()

    steps = parse_script(text)
    if not steps:
        print(json.dumps({'ok': True, 'steps': 0, 'errors': [], 'warnings': []}))
        return

    # Validate
    errors = validate_steps(steps)
    warnings = []

    # Analyse: collect metadata
    verbs_used = [v for v, _ in steps]
    selectors = []
    files_created = []
    urls = []

    for verb, args in steps:
        if verb in ('click', 'click-if', 'hover', 'tap', 'type', 'fill',
                     'select', 'wait-for') and args:
            selectors.append(args[0])
        if verb in ('click-text',) and args:
            selectors.append(f'text:{args[0]}')
        if verb == 'goto' and args:
            urls.append(args[0])
        if verb == 'fetch' and args:
            fetch_args = [a for a in args if not a.startswith('--')]
            if fetch_args:
                urls.append(fetch_args[0])
        if verb in ('screenshot', 'snapshot', 'read', 'fetch') and args:
            clean = [a for a in args if not a.startswith('--')]
            if clean:
                files_created.append({'verb': verb, 'path': clean[-1]
                                      if verb != 'fetch' else
                                      (clean[1] if len(clean) > 1 else None)})
        if verb == 'eval-to' and len(args) >= 1:
            files_created.append({'verb': verb, 'path': args[0]})
        if verb == 'eval-file-to' and len(args) >= 1:
            files_created.append({'verb': verb, 'path': args[0]})
        if verb == 'capture' and args:
            clean = [a for a in args if not a.startswith('--')]
            if clean:
                files_created.append({'verb': verb, 'path': clean[0]})

    # Reuse hint logic: goto+read pattern, inline complexity, long evals
    for i, (verb, args) in enumerate(steps):
        if verb != 'goto':
            continue
        j = i + 1
        saw_wait = False
        while j < len(steps) and steps[j][0] == 'wait':
            saw_wait = True
            j += 1
        if j < len(steps) and steps[j][0] in ('read', 'extract'):
            warnings.append('goto+extract detected — use fetch verb instead '
                            '(goto + auto-wait + extract in one step)')
            if saw_wait:
                warnings.append('Explicit wait before read is unnecessary — '
                                'read auto-waits after navigation verbs')
    if inline:
        if len(steps) > 4 or len(inline) > 200:
            warnings.append('Complex inline script — use heredoc for 5+ verbs')
        for verb, args in steps:
            if verb in ('eval', 'eval-to', 'assert') and args:
                expr = args[-1]
                if len(expr) > 120:
                    warnings.append(f'Long {verb} expression ({len(expr)} chars) '
                                    f'— use eval-file instead')

    # Capture position warning
    for i, (verb, _) in enumerate(steps):
        if verb == 'capture' and i > 0:
            warnings.append('capture is not the first verb — '
                            'network requests from earlier steps will be missed')

    files_created = [f for f in files_created if f.get('path')]

    result = {
        'ok': len(errors) == 0,
        'steps': len(steps),
        'verbs': verbs_used,
        'urls': urls,
        'selectors': selectors,
        'files': files_created,
        'errors': errors,
        'warnings': warnings,
    }
    print(json.dumps(result))
    sys.exit(0 if not errors else 1)


async def _warn_if_blank_page(client):
    """Warn if attached to about:blank or chrome:// — likely stale tab after run."""
    try:
        url = await do_eval(client, 'window.location.href')
        if url in ('about:blank', '') or url.startswith('chrome://'):
            print(f'[passe] warning: attached to {url} — did a previous '
                  f'passe run just close its tab? Use eval-to/screenshot '
                  f'inside the run script instead.', file=sys.stderr)
    except Exception:
        pass


async def cmd_screenshot(args: list[str], device: str = None, dpr: float = None):
    """Atomic screenshot of current page. Parses --fast, --viewport, --format, --quality."""
    output, fmt, quality, viewport_only, optimize = parse_screenshot_flags(args)
    async with connect() as (client, conn_info):
        await client.attach_to_first_page()
        await _warn_if_blank_page(client)
        if device:
            await do_device(client, device, dpr_override=dpr)
        info = await do_screenshot(client, output, viewport_only=viewport_only,
                                   fmt=fmt, quality=quality, optimize_speed=optimize)
        print(json.dumps({
            'ok': True, 'file': info['file'], 'kb': info['kb'],
            'format': info['format'],
        }))


async def cmd_eval(expression: str):
    """Atomic JS eval on current page."""
    async with connect() as (client, conn_info):
        await client.attach_to_first_page()
        await _warn_if_blank_page(client)
        result = await do_eval(client, expression)
        print(result)


def cmd_devices():
    """Print available device presets as a table."""
    from passe._devices import DEVICES
    print(f'{"Name":<16} {"Size":>11}  {"DPR":>6}  {"Type":<7}')
    print(f'{"─" * 16} {"─" * 11}  {"─" * 6}  {"─" * 7}')
    for name, dev in DEVICES.items():
        size = f'{dev["width"]}×{dev["height"]}'
        dpr_num = dev["deviceScaleFactor"]
        dpr = f'{int(dpr_num)}x' if dpr_num == int(dpr_num) else f'{dpr_num}x'
        kind = 'mobile' if dev['mobile'] else 'desktop'
        print(f'{name:<16} {size:>11}  {dpr:>6}  {kind:<7}')
