"""CLI subcommands — run, screenshot, eval, devices."""

import json
import sys

from passe.connection import connect
from passe.parser import parse_script, split_inline
from passe.runner import run_script
from passe.verbs import do_device, do_eval, do_screenshot


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
