"""
Query tools for passe network capture JSONL files.

Reads JSONL from daemon logs or one-shot `passe capture` output.
No passe imports — sits parallel to runner.py in the DAG.
"""

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_LOG_DIR = Path.home() / '.passe' / 'logs'
DEFAULT_LOG_PATH = DEFAULT_LOG_DIR / 'requests.jsonl'

# ANSI color codes
_RESET = '\033[0m'
_BOLD = '\033[1m'
_DIM = '\033[2m'
_RED = '\033[31m'
_GREEN = '\033[32m'
_YELLOW = '\033[33m'
_BLUE = '\033[34m'
_MAGENTA = '\033[35m'
_CYAN = '\033[36m'


def _use_color() -> bool:
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()


# ── Reading ────────────────────────────────────────────────


def read_requests(path: str | Path) -> list[dict]:
    """Read all requests from a JSONL file. Skips malformed lines.

    Returns list (newest last) — caller reverses for display.
    Handles both old-format (content_type) and new-format (mime) fields.
    """
    path = Path(path)
    if not path.exists():
        return []

    requests = []
    with open(path) as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                # Normalize old-format fields
                if 'content_type' in entry and 'mime' not in entry:
                    entry['mime'] = entry['content_type']
                if 'requestId' in entry and 'id' not in entry:
                    entry['id'] = entry['requestId']
                if 'encoded_data_length' in entry and 'size' not in entry:
                    entry['size'] = entry['encoded_data_length']
                requests.append(entry)
            except json.JSONDecodeError:
                print(f'[passe log] skipping malformed line {line_num}',
                      file=sys.stderr)
    return requests


def read_requests_with_rotated(log_path: str | Path) -> list[dict]:
    """Read requests from main log and rotated files. Oldest first."""
    log_path = Path(log_path)
    all_requests = []

    # Read rotated files first (oldest to newest: .3, .2, .1)
    for i in range(3, 0, -1):
        rotated = log_path.parent / f'{log_path.name}.{i}'
        if rotated.exists():
            all_requests.extend(read_requests(rotated))

    # Then the active log
    all_requests.extend(read_requests(log_path))
    return all_requests


# ── Filtering ──────────────────────────────────────────────


def filter_requests(
    requests: list[dict],
    url_pattern: str | None = None,
    method: str | None = None,
    status_pattern: str | None = None,
    limit: int | None = None,
) -> list[dict]:
    """Filter requests by URL pattern, method, and status.

    status_pattern supports:
      - Exact code: '404'
      - Class glob: '4xx', '5xx', '2xx'
    """
    filtered = requests

    if url_pattern:
        try:
            pat = re.compile(url_pattern, re.IGNORECASE)
            filtered = [r for r in filtered if pat.search(r.get('url', ''))]
        except re.error:
            # Fall back to simple substring match
            filtered = [r for r in filtered
                        if url_pattern.lower() in r.get('url', '').lower()]

    if method:
        method_upper = method.upper()
        filtered = [r for r in filtered
                    if r.get('method', '').upper() == method_upper]

    if status_pattern:
        filtered = [r for r in filtered
                    if _match_status(r.get('status'), status_pattern)]

    if limit is not None:
        filtered = filtered[-limit:]  # last N (newest if pre-sorted)

    return filtered


def _match_status(status: int | None, pattern: str) -> bool:
    """Match a status code against a pattern like '404' or '4xx'."""
    if status is None:
        return False
    if pattern.endswith('xx'):
        try:
            prefix = int(pattern[0])
            return status // 100 == prefix
        except (ValueError, IndexError):
            return False
    try:
        return status == int(pattern)
    except ValueError:
        return False


# ── Formatting ─────────────────────────────────────────────


def _color_method(method: str) -> str:
    colors = {
        'GET': _GREEN, 'POST': _YELLOW, 'PUT': _BLUE,
        'DELETE': _RED, 'PATCH': _MAGENTA, 'HEAD': _CYAN,
        'OPTIONS': _DIM,
    }
    c = colors.get(method.upper(), '')
    return f'{c}{method:<7}{_RESET}'


