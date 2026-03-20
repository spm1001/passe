"""Tests for passe.log_query — JSONL reading, filtering, and formatting."""

import json
import os
import tempfile
from pathlib import Path

import pytest

from passe.log_query import (
    read_requests,
    read_requests_with_rotated,
    filter_requests,
    format_request_line,
    format_request_detail,
    cmd_log_tail,
    cmd_log_show,
    cmd_log_clear,
    _match_status,
    _parse_duration,
    _format_size,
    _format_timing,
    _format_body,
)


# ── Fixtures ───────────────────────────────────────────────

# New-format request (shared JSONL schema)
NEW_FORMAT = {
    "id": "F9A2B3C4D5E6F7",
    "ts": "2026-03-20T16:00:00.123Z",
    "method": "POST",
    "url": "https://api.example.com/v1/data",
    "status": 200,
    "mime": "application/json",
    "resource_type": "XHR",
    "size": 1234,
    "timing_ms": 342,
    "tab": {"id": "TAB1", "url": "https://app.example.com/dashboard"},
    "request_headers": {"Host": "api.example.com", "Content-Type": "application/json"},
    "response_headers": {"Content-Type": "application/json"},
    "request_body": '{"query": "test"}',
    "response_body": '{"results": [1, 2, 3]}',
}

# Old-format request (from existing passe capture)
OLD_FORMAT = {
    "requestId": "OLD123",
    "method": "GET",
    "url": "https://cdn.example.com/script.js",
    "content_type": "application/javascript",
    "resource_type": "Script",
    "status": 200,
    "request_headers": {"Host": "cdn.example.com"},
    "response_headers": {"Content-Type": "application/javascript"},
    "timestamp": 1234567.89,
    "encoded_data_length": 5678,
}


def _write_jsonl(path: Path, entries: list[dict]):
    with open(path, 'w') as f:
        for entry in entries:
            f.write(json.dumps(entry) + '\n')


@pytest.fixture
def sample_log(tmp_path):
    """Create a sample JSONL log file with mixed formats."""
    log_path = tmp_path / 'requests.jsonl'
    entries = [
        {**NEW_FORMAT, "id": "AAA111", "method": "GET",
         "url": "https://api.example.com/users", "status": 200,
         "ts": "2026-03-20T15:00:00Z"},
        {**NEW_FORMAT, "id": "BBB222", "method": "POST",
         "url": "https://api.example.com/login", "status": 401,
         "ts": "2026-03-20T15:01:00Z"},
        {**NEW_FORMAT, "id": "CCC333", "method": "GET",
         "url": "https://cdn.example.com/style.css", "status": 200,
         "resource_type": "Stylesheet", "ts": "2026-03-20T15:02:00Z"},
        {**NEW_FORMAT, "id": "DDD444", "method": "DELETE",
         "url": "https://api.example.com/users/1", "status": 500,
         "ts": "2026-03-20T15:03:00Z"},
        OLD_FORMAT,  # old format entry
    ]
    _write_jsonl(log_path, entries)
    return log_path


# ── Reading ────────────────────────────────────────────────


def test_read_requests_basic(sample_log):
    reqs = read_requests(sample_log)
    assert len(reqs) == 5


def test_read_requests_normalizes_old_format(sample_log):
    reqs = read_requests(sample_log)
    old = reqs[-1]
    assert old['mime'] == 'application/javascript'  # content_type → mime
    assert old['id'] == 'OLD123'  # requestId → id
    assert old['size'] == 5678  # encoded_data_length → size


def test_read_requests_empty_file(tmp_path):
    log = tmp_path / 'empty.jsonl'
    log.write_text('')
    assert read_requests(log) == []


def test_read_requests_missing_file(tmp_path):
    assert read_requests(tmp_path / 'nonexistent.jsonl') == []


def test_read_requests_skips_malformed(tmp_path):
    log = tmp_path / 'bad.jsonl'
    log.write_text('{"id": "good", "method": "GET", "url": "http://x"}\n'
                   'not json at all\n'
                   '{"id": "also_good", "method": "POST", "url": "http://y"}\n')
    reqs = read_requests(log)
    assert len(reqs) == 2


