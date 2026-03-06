"""Script parsing for the passe DSL."""

import shlex

# Content shorter than this (in words) is inlined in JSON output
# rather than written to a file. Used by both cmd_fetch and run_script.
CONTENT_INLINE_THRESHOLD = 2000


KNOWN_VERBS = {
    'goto', 'click', 'click-text', 'click-if', 'fill', 'type', 'select',
    'press', 'hover', 'tap', 'swipe', 'scroll', 'screenshot', 'snapshot', 'read', 'fetch',
    'capture', 'viewport', 'device', 'watch', 'wait', 'wait-for', 'wait-idle', 'wait-navigation',
    'back', 'forward', 'eval', 'eval-to', 'eval-file', 'eval-file-to',
    'assert', 'log', 'bring-to-front',
}

# Verbs that trigger auto-wait in the next read/fetch step.
# Keep near KNOWN_VERBS so new navigation verbs don't get forgotten.
NAV_VERBS = {'goto', 'back', 'forward'}

RAW_REST_VERBS = {'eval', 'assert', 'log'}
RAW_REST_AFTER_PATH_VERBS = {'eval-to'}

# Common mistakes → (correct verb, extra hint or None)
VERB_SUGGESTIONS = {
    'navigate': ('goto', None),
    'browse': ('goto', None),
    'open': ('goto', None),
    'visit': ('goto', None),
    'load': ('goto', None),
    'go': ('goto', None),
    'input': ('type', None),
    'enter': ('press', 'use "press Enter" to submit, or "type" to enter text'),
    'find': ('wait-for', None),
    'sleep': ('wait', None),
    'delay': ('wait', None),
    'pause': ('wait', None),
    'shoot': ('screenshot', None),
    'snap': ('screenshot', None),
    'print': ('screenshot', None),
    'extract': ('read', None),
    'scrape': ('read', None),
    'get': ('read', 'use "goto" to navigate or "read" to extract content'),
    'scroll-down': ('scroll', 'scroll uses coordinates: scroll 0 500'),
    'scroll-up': ('scroll', 'scroll uses coordinates: scroll 0 -500'),
    'scroll-left': ('scroll', 'scroll uses coordinates: scroll -500 0'),
    'scroll-right': ('scroll', 'scroll uses coordinates: scroll 500 0'),
}

# Direction words used as args to scroll (e.g. "scroll down 500")
SCROLL_DIRECTIONS = {'up', 'down', 'left', 'right'}


# Minimum argument counts per verb, derived from run_script dispatch.
# Verbs not listed here accept 0 args.
VERB_MIN_ARGS = {
    'goto': 1, 'click': 1, 'click-text': 1, 'click-if': 1,
    'fill': 2, 'type': 2, 'select': 2,
    'press': 1, 'hover': 1, 'tap': 1, 'swipe': 2,
    'scroll': 2, 'viewport': 2,
    'device': 1, 'fetch': 1,
    'wait': 1, 'wait-for': 1,
    'eval': 1, 'eval-to': 2, 'eval-file': 1, 'eval-file-to': 2,
    'assert': 1, 'log': 1, 'capture': 1,
}


def validate_steps(steps: list[tuple[str, list[str]]]) -> list[dict]:
    """Validate parsed steps without executing. Returns list of error dicts.

    Each error: {'line': int, 'verb': str, 'error': str}
    Line numbers are 1-based step indices.
    """
    import os
    errors = []
    for i, (verb, args) in enumerate(steps):
        line = i + 1
        if verb not in KNOWN_VERBS:
            if verb in VERB_SUGGESTIONS:
                correct, hint = VERB_SUGGESTIONS[verb]
                msg = f'Unknown verb "{verb}" — did you mean "{correct}"?'
                if hint:
                    msg += f' ({hint})'
            else:
                msg = f'Unknown verb: {verb}'
            errors.append({'line': line, 'verb': verb, 'error': msg})
            continue

        min_args = VERB_MIN_ARGS.get(verb, 0)
        if len(args) < min_args:
            errors.append({
                'line': line, 'verb': verb,
                'error': f'{verb} requires at least {min_args} argument(s), got {len(args)}',
            })

        # File existence checks for eval-file variants
        if verb in ('eval-file', 'eval-file-to') and args:
            js_path = args[1] if verb == 'eval-file-to' and len(args) > 1 else args[0]
            if not os.path.isfile(js_path):
                errors.append({
                    'line': line, 'verb': verb,
                    'error': f'File not found: {js_path}',
                })

    return errors