def _color_status(status: int | None) -> str:
    if status is None:
        return f'{_DIM}  ---{_RESET}'
    if 200 <= status < 300:
        return f'{_GREEN}{status:>5}{_RESET}'
    elif 300 <= status < 400:
        return f'{_CYAN}{status:>5}{_RESET}'
    elif 400 <= status < 500:
        return f'{_YELLOW}{status:>5}{_RESET}'
    else:
        return f'{_RED}{status:>5}{_RESET}'


def _format_size(size: int | None) -> str:
    if size is None:
        return '     -'
    if size < 1024:
        return f'{size:>5}B'
    elif size < 1024 * 1024:
        return f'{size / 1024:>5.1f}K'
    else:
        return f'{size / (1024 * 1024):>5.1f}M'


def _format_timing(ms: float | None) -> str:
    if ms is None:
        return '     -'
    if ms < 1000:
        return f'{ms:>5.0f}ms'
    else:
        return f'{ms / 1000:>5.1f}s '


def _truncate_url(url: str, max_len: int = 80) -> str:
    if len(url) <= max_len:
        return url
    return url[:max_len - 3] + '...'


def format_request_line(r: dict, color: bool = True) -> str:
    """Format a single request as a one-line summary."""
    method = r.get('method', '???')
    status = r.get('status')
    url = r.get('url', '')
    size = r.get('size') or r.get('encoded_data_length')
    timing = r.get('timing_ms')
    rid = (r.get('id') or r.get('requestId') or '')[:8]

    if color:
        parts = [
            f'{_DIM}{rid}{_RESET}',
            _color_method(method),
            _color_status(status),
            _format_size(size),
            _format_timing(timing),
            _truncate_url(url),
        ]
    else:
        parts = [
            rid,
            f'{method:<7}',
            f'{status or "---":>5}',
            _format_size(size),
            _format_timing(timing),
            url,
        ]
    return '  '.join(parts)


def format_request_detail(r: dict, show_headers: bool = False,
                          show_body: bool = False) -> str:
    """Format full request detail for `passe log show`."""
    lines = []
    rid = r.get('id') or r.get('requestId') or 'unknown'
    method = r.get('method', '???')
    url = r.get('url', '')
    status = r.get('status')
    mime = r.get('mime') or r.get('content_type', '')
    resource_type = r.get('resource_type', '')
    size = r.get('size') or r.get('encoded_data_length')
    timing = r.get('timing_ms')
    ts = r.get('ts', '')
    tab = r.get('tab', {})

    lines.append(f'{method} {url}')
    lines.append(f'  ID:       {rid}')
    if ts:
        lines.append(f'  Time:     {ts}')
    if status is not None:
        lines.append(f'  Status:   {status}')
    if mime:
        lines.append(f'  MIME:     {mime}')
    if resource_type:
        lines.append(f'  Type:     {resource_type}')
    if size is not None:
        lines.append(f'  Size:     {_format_size(size).strip()}')
    if timing is not None:
        lines.append(f'  Timing:   {_format_timing(timing).strip()}')
    if tab:
        tab_url = tab.get('url', '') if isinstance(tab, dict) else str(tab)
        if tab_url:
            lines.append(f'  Tab:      {tab_url}')

    if show_headers:
        req_headers = r.get('request_headers', {})
        if req_headers:
            lines.append('')
            lines.append('  Request Headers:')
            for k, v in sorted(req_headers.items()):
                lines.append(f'    {k}: {v}')

        resp_headers = r.get('response_headers', {})
        if resp_headers:
            lines.append('')
            lines.append('  Response Headers:')
            for k, v in sorted(resp_headers.items()):
                lines.append(f'    {k}: {v}')

    if show_body:
        req_body = r.get('request_body') or r.get('requestBody')
        if req_body:
            lines.append('')
            lines.append('  Request Body:')
            lines.append(_format_body(req_body))

        resp_body = r.get('response_body') or r.get('responseBody') or r.get('body')
        if resp_body:
            lines.append('')
            lines.append('  Response Body:')
            lines.append(_format_body(resp_body))

    return '\n'.join(lines)


