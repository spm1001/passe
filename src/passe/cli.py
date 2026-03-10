"""
Passe — fast CDP browser automation via line DSL.

The kitchen pass: inspect everything before it goes out.

Commands:
  passe run -c 'goto URL; screenshot /tmp/out.png'
  passe run script.passe
  passe run - <<'EOF'
  passe screenshot <output.png>
  passe eval <expression>
"""

import asyncio
import os
import sys

from passe.connection import set_cdp_override
from passe.commands import (cmd_run, cmd_fetch, cmd_look, cmd_check, cmd_capture,
                            cmd_explain, cmd_screenshot, cmd_eval, cmd_devices)

# ── Re-exports for backward compatibility ─────────────────
# Tests and external code import these from passe.cli.
# Keep until all consumers migrate to the new module paths.
from passe.client import CDPClient  # noqa: F401
from passe.connection import connect, _find_chrome  # noqa: F401
from passe.parser import (  # noqa: F401
    KNOWN_VERBS, NAV_VERBS, RAW_REST_VERBS, RAW_REST_AFTER_PATH_VERBS,
    parse_script, split_inline,
)
from passe.verbs import (  # noqa: F401
    do_navigate, do_back, do_forward, do_wait_idle,
    do_click, do_click_text, do_click_if, do_fill, do_type, do_select,
    do_press, do_hover, do_tap, do_swipe, do_scroll,
    do_screenshot, do_snapshot, do_read, do_fetch,
    do_device, do_viewport, do_wait_for, do_wait_navigation, do_wait_stable,
    do_eval, do_eval_to, do_eval_file, do_eval_file_to,
    do_assert, do_watch, _check_thin_read,
)
from passe.runner import run_script, _build_capture_summary, _write_capture_jsonl  # noqa: F401


def _extract_flag(args: list[str], flag: str) -> tuple[str | None, list[str]]:
    """Extract --flag value from args, return (value, remaining_args).

    Raises SystemExit if flag is present but has no value.
    """
    if flag in args:
        idx = args.index(flag)
        if idx + 1 < len(args):
            val = args[idx + 1]
            return val, args[:idx] + args[idx + 2:]
        print(f'{flag} requires an argument', file=sys.stderr)
        sys.exit(1)
    return None, args


# ── Entry point ───────────────────────────────────────────

USAGE = """\
passe — fast CDP browser automation

Commands:
  passe run -c 'verbs...'         Run inline script
  passe run script.passe          Run script file
  passe run - <<'EOF' ... EOF     Run from stdin
  passe look <url> [path]          Goto + fast screenshot (see the page)
  passe check <url> --contains T  Goto + assert text present (deploy verification)
  passe capture <url> [flags] <path> Goto + wait + record network requests
  passe fetch <url> [flags] [path] Fetch and extract page content
  passe screenshot [flags] <out>  Screenshot current page
  passe eval <expression>         Eval JS on current page
  passe explain -c 'verbs...'     Dry-run: validate script without executing
  passe devices                   List available device presets

Global flags:
  --cdp <url>       CDP endpoint (default: PASSE_CDP env or http://localhost:9222)
  --device <name>   Device emulation preset (e.g. "iPhone 14 Pro")
  --dpr <n>         Override device pixel ratio

Run flags:
  --keep-tab        Keep tab open after script
  --reuse-tab       Attach to existing visible tab (implies --keep-tab)
  --flash [secs]    Keep tab, auto-close after idle timeout (default 30s)
  --no-keep-on-fail Close tab even when script fails (default: keep on failure)
  --foreground      Create tab in foreground (visible to human). For jsaction sites, OAuth flows.
  --quiet           Suppress stderr hints (same as PASSE_HINTS=0)

Screenshot flags:
  --fast            JPEG q70, viewport-only, optimizeForSpeed
  --no-fast         Override PASSE_SCREENSHOT_FAST env var
  --viewport        Viewport only (default is full-page)
  --format <fmt>    png, jpeg, or webp (default: png)
  --quality <n>     0-100, for jpeg/webp

Environment:
  PASSE_CDP               CDP endpoint (default http://localhost:9222)
  PASSE_SCREENSHOT_FAST   Default to --fast for all screenshots
  PASSE_HINTS             Set to 0 to suppress stderr hints

Use 'passe run --help' for the verb reference.
"""

