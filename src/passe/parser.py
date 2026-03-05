"""Script parsing for the passe DSL."""

import shlex


KNOWN_VERBS = {
    'goto', 'click', 'click-text', 'click-if', 'fill', 'type', 'select',
    'press', 'hover', 'tap', 'swipe', 'scroll', 'screenshot', 'snapshot', 'read', 'fetch',
    'capture', 'viewport', 'device', 'watch', 'wait', 'wait-for', 'wait-idle', 'wait-navigation',
    'back', 'forward', 'eval', 'eval-to', 'eval-file', 'eval-file-to',
    'assert', 'log',
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
    'capture': ('capture', None),  # already valid, but 'screenshot' alias below
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