def _format_body(body: str, max_bytes: int = 4096) -> str:
    """Format a body string, pretty-printing JSON and truncating large bodies."""
    if len(body) > max_bytes:
        truncated = body[:max_bytes]
        remaining = len(body) - max_bytes
        suffix = f'\n    ... ({remaining:,} more bytes)'
    else:
        truncated = body
        suffix = ''

    # Try to pretty-print JSON
    try:
        parsed = json.loads(truncated if not suffix else body)
        pretty = json.dumps(parsed, indent=2)
        if len(pretty) > max_bytes:
            pretty = pretty[:max_bytes] + f'\n    ... ({len(pretty) - max_bytes:,} more bytes)'
        return '    ' + pretty.replace('\n', '\n    ') + suffix
    except (json.JSONDecodeError, RecursionError):
        return '    ' + truncated.replace('\n', '\n    ') + suffix


# ── Commands ───────────────────────────────────────────────


def cmd_log_tail(args: list[str]):
    """passe log tail [-n N] [--file PATH] [--json]"""
    count = 20
    file_path = str(DEFAULT_LOG_PATH)
    as_json = '--json' in args
    args = [a for a in args if a != '--json']

    if '-n' in args:
        idx = args.index('-n')
        if idx + 1 < len(args):
            try:
                count = int(args[idx + 1])
            except ValueError:
                print('passe log tail: -n requires a number', file=sys.stderr)
                sys.exit(1)
            args = args[:idx] + args[idx + 2:]

    explicit_file = False
    if '--file' in args:
        idx = args.index('--file')
        if idx + 1 < len(args):
            file_path = args[idx + 1]
            explicit_file = True
            args = args[:idx] + args[idx + 2:]

    if not Path(file_path).exists():
        if explicit_file:
            print(f'passe log: no log file at {file_path}', file=sys.stderr)
            sys.exit(1)
        print('No requests yet', file=sys.stderr)
        return

    requests = read_requests(file_path)
    recent = requests[-count:]  # last N, oldest first
    recent.reverse()  # newest first for display

    if as_json:
        for r in recent:
            print(json.dumps(r, default=str))
        return

    color = _use_color()
    for r in recent:
        print(format_request_line(r, color=color))


def cmd_log_list(args: list[str]):
    """passe log list [--filter P] [--method M] [--status S] [--limit N] [--file PATH] [--json]"""
    file_path = str(DEFAULT_LOG_PATH)
    explicit_file = False
    url_pattern = None
    method = None
    status_pattern = None
    limit = 50  # default limit to avoid flooding
    as_json = '--json' in args
    args = [a for a in args if a != '--json']

    # Extract flags
    for flag, attr in [('--filter', 'url_pattern'), ('--method', 'method'),
                       ('--status', 'status_pattern'), ('--limit', 'limit'),
                       ('--file', 'file_path')]:
        if flag in args:
            idx = args.index(flag)
            if idx + 1 < len(args):
                val = args[idx + 1]
                if attr == 'limit':
                    val = int(val)
                if attr == 'url_pattern':
                    url_pattern = val
                elif attr == 'method':
                    method = val
                elif attr == 'status_pattern':
                    status_pattern = val
                elif attr == 'limit':
                    limit = val
                elif attr == 'file_path':
                    file_path = val
                    explicit_file = True
                args = args[:idx] + args[idx + 2:]

    if not Path(file_path).exists():
        if explicit_file:
            print(f'passe log: no log file at {file_path}', file=sys.stderr)
            sys.exit(1)
        print('No requests yet', file=sys.stderr)
        return

    requests = read_requests(file_path)
    filtered = filter_requests(requests, url_pattern=url_pattern,
                               method=method, status_pattern=status_pattern,
                               limit=limit)
    filtered.reverse()  # newest first

    if as_json:
        for r in filtered:
            print(json.dumps(r, default=str))
        return

    color = _use_color()
    for r in filtered:
        print(format_request_line(r, color=color))

    print(f'\n{len(filtered)} requests (of {len(requests)} total)',
          file=sys.stderr)