RUN_HELP = """\
passe run — DSL verb reference

Navigation:
  goto <url>                Navigate and wait for load
  back / forward            Browser history

Interaction:
  click <selector>          CSS selector click
  click-text <"label">      Find by visible text, click
  click-if <selector>       Click if exists, silently skip if not
  type <selector> <text>    Character-by-character input (works with React)
  fill <selector> <value>   Set value directly (plain HTML forms only)
  select <selector> <value> Dropdown selection
  press <key>               Keypress (Enter, Tab, Escape, etc.)
  hover <selector>          Mouseover event
  tap <selector>            Touch event (touchStart + touchEnd) for mobile UI
  swipe <sel> <dir> [dist]  Swipe gesture (left/right/up/down, default 200px)

Observation:
  screenshot [flags] [path] Full-page by default (entire document, max 16384px — no need to scroll).
                            --viewport for visible area only. Flags: --fast, --viewport, --format, --quality
  snapshot [path]           List interactive elements with CSS selectors
  read [flags] [path]       Extract page content as markdown (flags: --source, --no-wait)
  fetch <url> [flags] [path] goto + auto-wait + read in one step (flags: --source)
  eval <expression>         Run JS, result to stdout
  eval-to <path> <expr>     Run JS, write result to file
  eval-file <js-path>       Run JS from file
  eval-file-to <out> <js>   Run JS from file, write to file

Network:
  capture [--bodies] <path> Record all network requests to JSONL file

Emulation:
  device <"name"> [--dpr N] Apply device preset (iPhone 14 Pro, Pixel 7, etc.)
  viewport <w> <h>          Set raw viewport dimensions

Control:
  wait <seconds>            Sleep (decimal ok: wait 0.5 = 500ms)
  wait-for <sel> [seconds]  Wait for selector (default 10)
  wait-idle [seconds]       Wait for network to settle (default 30)
  wait-navigation           Wait for page load event
  watch [flags] <path>      Auto-screenshot on HMR/DOM changes. --fast, --cooldown <ms> (default 1000)
  bring-to-front            Make tab visible (required for jsaction sites like Google Groups)
  assert <expression>       Fail script if JS expression is falsy
  log <message>             Print to stderr

Rarely needed:
  scroll <x> <y>            Position viewport (for lazy-load triggers or --viewport shots).
                            Most verbs work regardless of scroll position.
"""


def _run(coro):
    """Run an async command, catching unexpected exceptions as one-line errors."""
    try:
        asyncio.run(coro)
    except KeyboardInterrupt:
        sys.exit(130)
    except SystemExit:
        raise
    except Exception as exc:
        print(f'passe: {exc}', file=sys.stderr)
        sys.exit(1)


