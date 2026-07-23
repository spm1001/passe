"""CLI subcommands — run, screenshot, eval, devices, tabs."""

import json
import os
import sys


def _hints_enabled():
    """Check if stderr hints are enabled (PASSE_HINTS != '0')."""
    return os.environ.get('PASSE_HINTS', '1') != '0'

from passe.connection import connect, ChromeConnectionError
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


def _script_uses_cached_refs(steps) -> bool:
    """True when the script acts on eN refs BEFORE any navigation.

    Such a script is the act-step of a previous invocation's scout — the
    refs cache knows which tab the refs were snapped in. A goto before the
    first eN use makes cached refs irrelevant (navigation clears them).
    """
    from passe.refcache import REF_PATTERN
    for verb, args in steps:
        if verb in ('goto', 'back', 'forward'):
            return False
        if verb in ('click', 'type', 'hover', 'tap') and args \
                and REF_PATTERN.match(args[0]):
            return True
    return False


async def _resolve_reuse_tab(client, steps, goto_origin, tab_pattern,
                             endpoint):
    """Pick the tab --reuse-tab should attach to. Returns (target_id, url, via).

    Ladder: --tab pattern > cached eN refs > last kept tab > goto-origin
    match. NO silent fallback: the old "first non-chrome:// tab" grab landed
    in the human's live tab on shared browsers (2026-07-21) and in
    chrome://newtab once the kept tab had vanished (2026-07-23) — failing
    with the open-tab list beats acting in the wrong tab.
    """
    from passe import refcache, tabmemory

    tabs = await client.list_tabs()
    by_id = {t['target_id']: t for t in tabs}
    notes = []

    def _listing(subset=None):
        rows = subset if subset is not None else tabs
        return '\n'.join(f"  {t['target_id'][:12]}  {t['url'][:70]}"
                         for t in rows) or '  (none)'

    if tab_pattern:
        matches = [t for t in tabs
                   if t['target_id'].startswith(tab_pattern)
                   or tab_pattern.lower() in t['url'].lower()]
        if len(matches) == 1:
            t = matches[0]
            return t['target_id'], t['url'], f'--tab {tab_pattern}'
        kind = ('matches multiple tabs — be more specific'
                if matches else 'matches no open tab')
        raise RuntimeError(
            f'--tab {tab_pattern!r} {kind}:\n{_listing(matches or None)}')

    if _script_uses_cached_refs(steps):
        tab_id = refcache.newest_refs_tab(by_id.keys())
        if tab_id:
            return tab_id, by_id[tab_id]['url'], 'cached eN refs'
        notes.append('script uses eN refs but no open tab has cached refs '
                     '(re-run ax-tree --flat-refs)')

    record = tabmemory.load_last_tab(endpoint)
    if record:
        rec_id = record.get('target_id')
        if rec_id in by_id:
            return rec_id, by_id[rec_id]['url'], 'last kept tab'
        tabmemory.clear_last_tab(endpoint)
        notes.append('the last kept tab is gone '
                     f"({record.get('url') or rec_id})")

    if goto_origin:
        for t in tabs:
            if t['url'].startswith(goto_origin):
                return t['target_id'], t['url'], f'origin {goto_origin}'
        notes.append(f'no open tab at {goto_origin}')

    why = ('; '.join(notes) + '. ') if notes else ''
    raise RuntimeError(
        f'reuse-tab: cannot determine which tab to resume. {why}'
        f'Open tabs:\n{_listing()}\n'
        f'Target one explicitly with --tab <id-or-url-substring>, '
        f'or start fresh without --reuse-tab.')


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
                  foreground: bool = False, frame: str = None,
                  device: str = None, dpr: float = None,
                  tab: str = None):
    """Run a passe script from file, stdin, or inline."""
    # --tab names a reuse target; --reuse-tab implies --keep-tab
    # (don't close someone else's tab)
    if tab:
        reuse_tab = True
    if reuse_tab:
        keep_tab = True
    # --frame implies --keep-tab (we don't own the iframe or its parent)
    if frame:
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
        # Extract origin from first goto (used by --reuse-tab and --keep-tab auto-replace)
        goto_origin = None
        for verb, args in steps:
            if verb == 'goto' and args:
                from urllib.parse import urlparse
                parsed = urlparse(args[0])
                goto_origin = f'{parsed.scheme}://{parsed.netloc}'
                break

        # Auto-launched headless Chrome dies at teardown — no tab survives
        ephemeral_browser = conn_info.get('_process') is not None

        if frame:
            await client.attach_to_frame(frame)
        elif reuse_tab:
            target_id, tab_url, via = await _resolve_reuse_tab(
                client, steps, goto_origin, tab, conn_info['cdp'])
            await client.attach_to_tab(target_id)
            print(f'[passe] reuse-tab: {tab_url} (via {via})',
                  file=sys.stderr)
        else:
            # Auto-replace: close previous tabs at same origin before creating new one.
            # Prevents tab accumulation on repeated --keep-tab runs.
            if keep_tab and goto_origin:
                closed = await client.close_tabs_by_origin(goto_origin)
                if closed:
                    print(f'[passe] closed {closed} existing tab(s) at {goto_origin}',
                          file=sys.stderr)
            # A GUI window passe just launched has no human context to
            # disturb — work in front where the human can see (passe-cavudo)
            fresh_gui = conn_info.get('launched') == 'gui'
            if fresh_gui and not foreground:
                print('[passe] fresh Chrome window — running in the foreground tab',
                      file=sys.stderr)
            await client.create_tab(foreground=foreground or fresh_gui)
        await client.send('Page.enable')
        # Apply device preset before script if --device flag used
        if device:
            await do_device(client, device, dpr_override=dpr)
        script_ok = True
        summary = None
        try:
            summary = await run_script(client, steps)
            summary['cdp'] = conn_info['cdp']
            summary['browser'] = conn_info['browser']
            script_ok = summary.get('ok', True)
            if not script_ok and keep_on_fail and not keep_tab:
                if ephemeral_browser:
                    # Don't promise a resume in a browser we're about to kill
                    print('[passe] script failed — auto-launched headless '
                          'Chrome exits with the run, so no tab is kept. '
                          'To debug interactively, point --cdp at a running '
                          'Chrome and re-run.', file=sys.stderr)
                else:
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
            if should_keep and ephemeral_browser:
                # Nothing to keep — teardown takes the browser and its tabs
                if keep_tab:
                    print('[passe] note: --keep-tab has no effect — '
                          'auto-launched headless Chrome exits with the run',
                          file=sys.stderr)
            elif should_keep:
                # Remember the kept tab so a later --reuse-tab resumes THIS
                # tab, not whatever is first in Chrome's register. Skip in
                # frame mode (_target_id would be the iframe, not a tab).
                if not frame:
                    from passe import tabmemory
                    target_id = getattr(client, '_target_id', None)
                    if isinstance(target_id, str) and target_id:
                        tabmemory.save_last_tab(
                            conn_info['cdp'], target_id,
                            (summary or {}).get('final_url', ''))
                # Flash timer is explicit-only. The old 30s keep-on-fail
                # default never actually worked: window.close() is blocked
                # for tabs with navigation history and no script opener
                # (verified live 2026-07-23), and a tab silently vanishing
                # costs more than a stray tab.
                if flash and flash > 0 and not reuse_tab:
                    try:
                        await client.send('Runtime.evaluate', {
                            'expression': _FLASH_JS % (flash * 1000, flash),
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

    # --- HTTP fast-path: try before Chrome ---
    # Skip if: device emulation needed, or source forces browser-side extraction.
    # fast_path_reason records why Chrome took over — no silent attempts
    # (passe-nopiku).
    fast_path_reason = None
    if device:
        fast_path_reason = 'skipped: device emulation needs Chrome'
    elif source in ('readability', 'innertext'):
        fast_path_reason = f'skipped: --source {source} is browser-side'
    else:
        from passe.fastpath import try_http_fetch
        fp_result = try_http_fetch(url, force_source=source)
        if fp_result and fp_result.quality_score >= 0.35 and not fp_result.escalate_reason:
            word_count, resolved_path = resolve_fetch_output(
                fp_result.markdown, path if explicit_path else None)
            summary = {
                'ok': True, 'steps': 1,
                'total_ms': fp_result.fetch_ms,
                'final_url': fp_result.url,
                'fast_path': True,
            }
            if resolved_path is None:
                summary['content'] = fp_result.markdown
                summary['word_count'] = word_count
                summary['source'] = fp_result.source
                if fp_result.content_type:
                    summary['content_type'] = fp_result.content_type
            else:
                # resolve_fetch_output writes auto-temp files but not explicit
                # paths (Chrome path writes via do_fetch_verb). Fast-path must
                # write explicit paths itself.
                if explicit_path:
                    with open(resolved_path, 'w') as f:
                        f.write(fp_result.markdown)
                file_entry = {
                    'path': resolved_path, 'verb': 'fetch',
                    'source': fp_result.source,
                    'word_count': word_count,
                }
                if fp_result.content_type:
                    file_entry['content_type'] = fp_result.content_type
                summary['files'] = [file_entry]
            _emit_summary(summary)
            print(json.dumps(summary))
            return
        fast_path_reason = (fp_result.escalate_reason
                            if fp_result and fp_result.escalate_reason
                            else 'unknown')

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
                'fast_path': False,
                'fast_path_reason': fast_path_reason,
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

            # Exit code 1 for thin/degraded extraction
            # Only flag thin_read from the extraction cascade — don't second-guess
            # based on word count alone (short pages are legitimate)
            thin = bool(result.get('thin_read'))
            if thin:
                summary['thin'] = True

            _emit_summary(summary)
            print(json.dumps(summary))

            if thin:
                sys.exit(1)
        except Exception as exc:
            ms = round((time.monotonic() - t0) * 1000, 1)
            summary = {
                'ok': False, 'steps': 1, 'total_ms': ms,
                'verb': 'fetch', 'error': str(exc),
                'cdp': conn_info['cdp'],
                'browser': conn_info['browser'],
                'fast_path': False,
                'fast_path_reason': fast_path_reason,
            }
            _emit_summary(summary)
            print(json.dumps(summary))
            sys.exit(2)  # tool failure
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
                      filter_noise: bool = False,
                      device: str = None, dpr: float = None):
    """Atomic capture: create tab, enable network, goto + wait-idle, write JSONL."""
    import time
    from passe.runner import _build_capture_summary, _write_capture_jsonl
    from passe.verbs import do_navigate, do_wait_idle

    async with connect() as (client, conn_info):
        await client.create_tab()
        await client.send('Page.enable')
        await client.enable_network(large_buffers=True)
        if device:
            await do_device(client, device, dpr_override=dpr)
        try:
            t0 = time.monotonic()
            nav = await do_navigate(client, url)
            await do_wait_idle(client, timeout=30)

            requests = client.get_network_requests()
            # Filter analytics/tracking noise
            if filter_noise:
                from passe.log_daemon import should_skip_url, should_skip_mime
                requests = [r for r in requests
                            if not should_skip_url(r.get('url', ''))
                            and not should_skip_mime(r.get('content_type'))]
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
            tab_info = {'id': client._target_id or '',
                        'url': nav.get('url', url)}
            _write_capture_jsonl(path, requests, tab_info=tab_info)
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


async def cmd_screenshot(args: list[str], device: str = None, dpr: float = None,
                         frame: str = None):
    """Atomic screenshot of current page. Parses --fast, --viewport, --format, --quality."""
    output, fmt, quality, viewport_only, optimize = parse_screenshot_flags(args)
    async with connect() as (client, conn_info):
        if frame:
            await client.attach_to_frame(frame)
        else:
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


async def cmd_eval(expression: str, frame: str = None):
    """Atomic JS eval on current page."""
    async with connect() as (client, conn_info):
        if frame:
            await client.attach_to_frame(frame)
        else:
            await client.attach_to_first_page()
            await _warn_if_blank_page(client)
        result = await do_eval(client, expression)
        print(result)


def cmd_status():
    """Probe Chrome connection and report status for Claude consumption."""
    import urllib.request
    from passe.connection import _cdp_base_url, _is_loopback, discover_chrome

    base_url = _cdp_base_url()
    is_remote = not _is_loopback(base_url)

    fields = {
        'cdp_endpoint': base_url,
        'remote': is_remote,
        'reachable': False,
    }

    try:
        _, info = discover_chrome()
        fields['reachable'] = True
        fields['chrome_version'] = info.get('browser', 'unknown')

        # Get tab count via lightweight HTTP (no WebSocket needed)
        try:
            with urllib.request.urlopen(f'{base_url}/json/list', timeout=3) as resp:
                tabs = json.loads(resp.read())
                page_tabs = [t for t in tabs if t.get('type') == 'page']
                fields['tabs_open'] = len(page_tabs)
        except Exception:
            fields['tabs_open'] = '?'

    except ChromeConnectionError as exc:
        fields['reason'] = exc.reason
        fields['alternatives'] = '; '.join(exc.alternatives)

    for key, val in fields.items():
        print(f'[passe:status] {key}={val}', file=sys.stderr)


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


async def cmd_tabs(show_frames: bool = False):
    """List all Chrome tabs, optionally including iframe targets."""
    async with connect() as (client, conn_info):
        tabs = await client.list_tabs()
        if not tabs and not show_frames:
            print('No tabs open', file=sys.stderr)
            return
        for i, tab in enumerate(tabs):
            url = tab['url'] or 'about:blank'
            title = tab['title']
            line = f'[{i}] {url}'
            if title and title != url:
                line += f'  ({title})'
            print(line)
        if show_frames:
            frames = await client.list_frames()
            if frames:
                print(file=sys.stderr)
                for j, f in enumerate(frames):
                    url = f['url'] or 'about:blank'
                    title = f['title']
                    parent = f['parent_id'][:8] if f['parent_id'] else '?'
                    line = f'  iframe [{j}] {url}  (parent: {parent})'
                    if title and title != url:
                        line += f'  {title}'
                    print(line)
                print(f'\n{len(tabs)} tab(s), {len(frames)} iframe(s)',
                      file=sys.stderr)
            else:
                print(f'\n{len(tabs)} tab(s), 0 iframes', file=sys.stderr)
        else:
            print(f'\n{len(tabs)} tab(s)', file=sys.stderr)


async def cmd_tabs_close(args: list[str]):
    """Close Chrome tabs. --all closes all but one, --matching PATTERN filters by URL."""
    import re
    close_all = '--all' in args
    pattern = None
    if '--matching' in args:
        idx = args.index('--matching')
        if idx + 1 < len(args):
            pattern = args[idx + 1]
        else:
            print('passe tabs close: --matching requires a pattern', file=sys.stderr)
            sys.exit(1)

    if not close_all and not pattern:
        print('passe tabs close: use --all or --matching PATTERN', file=sys.stderr)
        sys.exit(1)

    async with connect() as (client, conn_info):
        tabs = await client.list_tabs()
        if not tabs:
            print('No tabs to close', file=sys.stderr)
            return

        to_close = []
        if close_all:
            # Keep one tab (Chrome quits if all tabs close)
            to_close = tabs[:-1] if len(tabs) > 1 else []
        elif pattern:
            try:
                pat = re.compile(pattern, re.IGNORECASE)
            except re.error:
                pat = None
            for tab in tabs:
                url = tab['url']
                if pat and pat.search(url):
                    to_close.append(tab)
                elif not pat and pattern.lower() in url.lower():
                    to_close.append(tab)
            # Safety: don't close every tab
            if len(to_close) == len(tabs) and len(tabs) > 1:
                to_close = to_close[:-1]
                print('[passe] keeping one tab to prevent Chrome from quitting',
                      file=sys.stderr)

        if not to_close:
            print('No tabs matched', file=sys.stderr)
            return

        closed = 0
        for tab in to_close:
            try:
                await client.send('Target.closeTarget',
                                  {'targetId': tab['target_id']}, timeout=5.0)
                closed += 1
            except Exception:
                pass

        print(f'Closed {closed} tab(s)', file=sys.stderr)