def cmd_log_show(args: list[str]):
    """passe log show ID [--headers] [--body] [--file PATH]"""
    file_path = str(DEFAULT_LOG_PATH)
    show_headers = '--headers' in args
    show_body = '--body' in args
    args = [a for a in args if a not in ('--headers', '--body')]

    if '--file' in args:
        idx = args.index('--file')
        if idx + 1 < len(args):
            file_path = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if not args:
        print('passe log show requires a request ID (or prefix)',
              file=sys.stderr)
        sys.exit(1)
    target_id = args[0]

    if not Path(file_path).exists():
        print(f'passe log: no log file at {file_path}', file=sys.stderr)
        sys.exit(1)

    requests = read_requests_with_rotated(file_path)
    # Prefix match on ID
    matches = [r for r in requests
               if (r.get('id') or r.get('requestId') or '').startswith(target_id)]

    if not matches:
        print(f'passe log show: no request matching {target_id!r}',
              file=sys.stderr)
        sys.exit(1)

    if len(matches) > 1:
        print(f'passe log show: {len(matches)} matches for {target_id!r}, '
              f'showing first. Use a longer prefix to narrow.',
              file=sys.stderr)

    print(format_request_detail(matches[0], show_headers=show_headers,
                                show_body=show_body))


def cmd_log_clear(args: list[str]):
    """passe log clear [--older Nd/Nh/Nm] [--file PATH]"""
    file_path = str(DEFAULT_LOG_PATH)
    older_than = None

    if '--file' in args:
        idx = args.index('--file')
        if idx + 1 < len(args):
            file_path = args[idx + 1]
            args = args[:idx] + args[idx + 2:]

    if '--older' in args:
        idx = args.index('--older')
        if idx + 1 < len(args):
            older_than = _parse_duration(args[idx + 1])
            if older_than is None:
                print('passe log clear: invalid duration (use Nd, Nh, or Nm)',
                      file=sys.stderr)
                sys.exit(1)
            args = args[:idx] + args[idx + 2:]

    log_path = Path(file_path)

    if older_than is not None:
        # Selective clear: keep entries newer than cutoff
        cutoff = datetime.now(timezone.utc) - older_than
        _prune_older(log_path, cutoff)
    else:
        # Full clear
        if log_path.exists():
            log_path.unlink()
            print(f'Cleared {log_path}', file=sys.stderr)

        # Also clear rotated files
        for i in range(1, 4):
            rotated = log_path.parent / f'{log_path.name}.{i}'
            if rotated.exists():
                rotated.unlink()
                print(f'Cleared {rotated}', file=sys.stderr)


def _parse_duration(s: str):
    """Parse duration string like '7d', '24h', '30m'. Returns timedelta or None."""
    from datetime import timedelta
    m = re.match(r'^(\d+)([dhm])$', s)
    if not m:
        return None
    val = int(m.group(1))
    unit = m.group(2)
    if unit == 'd':
        return timedelta(days=val)
    elif unit == 'h':
        return timedelta(hours=val)
    elif unit == 'm':
        return timedelta(minutes=val)
    return None


def _prune_older(log_path: Path, cutoff: datetime):
    """Remove entries older than cutoff from log and rotated files."""
    from datetime import timedelta

    # Clear rotated files entirely if they're older
    for i in range(3, 0, -1):
        rotated = log_path.parent / f'{log_path.name}.{i}'
        if rotated.exists():
            rotated.unlink()
            print(f'Cleared rotated file {rotated.name}', file=sys.stderr)

    # Filter active log
    if not log_path.exists():
        return

    cutoff_str = cutoff.isoformat()
    kept = 0
    removed = 0
    temp = log_path.with_suffix('.tmp')

    with open(log_path) as fin, open(temp, 'w') as fout:
        for line in fin:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                ts = entry.get('ts', '')
                if ts and ts < cutoff_str:
                    removed += 1
                    continue
            except json.JSONDecodeError:
                pass  # keep malformed lines
            fout.write(line + '\n')
            kept += 1

    temp.rename(log_path)
    print(f'Pruned {removed} entries, kept {kept}', file=sys.stderr)