def test_read_with_rotated(tmp_path):
    main = tmp_path / 'requests.jsonl'
    rot1 = tmp_path / 'requests.jsonl.1'
    rot2 = tmp_path / 'requests.jsonl.2'

    _write_jsonl(rot2, [{"id": "oldest", "method": "GET", "url": "http://a"}])
    _write_jsonl(rot1, [{"id": "middle", "method": "GET", "url": "http://b"}])
    _write_jsonl(main, [{"id": "newest", "method": "GET", "url": "http://c"}])

    reqs = read_requests_with_rotated(main)
    assert len(reqs) == 3
    assert reqs[0]['id'] == 'oldest'
    assert reqs[-1]['id'] == 'newest'


# ── Filtering ──────────────────────────────────────────────


def test_filter_by_url(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, url_pattern='api.example.com')
    # Should match AAA111, BBB222, DDD444 (api.example.com)
    assert len(filtered) == 3


def test_filter_by_method(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, method='GET')
    assert all(r['method'] == 'GET' for r in filtered)


def test_filter_by_status_exact(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, status_pattern='401')
    assert len(filtered) == 1
    assert filtered[0]['id'] == 'BBB222'


def test_filter_by_status_glob(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, status_pattern='2xx')
    assert all(200 <= r['status'] < 300 for r in filtered)


def test_filter_by_status_5xx(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, status_pattern='5xx')
    assert len(filtered) == 1
    assert filtered[0]['status'] == 500


def test_filter_limit(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, limit=2)
    assert len(filtered) == 2


def test_filter_combined(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, url_pattern='api', method='GET')
    assert len(filtered) == 1
    assert filtered[0]['id'] == 'AAA111'


def test_filter_url_regex(sample_log):
    reqs = read_requests(sample_log)
    filtered = filter_requests(reqs, url_pattern=r'users(/|$)')
    assert len(filtered) == 2  # /users and /users/1


def test_filter_url_invalid_regex_falls_back(sample_log):
    reqs = read_requests(sample_log)
    # Invalid regex should fall back to substring
    filtered = filter_requests(reqs, url_pattern='api[')
    assert len(filtered) == 0  # 'api[' as substring won't match


# ── Status matching ────────────────────────────────────────


def test_match_status_exact():
    assert _match_status(404, '404')
    assert not _match_status(200, '404')


def test_match_status_glob():
    assert _match_status(404, '4xx')
    assert _match_status(403, '4xx')
    assert not _match_status(200, '4xx')
    assert _match_status(503, '5xx')


def test_match_status_none():
    assert not _match_status(None, '200')
    assert not _match_status(None, '2xx')


# ── Formatting ─────────────────────────────────────────────


def test_format_request_line_no_color():
    line = format_request_line(NEW_FORMAT, color=False)
    assert 'POST' in line
    assert 'api.example.com' in line
    assert '200' in line


def test_format_request_line_old_format():
    line = format_request_line(OLD_FORMAT, color=False)
    assert 'GET' in line
    assert 'cdn.example.com' in line


def test_format_request_detail_basic():
    detail = format_request_detail(NEW_FORMAT)
    assert 'POST https://api.example.com/v1/data' in detail
    assert 'F9A2B3C4D5E6F7' in detail
    assert '200' in detail


def test_format_request_detail_headers():
    detail = format_request_detail(NEW_FORMAT, show_headers=True)
    assert 'Request Headers:' in detail
    assert 'Host: api.example.com' in detail
    assert 'Response Headers:' in detail


def test_format_request_detail_body():
    detail = format_request_detail(NEW_FORMAT, show_body=True)
    assert 'Request Body:' in detail
    assert '"query"' in detail
    assert 'Response Body:' in detail
    assert '"results"' in detail


def test_format_request_detail_no_headers_or_body():
    detail = format_request_detail(NEW_FORMAT)
    assert 'Request Headers:' not in detail
    assert 'Request Body:' not in detail