def resolve_fetch_output(markdown: str, explicit_path: str | None):
    """Decide whether fetch content should be inlined or written to a file.

    Returns (word_count, path_or_none).
    - If inlined: path_or_none is None (caller should use markdown directly)
    - If file: path_or_none is the path (explicit or auto-created temp file)

    Lives in parser.py (not commands/runner) because both cmd_fetch and
    run_script's fetch verb need it — parser.py is the shared-logic module
    (also owns CONTENT_INLINE_THRESHOLD).
    """
    import os
    import tempfile
    word_count = len(markdown.split()) if markdown else 0
    if explicit_path is None and word_count <= CONTENT_INLINE_THRESHOLD:
        return word_count, None
    # Write to file
    path = explicit_path
    if path is None:
        fd, path = tempfile.mkstemp(suffix='.md', prefix='passe-fetch-')
        os.close(fd)
        with open(path, 'w') as f:
            f.write(markdown)
    return word_count, path


def parse_screenshot_flags(args: list[str]) -> tuple[str | None, str, int | None, bool, bool]:
    """Parse screenshot flags from an argument list.

    Returns (path, fmt, quality, viewport_only, optimize_speed).
    Handles --fast, --no-fast, --viewport, --format, --quality,
    and the PASSE_SCREENSHOT_FAST env var.
    """
    import os
    remaining = list(args)
    viewport_only = '--viewport' in remaining
    no_fast = '--no-fast' in remaining
    fast = '--fast' in remaining
    if not fast and not no_fast:
        fast = bool(os.environ.get('PASSE_SCREENSHOT_FAST', ''))
    remaining = [a for a in remaining
                 if a not in ('--viewport', '--fast', '--no-fast')]
    fmt = 'png'
    quality = None
    optimize = False
    if '--format' in remaining:
        idx = remaining.index('--format')
        if idx + 1 < len(remaining):
            fmt = remaining[idx + 1]
            del remaining[idx:idx + 2]
    if '--quality' in remaining:
        idx = remaining.index('--quality')
        if idx + 1 < len(remaining):
            quality = int(remaining[idx + 1])
            del remaining[idx:idx + 2]
    if fast:
        fmt = 'jpeg'
        quality = quality or 70
        optimize = True
        viewport_only = True
    path = remaining[0] if remaining else None
    return path, fmt, quality, viewport_only, optimize


def split_inline(text: str) -> str:
    """Split inline -c text on '; ' but only when followed by a known verb.

    Plain replace(';', newline) destroys semicolons inside JS expressions.
    This verb-aware split keeps JS intact:
      'goto URL; eval var x = 1; x'  →  two lines, not three
    """
    parts = text.split('; ')
    if len(parts) <= 1:
        return text

    lines = [parts[0]]
    for part in parts[1:]:
        first_word = part.split(None, 1)[0].lower() if part.strip() else ''
        if first_word in KNOWN_VERBS:
            lines.append(part)
        else:
            # Not a verb — this semicolon was inside an expression, rejoin
            lines[-1] += '; ' + part
    return '\n'.join(lines)


def parse_script(text: str) -> list[tuple[str, list[str]]]:
    """Parse script text into list of (verb, args) tuples."""
    steps = []
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        # Split verb from rest, preserving raw text for expression verbs
        parts = line.split(None, 1)
        if not parts:
            continue
        verb = parts[0].lower()
        rest = parts[1] if len(parts) > 1 else ''

        if verb in RAW_REST_VERBS:
            # eval, assert, log: entire rest is a single raw argument
            args = [rest] if rest else []
        elif verb in RAW_REST_AFTER_PATH_VERBS:
            # eval-to: first arg is path (shlex), rest is raw expression
            sub_parts = rest.split(None, 1)
            if len(sub_parts) >= 2:
                args = [sub_parts[0], sub_parts[1]]
            elif sub_parts:
                args = [sub_parts[0]]
            else:
                args = []
        else:
            # Standard verbs: full shlex parsing
            try:
                all_parts = shlex.split(line)
            except ValueError:
                all_parts = line.split()
            args = all_parts[1:] if len(all_parts) > 1 else []

        steps.append((verb, args))
    return steps
