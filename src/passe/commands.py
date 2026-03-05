"""CLI subcommands — run, screenshot, eval, devices."""

import json
import sys

from passe.connection import connect
from passe.parser import parse_script, split_inline
from passe.runner import run_script
from passe.verbs import do_device, do_eval, do_screenshot


def _emit_fetch_hint(steps):
    """Emit stderr hint when goto+read (or goto+wait+read) detected.

    Fires once per script — suggests the fetch compound verb.
    """
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
        if j < len(steps) and steps[j][0] == 'read':
            if not hinted_fetch:
                print('[passe] hint: fetch URL [path] combines '
                      'goto+wait+read in one step', file=sys.stderr)
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


async def cmd_run(source: str, inline: str = None,
                  keep_tab: bool = False, reuse_tab: bool = False,
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
            await client.create_tab()
        await client.send('Page.enable')
        # Apply device preset before script if --device flag used
        if device:
            await do_device(client, device, dpr_override=dpr)
        try:
            summary = await run_script(client, steps)
            summary['cdp'] = conn_info['cdp']
            summary['browser'] = conn_info['browser']
            print(json.dumps(summary))
            sys.exit(0 if summary['ok'] else 1)
        finally:
            if not keep_tab:
                await client.close_tab()


async def cmd_screenshot(args: list[str], device: str = None, dpr: float = None):
    """Atomic screenshot of current page. Parses --fast, --viewport, --format, --quality."""
    fast = '--fast' in args
    viewport_only = '--viewport' in args
    args = [a for a in args if a not in ('--fast', '--viewport')]
    fmt = 'png'
    quality = None
    optimize = False
    if '--format' in args:
        idx = args.index('--format')
        if idx + 1 < len(args):
            fmt = args[idx + 1]
            del args[idx:idx + 2]
    if '--quality' in args:
        idx = args.index('--quality')
        if idx + 1 < len(args):
            quality = int(args[idx + 1])
            del args[idx:idx + 2]
    if fast:
        fmt = 'jpeg'
        quality = quality or 70
        optimize = True
        viewport_only = True
    output = args[0] if args else None
    async with connect() as (client, conn_info):
        await client.attach_to_first_page()
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