# ── Format helpers ─────────────────────────────────────────


def test_format_size():
    assert _format_size(None) == '     -'
    assert 'B' in _format_size(512)
    assert 'K' in _format_size(2048)
    assert 'M' in _format_size(2 * 1024 * 1024)


def test_format_timing():
    assert _format_timing(None) == '     -'
    assert 'ms' in _format_timing(342)
    assert 's' in _format_timing(1500)


def test_format_body_json():
    body = '{"key": "value"}'
    formatted = _format_body(body)
    assert '"key"' in formatted
    assert '"value"' in formatted


def test_format_body_truncation():
    body = 'x' * 10000
    formatted = _format_body(body, max_bytes=100)
    assert 'more bytes' in formatted


def test_format_body_non_json():
    body = '<html><body>Hello</body></html>'
    formatted = _format_body(body)
    assert 'Hello' in formatted


# ── Duration parsing ───────────────────────────────────────


def test_parse_duration_days():
    from datetime import timedelta
    assert _parse_duration('7d') == timedelta(days=7)


def test_parse_duration_hours():
    from datetime import timedelta
    assert _parse_duration('24h') == timedelta(hours=24)


def test_parse_duration_minutes():
    from datetime import timedelta
    assert _parse_duration('30m') == timedelta(minutes=30)


def test_parse_duration_invalid():
    assert _parse_duration('abc') is None
    assert _parse_duration('7x') is None
    assert _parse_duration('') is None


# ── CLI commands ───────────────────────────────────────────


def test_cmd_log_tail(sample_log, capsys):
    cmd_log_tail(['-n', '2', '--file', str(sample_log)])
    output = capsys.readouterr().out
    lines = [l for l in output.strip().split('\n') if l.strip()]
    assert len(lines) == 2


def test_cmd_log_tail_json(sample_log, capsys):
    cmd_log_tail(['-n', '3', '--file', str(sample_log), '--json'])
    output = capsys.readouterr().out
    lines = [l for l in output.strip().split('\n') if l.strip()]
    assert len(lines) == 3
    for line in lines:
        parsed = json.loads(line)
        assert 'method' in parsed


def test_cmd_log_show(sample_log, capsys):
    cmd_log_show(['AAA111', '--file', str(sample_log)])
    output = capsys.readouterr().out
    assert 'GET https://api.example.com/users' in output


def test_cmd_log_show_prefix(sample_log, capsys):
    cmd_log_show(['AAA', '--file', str(sample_log)])
    output = capsys.readouterr().out
    assert 'AAA111' in output


def test_cmd_log_show_headers(sample_log, capsys):
    cmd_log_show(['AAA111', '--headers', '--file', str(sample_log)])
    output = capsys.readouterr().out
    assert 'Request Headers:' in output


def test_cmd_log_show_not_found(sample_log):
    with pytest.raises(SystemExit):
        cmd_log_show(['ZZZZZ', '--file', str(sample_log)])


def test_cmd_log_clear_full(tmp_path):
    log = tmp_path / 'requests.jsonl'
    rot1 = tmp_path / 'requests.jsonl.1'
    _write_jsonl(log, [{"id": "a", "method": "GET", "url": "http://x"}])
    _write_jsonl(rot1, [{"id": "b", "method": "GET", "url": "http://y"}])

    cmd_log_clear(['--file', str(log)])

    assert not log.exists()
    assert not rot1.exists()


def test_cmd_log_clear_older(tmp_path):
    log = tmp_path / 'requests.jsonl'
    entries = [
        {"id": "old", "ts": "2026-01-01T00:00:00Z", "method": "GET", "url": "http://old"},
        {"id": "new", "ts": "2099-01-01T00:00:00Z", "method": "GET", "url": "http://new"},
    ]
    _write_jsonl(log, entries)

    cmd_log_clear(['--older', '1d', '--file', str(log)])

    remaining = read_requests(log)
    assert len(remaining) == 1
    assert remaining[0]['id'] == 'new'
