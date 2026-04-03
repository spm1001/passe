"""Script execution engine — dispatches verbs to action functions."""

import asyncio
import base64
import json
import os
import sys
import time

from passe.client import CDPClient
from passe.parser import (
    CONTENT_INLINE_THRESHOLD, KNOWN_VERBS, NAV_VERBS,
    parse_screenshot_flags, resolve_fetch_output,
    SCROLL_DIRECTIONS, VERB_SUGGESTIONS,
)
from passe.verbs import (
    do_navigate, do_back, do_forward, do_wait_idle,
    do_click, do_click_text, do_fill, do_type, do_select,
    do_press, do_hover, do_tap, do_swipe, do_scroll,
    do_screenshot, do_snapshot, do_read, do_fetch,
    do_device, do_viewport, do_wait_for, do_wait_stable,
    do_eval, do_eval_to, do_eval_file, do_eval_file_to,
    do_assert, do_watch, do_frame,
    do_ax_tree, do_ax_find, do_ax_node,
)


def _parse_timeout(s: str, default: float) -> float:
    """Parse a user-facing seconds arg. Returns seconds as float."""
    return float(s) if s else default


# Characters that signal a CSS selector, not plain text.
_CSS_CHARS = set('.#[:>~+')


def _is_css_selector(arg: str) -> bool:
    """Return True if arg looks like a CSS selector, False if it's plain text."""
    return bool(arg) and any(c in arg for c in _CSS_CHARS)


def _classify_wait_arg(arg: str) -> str:
    """Classify a wait argument as 'seconds', 'selector', or 'ambiguous'.

    - Starts with . # [ or contains > : ~ + → 'selector'
    - Parses as float → 'seconds'
    - Otherwise → 'ambiguous'
    """
    if not arg:
        return 'ambiguous'
    # Float check first for leading-dot numbers like .5 (= 0.5 seconds)
    try:
        float(arg)
        return 'seconds'
    except ValueError:
        pass
    # CSS indicators: starts with selector-start chars, or contains combinator/pseudo chars
    if arg[0] in '.#[:' or any(c in arg for c in '>~+'):
        return 'selector'
    return 'ambiguous'


# Verbs where a failure should auto-snapshot to show what's on the page.
# These are interaction verbs that target selectors — if the selector doesn't
# match, showing available elements saves a round-trip.
_SNAPSHOT_ON_FAIL_VERBS = {
    'click', 'click-text', 'type', 'fill', 'select', 'hover', 'tap',
}


def _build_capture_summary(requests: list[dict]) -> dict:
    """Build a summary of captured network requests for step NDJSON."""
    by_type: dict[str, int] = {}
    domains: set[str] = set()
    errors: list[dict] = []

    for r in requests:
        rt = r.get('resource_type', 'Other')
        by_type[rt] = by_type.get(rt, 0) + 1

        url = r.get('url', '')
        if '://' in url:
            domain = url.split('://')[1].split('/')[0].split(':')[0]
            domains.add(domain)

        status = r.get('status')
        if status is not None and (status < 200 or status >= 300):
            errors.append({'url': url, 'status': status})
        elif r.get('failed'):
            errors.append({'url': url, 'error': r.get('error_text', 'unknown')})

    summary = {
        'requests': len(requests),
        'by_type': by_type,
        'domains': sorted(domains),
    }
    if errors:
        summary['errors'] = errors
    return summary


def _write_capture_jsonl(path: str, requests: list[dict],
                         tab_info: dict | None = None) -> int:
    """Write captured requests to JSONL in shared schema format.

    Transforms CDPClient's internal format to the shared schema
    matching log_daemon.py output. Field mapping:
      requestId → id, content_type → mime, encoded_data_length → size.
    Timestamp derived from CDP wallTime when available.
    """
    from datetime import datetime, timezone

    with open(path, 'w') as f:
        for r in requests:
            wall_time = r.get('wall_time')
            if wall_time:
                ts = datetime.fromtimestamp(
                    wall_time, tz=timezone.utc).isoformat()
            else:
                ts = datetime.now(timezone.utc).isoformat()

            record = {
                'id': r.get('requestId', ''),
                'ts': ts,
                'method': r.get('method'),
                'url': r.get('url'),
            }
            if r.get('status') is not None:
                record['status'] = r['status']
            if r.get('content_type'):
                record['mime'] = r['content_type']
            if r.get('resource_type'):
                record['resource_type'] = r['resource_type']
            if r.get('encoded_data_length') is not None:
                record['size'] = r['encoded_data_length']
            if r.get('timing_ms') is not None:
                record['timing_ms'] = r['timing_ms']
            if tab_info:
                record['tab'] = tab_info
            if r.get('request_headers'):
                record['request_headers'] = r['request_headers']
            if r.get('response_headers'):
                record['response_headers'] = r['response_headers']
            if r.get('request_body'):
                record['request_body'] = r['request_body']
            # Response body from --bodies flag
            if r.get('body'):
                record['response_body'] = r['body']

            f.write(json.dumps(record, default=str) + '\n')
    return os.path.getsize(path)