def main():
    if len(sys.argv) < 2:
        print(USAGE, file=sys.stderr)
        sys.exit(1)

    # Global flags: extract before subcommand processing
    all_args = sys.argv[1:]

    cdp_url, all_args = _extract_flag(all_args, '--cdp')
    if cdp_url:
        set_cdp_override(cdp_url)
    device_name, all_args = _extract_flag(all_args, '--device')
    dpr_str, all_args = _extract_flag(all_args, '--dpr')
    dpr_val = float(dpr_str) if dpr_str else None

    # Re-derive cmd after extracting global flags
    if not all_args:
        print(USAGE, file=sys.stderr)
        sys.exit(1)
    cmd = all_args[0]

    if cmd in ('--help', '-h'):
        print(USAGE)
        sys.exit(0)
    elif cmd in ('--version', '-V'):
        from importlib.metadata import version
        print(f"passe {version('passe')}")
        sys.exit(0)
    elif cmd == 'run':
        # Extract flags before positional args
        run_args = all_args[1:]
        if '--help' in run_args or '-h' in run_args:
            print(RUN_HELP)
            sys.exit(0)
        keep_tab = '--keep-tab' in run_args
        reuse_tab = '--reuse-tab' in run_args
        no_keep_on_fail = '--no-keep-on-fail' in run_args
        foreground = '--foreground' in run_args
        quiet = '--quiet' in run_args or '-q' in run_args
        if quiet:
            os.environ['PASSE_HINTS'] = '0'
        # --flash [seconds]: keep tab then auto-close. Bare --flash = 30s.
        flash_val = None
        if '--flash' in run_args:
            idx = run_args.index('--flash')
            # Peek at next arg — if it's a number, consume it as timeout
            if idx + 1 < len(run_args) and run_args[idx + 1].isdigit():
                flash_val = int(run_args[idx + 1])
                run_args = run_args[:idx] + run_args[idx + 2:]
            else:
                flash_val = 30
                run_args = run_args[:idx] + run_args[idx + 1:]
            keep_tab = True  # --flash implies --keep-tab
        run_args = [a for a in run_args
                    if a not in ('--keep-tab', '--reuse-tab',
                                 '--no-keep-on-fail', '--foreground',
                                 '--quiet', '-q')]

        if len(run_args) >= 2 and run_args[0] == '-c':
            # passe run [-flags] -c 'inline script'
            _run(cmd_run(None, inline=' '.join(run_args[1:]),
                                keep_tab=keep_tab, reuse_tab=reuse_tab,
                                keep_on_fail=not no_keep_on_fail,
                                flash=flash_val, foreground=foreground,
                                device=device_name, dpr=dpr_val))
        elif len(run_args) == 1:
            # passe run [-flags] script.passe  OR  passe run [-flags] -
            _run(cmd_run(run_args[0],
                                keep_tab=keep_tab, reuse_tab=reuse_tab,
                                keep_on_fail=not no_keep_on_fail,
                                flash=flash_val, foreground=foreground,
                                device=device_name, dpr=dpr_val))
        else:
            print(USAGE, file=sys.stderr)
            sys.exit(1)
    elif cmd == 'look' and len(all_args) >= 2:
        look_args = all_args[1:]
        url = look_args[0]
        path = look_args[1] if len(look_args) > 1 else None
        _run(cmd_look(url, path=path, device=device_name, dpr=dpr_val))
    elif cmd == 'check' and len(all_args) >= 2:
        check_args = all_args[1:]
        # Extract --contains TEXT
        contains_val, check_args = _extract_flag(check_args, '--contains')
        if not contains_val:
            print('passe check requires --contains TEXT', file=sys.stderr)
            sys.exit(1)
        # Extract optional --screenshot path
        shot_path, check_args = _extract_flag(check_args, '--screenshot')
        url = check_args[0] if check_args else None
        if not url:
            print('passe check requires a URL', file=sys.stderr)
            sys.exit(1)
        _run(cmd_check(url, contains=contains_val, screenshot_path=shot_path,
                        device=device_name, dpr=dpr_val))
    elif cmd == 'capture' and len(all_args) >= 2:
        cap_args = all_args[1:]
        bodies = '--bodies' in cap_args
        cap_args = [a for a in cap_args if a != '--bodies']
        url = cap_args[0] if len(cap_args) >= 1 else None
        path = cap_args[1] if len(cap_args) >= 2 else None
        if not url or not path:
            print('passe capture requires URL and output path', file=sys.stderr)
            sys.exit(1)
        _run(cmd_capture(url, path=path, bodies=bodies,
                         device=device_name, dpr=dpr_val))
    elif cmd == 'fetch' and len(all_args) >= 2:
        fetch_args = all_args[1:]
        source_val, fetch_args = _extract_flag(fetch_args, '--source')
        url = fetch_args[0]
        path = fetch_args[1] if len(fetch_args) > 1 else None
        _run(cmd_fetch(url, path=path, source=source_val,
                       device=device_name, dpr=dpr_val))
    elif cmd == 'explain':
        explain_args = all_args[1:]
        if len(explain_args) >= 2 and explain_args[0] == '-c':
            cmd_explain(None, inline=' '.join(explain_args[1:]))
        elif len(explain_args) == 1:
            cmd_explain(explain_args[0])
        else:
            print('Usage: passe explain -c "script" | passe explain file.passe | passe explain -',
                  file=sys.stderr)
            sys.exit(1)
    elif cmd == 'screenshot' and len(all_args) >= 2:
        _run(cmd_screenshot(all_args[1:], device=device_name, dpr=dpr_val))
    elif cmd == 'eval' and len(all_args) >= 2:
        _run(cmd_eval(' '.join(all_args[1:])))
    elif cmd == 'devices':
        cmd_devices()
    else:
        print(USAGE, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