async def run_script(client: CDPClient, steps: list[tuple[str, list[str]]]) -> dict:
    """Execute parsed script steps. Returns summary dict."""
    total_t0 = time.monotonic()
    files = []
    ok = True
    failed_at = None
    fail_verb = None
    fail_error = None
    capture_path = None  # set by 'capture' verb
    capture_bodies = False  # --bodies flag on capture verb

    prev_verb = None

    for i, (verb, args) in enumerate(steps):
        if verb not in KNOWN_VERBS:
            if verb in VERB_SUGGESTIONS:
                correct, hint = VERB_SUGGESTIONS[verb]
                fail_error = f'Unknown verb "{verb}" — did you mean "{correct}"?'
                if hint:
                    fail_error += f' ({hint})'
            else:
                fail_error = f'Unknown verb: {verb}'
            ok = False
            failed_at = i
            fail_verb = verb
            step_info = {'i': i, 'verb': verb, 'error': fail_error}
            print(json.dumps(step_info), file=sys.stderr)
            break

        t0 = time.monotonic()
        step_info = {'i': i, 'verb': verb}

        try:
            if verb == 'goto':
                nav = await do_navigate(client, args[0])
                step_info['url'] = nav['url']
                if nav['status_code'] is not None:
                    step_info['status_code'] = nav['status_code']
            elif verb in ('click', 'click-text'):
                if verb == 'click-text' or not _is_css_selector(args[0]):
                    await do_click_text(client, args[0])
                else:
                    await do_click(client, args[0])
            elif verb == 'fill':
                await do_fill(client, args[0], args[1])
            elif verb == 'type':
                await do_type(client, args[0], args[1])
            elif verb == 'select':
                await do_select(client, args[0], args[1])
            elif verb == 'press':
                await do_press(client, args[0])
            elif verb == 'hover':
                await do_hover(client, args[0])
            elif verb == 'tap':
                await do_tap(client, args[0])
            elif verb == 'swipe':
                dist = int(args[2]) if len(args) > 2 else 200
                swipe_result = await do_swipe(client, args[0], args[1], dist)
                step_info['start'] = [swipe_result['startX'], swipe_result['startY']]
                step_info['end'] = [swipe_result['endX'], swipe_result['endY']]
            elif verb == 'scroll':
                if args and args[0].lower() in SCROLL_DIRECTIONS:
                    direction = args[0].lower()
                    dist = args[1] if len(args) > 1 else '500'
                    coords = {'up': f'0 -{dist}', 'down': f'0 {dist}',
                              'left': f'-{dist} 0', 'right': f'{dist} 0'}
                    raise RuntimeError(
                        f'scroll uses coordinates: scroll {coords[direction]} '
                        f'(not "scroll {direction} {dist}")')
                await do_scroll(client, int(args[0]), int(args[1]))
            elif verb == 'screenshot':
                path, ss_fmt, ss_quality, viewport_only, ss_optimize = (
                    parse_screenshot_flags(args))
                if (prev_verb == 'scroll' and not viewport_only
                        and os.environ.get('PASSE_HINTS', '1') != '0'):
                    print(
                        '[screenshot] hint: screenshot is full-page by default'
                        ' (max 16384px) — scroll before screenshot is usually'
                        ' unnecessary', file=sys.stderr,
                    )
                info = await do_screenshot(
                    client, path, viewport_only=viewport_only,
                    fmt=ss_fmt, quality=ss_quality, optimize_speed=ss_optimize,
                )
                step_info['file'] = info['file']
                step_info['kb'] = info['kb']
                step_info['format'] = info['format']
                step_info['breakdown'] = info['breakdown']
                files.append({'path': info['file'], 'verb': 'screenshot',
                              'format': info['format'], 'kb': info['kb']})
            elif verb == 'snapshot':
                path = args[0] if args else None
                text = await do_snapshot(client, path)
                if path:
                    element_count = len(text.strip().splitlines()) if text.strip() else 0
                    files.append({'path': path, 'verb': 'snapshot',
                                  'element_count': element_count})
                else:
                    step_info['result'] = text[:200]
            elif verb in ('read', 'extract'):
                read_args = list(args)
                force_source = None
                no_wait = '--no-wait' in read_args
                if no_wait:
                    read_args.remove('--no-wait')
                if '--source' in read_args:
                    idx = read_args.index('--source')
                    if idx + 1 < len(read_args):
                        force_source = read_args[idx + 1]
                        del read_args[idx:idx + 2]
                    else:
                        del read_args[idx]
                # Auto-wait: if previous verb was navigation, wait for DOM stability
                if not no_wait and prev_verb in NAV_VERBS:
                    t_wait = time.monotonic()
                    stable = await do_wait_stable(client)
                    wait_ms = round((time.monotonic() - t_wait) * 1000, 1)
                    step_info['auto_wait_ms'] = wait_ms
                    if not stable:
                        step_info['auto_wait_timed_out'] = True
                    print(f'[{verb}] auto-wait: {wait_ms}ms', file=sys.stderr)
                path = read_args[0] if read_args else None
                read_result = await do_read(client, path, force_source=force_source)
                md = read_result.get('markdown', '')
                word_count = len(md.split()) if md else 0
                if path:
                    file_entry = {'path': path, 'verb': verb,
                                  'source': read_result.get('source'),
                                  'word_count': word_count}
                    if read_result.get('content_type'):
                        file_entry['content_type'] = read_result['content_type']
                    files.append(file_entry)
                elif word_count <= CONTENT_INLINE_THRESHOLD:
                    step_info['content'] = md
                    step_info['word_count'] = word_count
                else:
                    step_info['result'] = md[:200]
                if read_result.get('warning'):
                    step_info['warning'] = read_result['warning']
                if read_result.get('source'):
                    step_info['source'] = read_result['source']
                if read_result.get('content_type'):
                    step_info['content_type'] = read_result['content_type']
                if read_result.get('thin_read'):
                    step_info['thin_read'] = read_result['thin_read']
                if read_result.get('title'):
                    step_info['title'] = read_result['title']
            elif verb == 'fetch':
                fetch_args = list(args)
                force_source = None
                if '--source' in fetch_args:
                    idx = fetch_args.index('--source')
                    if idx + 1 < len(fetch_args):
                        force_source = fetch_args[idx + 1]
                        del fetch_args[idx:idx + 2]
                    else:
                        del fetch_args[idx]
                url = fetch_args[0]
                explicit_path = fetch_args[1] if len(fetch_args) > 1 else None
                read_result = await do_fetch(
                    client, url, explicit_path, force_source=force_source)
                md = read_result.get('markdown', '')
                word_count, resolved_path = resolve_fetch_output(
                    md, explicit_path)
                if resolved_path is None:
                    step_info['content'] = md
                    step_info['word_count'] = word_count
                else:
                    file_entry = {'path': resolved_path, 'verb': 'fetch',
                                  'source': read_result.get('source'),
                                  'word_count': word_count}
                    if read_result.get('content_type'):
                        file_entry['content_type'] = read_result['content_type']
                    files.append(file_entry)
                    step_info['file'] = resolved_path
                step_info['url'] = read_result.get('nav_url')
                if read_result.get('nav_status_code') is not None:
                    step_info['status_code'] = read_result['nav_status_code']
                step_info['nav_ms'] = read_result.get('nav_ms')
                step_info['wait_ms'] = read_result.get('wait_ms')
                step_info['read_ms'] = read_result.get('read_ms')
                if read_result.get('timed_out'):
                    step_info['auto_wait_timed_out'] = True
                if read_result.get('warning'):
                    step_info['warning'] = read_result['warning']
                if read_result.get('source'):
                    step_info['source'] = read_result['source']
                if read_result.get('content_type'):
                    step_info['content_type'] = read_result['content_type']
                if read_result.get('thin_read'):
                    step_info['thin_read'] = read_result['thin_read']
                if read_result.get('title'):
                    step_info['title'] = read_result['title']
            elif verb == 'viewport':
                await do_viewport(client, int(args[0]), int(args[1]))
            elif verb == 'device':
                dev_args = list(args)
                dpr_override = None
                if '--dpr' in dev_args:
                    idx = dev_args.index('--dpr')
                    if idx + 1 < len(dev_args):
                        dpr_override = float(dev_args[idx + 1])
                        del dev_args[idx:idx + 2]
                await do_device(client, dev_args[0], dpr_override=dpr_override)
            elif verb == 'watch':
                # watch is a blocking verb — runs until killed. Must be last.
                w_args = list(args)
                w_fast = '--fast' in w_args
                w_args = [a for a in w_args if a != '--fast']
                w_cooldown_ms = 1000
                if '--cooldown' in w_args:
                    idx = w_args.index('--cooldown')
                    if idx + 1 < len(w_args):
                        w_cooldown_ms = int(float(w_args[idx + 1]) * 1000)
                        del w_args[idx:idx + 2]
                w_path = w_args[0] if w_args else '/tmp/passe-watch.jpg'
                await do_watch(client, w_path, fast=w_fast, cooldown_ms=w_cooldown_ms)
                # do_watch only returns on cancellation — skip remaining steps
                break
            elif verb in ('wait', 'wait-for', 'wait-idle'):
                if verb == 'wait-for':
                    # Explicit alias: wait-for <selector> [timeout]
                    timeout = _parse_timeout(
                        args[1] if len(args) > 1 else '', 10)
                    await do_wait_for(client, args[0], timeout)
                elif verb == 'wait-idle':
                    # Explicit alias: wait-idle [timeout]
                    timeout = _parse_timeout(args[0] if args else '', 30)
                    idle_result = await do_wait_idle(client, timeout=timeout)
                    step_info['settled_after_ms'] = idle_result['settled_after_ms']
                    if idle_result['timed_out']:
                        step_info['timed_out'] = True
                        print(f'[wait] network idle timed out after '
                              f'{timeout}s', file=sys.stderr)
                elif not args:
                    # Bare wait → network idle (default 30s)
                    idle_result = await do_wait_idle(client, timeout=30)
                    step_info['settled_after_ms'] = idle_result['settled_after_ms']
                    if idle_result['timed_out']:
                        step_info['timed_out'] = True
                        print('[wait] network idle timed out after 30s',
                              file=sys.stderr)
                else:
                    kind = _classify_wait_arg(args[0])
                    if kind == 'seconds':
                        secs = float(args[0])
                        if secs >= 30:
                            print(f'[wait] {secs}s is a long wait — did you '
                                  f'mean seconds? (wait 0.5 = 500ms)',
                                  file=sys.stderr)
                        await asyncio.sleep(secs)
                    elif kind == 'selector':
                        timeout = _parse_timeout(
                            args[1] if len(args) > 1 else '', 10)
                        await do_wait_for(client, args[0], timeout)
                    else:
                        raise ValueError(
                            f'Ambiguous wait argument: {args[0]!r} — '
                            f'use a number for seconds (wait 3), '
                            f'a CSS selector (wait .results), '
                            f'or bare wait for network idle'
                        )
            elif verb == 'back':
                step_info['url'] = await do_back(client)
            elif verb == 'forward':
                step_info['url'] = await do_forward(client)
            elif verb == 'eval':
                result = await do_eval(client, args[0])
                step_info['result'] = str(result)
            elif verb == 'eval-to':
                await do_eval_to(client, args[0], args[1])
                files.append({'path': args[0], 'verb': 'eval-to',
                              'byte_size': os.path.getsize(args[0])})
            elif verb == 'eval-file':
                result = await do_eval_file(client, args[0])
                step_info['result'] = str(result)[:200]
            elif verb == 'eval-file-to':
                await do_eval_file_to(client, args[0], args[1])
                files.append({'path': args[0], 'verb': 'eval-file-to',
                              'byte_size': os.path.getsize(args[0])})
            elif verb == 'assert':
                await do_assert(client, args[0])
            elif verb == 'log':
                print(f'[log] {args[0]}', file=sys.stderr)
            elif verb == 'frame':
                timeout = float(args[1]) if len(args) > 1 else 10.0
                await do_frame(client, args[0], timeout=timeout)
                if args[0].lower() == 'top':
                    step_info['target'] = 'top'
                else:
                    step_info['frame_url'] = args[0]
            elif verb == 'ax-tree':
                tree_args = list(args)
                depth = None
                if '--depth' in tree_args:
                    idx = tree_args.index('--depth')
                    if idx + 1 < len(tree_args):
                        depth = int(tree_args[idx + 1])
                        del tree_args[idx:idx + 2]
                text = await do_ax_tree(client, depth=depth)
                word_count = len(text.split())
                if word_count <= CONTENT_INLINE_THRESHOLD:
                    step_info['content'] = text
                else:
                    step_info['result'] = text[:200]
                step_info['node_count'] = text.count('"role"')
            elif verb == 'ax-find':
                find_args = list(args)
                role = name_filter = None
                if '--role' in find_args:
                    idx = find_args.index('--role')
                    if idx + 1 < len(find_args):
                        role = find_args[idx + 1]
                        del find_args[idx:idx + 2]
                if '--name' in find_args:
                    idx = find_args.index('--name')
                    if idx + 1 < len(find_args):
                        name_filter = find_args[idx + 1]
                        del find_args[idx:idx + 2]
                # Positional: ax-find ROLE or ax-find ROLE NAME
                if not role and find_args:
                    role = find_args.pop(0)
                if not name_filter and find_args:
                    name_filter = find_args.pop(0)
                text = await do_ax_find(client, role=role, name=name_filter)
                step_info['content'] = text
                step_info['match_count'] = text.count('"role"')
            elif verb == 'ax-node':
                selector = args[0] if args else 'body'
                text = await do_ax_node(client, selector)
                step_info['content'] = text
            elif verb == 'bring-to-front':
                await client.send('Page.bringToFront')
            elif verb == 'capture':
                if i > 0:
                    print('[capture] Warning: capture is not the first verb — '
                          'network requests from earlier steps were not recorded. '
                          'Place capture at the start of your script.',
                          file=sys.stderr)
                cap_args = list(args)
                if '--bodies' in cap_args:
                    capture_bodies = True
                    cap_args.remove('--bodies')
                if not cap_args:
                    raise RuntimeError('capture requires an output path')
                capture_path = cap_args[0]
                await client.enable_network(large_buffers=capture_bodies)

            step_info['ms'] = round((time.monotonic() - t0) * 1000, 1)
            prev_verb = verb

        except Exception as e:
            step_info['ms'] = round((time.monotonic() - t0) * 1000, 1)
            step_info['error'] = str(e)
            ok = False
            failed_at = i
            fail_verb = verb
            fail_error = str(e)
            # Self-healing: snapshot on interaction verb failure
            if verb in _SNAPSHOT_ON_FAIL_VERBS:
                try:
                    snap_text = await do_snapshot(client, limit=10)
                    lines = snap_text.strip().splitlines()[:10]
                    if lines:
                        step_info['elements'] = lines
                        compact = '; '.join(
                            ln.split(' css=')[0].lstrip('[0123456789] ')
                            for ln in lines
                        )
                        print(
                            f'[passe] {verb} failed: {e}\n'
                            f'[passe] Page has: {compact}',
                            file=sys.stderr,
                        )
                except Exception:
                    pass  # Never let recovery crash the error path
            print(json.dumps(step_info), file=sys.stderr)
            break

        print(json.dumps(step_info), file=sys.stderr)

    # Finalize network capture — write JSONL and emit summary step
    if capture_path is not None:
        requests = client.get_network_requests()
        # Build tab info for JSONL output
        tab_info = None
        if client._target_id:
            tab_url = None
            try:
                tab_url = await do_eval(client, 'window.location.href')
            except Exception:
                pass
            tab_info = {'id': client._target_id, 'url': tab_url or ''}
        # Fetch response bodies if --bodies was set
        if capture_bodies:
            total_body_bytes = 0
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
                    r['body_size'] = len(base64.b64decode(body)) if is_base64 else len(body)
                    total_body_bytes += r['body_size']
                except Exception:
                    pass  # Body may not be available (e.g. streamed, evicted)
        _write_capture_jsonl(capture_path, requests, tab_info=tab_info)
        cap_summary = _build_capture_summary(requests)
        if capture_bodies:
            cap_summary['body_bytes'] = total_body_bytes
        file_entry = {'path': capture_path, 'verb': 'capture'}
        file_entry.update(cap_summary)
        files.append(file_entry)
        cap_step = {'verb': 'capture', 'file': capture_path}
        cap_step.update(cap_summary)
        print(json.dumps(cap_step), file=sys.stderr)

    total_ms = round((time.monotonic() - total_t0) * 1000, 1)
    summary = {
        'ok': ok,
        'steps': (failed_at + 1) if failed_at is not None else len(steps),
        'total_ms': total_ms,
    }
    if files:
        summary['files'] = files
    if not ok:
        summary['failed_at'] = failed_at
        summary['verb'] = fail_verb
        summary['error'] = fail_error

    # Capture final URL (post-redirect) before the tab is closed.
    # Best effort — don't fail the run for this.
    try:
        summary['final_url'] = await do_eval(client, 'window.location.href')
    except Exception:
        pass

    return summary

