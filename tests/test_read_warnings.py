"""
Test Chamber 9: Read Extraction Cascade
========================================

Tests for the three-stage extraction cascade in do_read:
  trafilatura → Readability.js+Turndown → innerText

No browser needed: we mock CDP calls and trafilatura to test
the Python-side cascade logic directly.
"""

import json
import sys
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from passe.cli import do_read


def _make_client(*values):
    """Mock CDPClient where each send() returns a different value string.

    do_read calls client.send (via do_eval) for outerHTML and metadata,
    then optionally for the Readability fallback path. Each call returns
    the next value from the sequence.
    """
    client = AsyncMock()
    client.send = AsyncMock(side_effect=[
        {'result': {'result': {'value': v}}} for v in values
    ])
    return client


def _traf_module(return_value=None, side_effect=None):
    """Create a mock trafilatura module injected via sys.modules."""
    mod = MagicMock()
    mod.extract = MagicMock(return_value=return_value, side_effect=side_effect)
    return mod


# ── Stage 1: trafilatura succeeds ──────────────────────────

@pytest.mark.asyncio
async def test_trafilatura_succeeds():
    """Trafilatura extracts good content — used as primary."""
    content = 'A' * 500
    client = _make_client(
        '<html><body><article>' + content + '</article></body></html>',
        json.dumps({'textLength': 600, 'url': 'http://example.com'}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'
    assert result['warning'] is None
    assert len(result['markdown']) == 500
    mock_traf.extract.assert_called_once()


@pytest.mark.asyncio
async def test_trafilatura_file_output(tmp_path):
    """Trafilatura content written to file."""
    content = 'Good markdown content'
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com'}),
    )
    outfile = str(tmp_path / 'out.md')
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client, path=outfile)

    assert result['source'] == 'trafilatura'
    with open(outfile) as f:
        assert f.read() == content


@pytest.mark.asyncio
async def test_trafilatura_passes_url():
    """Trafilatura receives the page URL for better extraction."""
    content = 'A' * 500
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 600, 'url': 'http://example.com/article'}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        await do_read(client)

    _, kwargs = mock_traf.extract.call_args
    assert kwargs['url'] == 'http://example.com/article'


# ── Stage 2: trafilatura fails, Readability succeeds ───────

@pytest.mark.asyncio
async def test_trafilatura_none_falls_to_readability():
    """Trafilatura returns None — falls through to Readability."""
    readability_data = json.dumps({
        'title': 'Test Article',
        'markdown': 'B' * 500,
        'length': 500,
        'pageTextLength': 600,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 600, 'url': 'http://example.com'}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    assert result['warning'] is None
    assert len(result['markdown']) == 500


@pytest.mark.asyncio
async def test_trafilatura_too_short_falls_to_readability():
    """Trafilatura extracts <10% of page text — rejected, falls to Readability."""
    readability_data = json.dumps({
        'title': 'Test',
        'markdown': 'C' * 2000,
        'length': 2000,
        'pageTextLength': 5000,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 5000, 'url': 'http://example.com'}),
        readability_data,
    )
    # 4 chars out of 5000 = 0.08%
    mock_traf = _traf_module(return_value='tiny')
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'


@pytest.mark.asyncio
async def test_trafilatura_exception_falls_to_readability():
    """Trafilatura throws — falls through gracefully to Readability."""
    readability_data = json.dumps({
        'title': 'Test',
        'markdown': 'D' * 500,
        'length': 500,
        'pageTextLength': 600,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 600, 'url': 'http://example.com'}),
        readability_data,
    )
    mock_traf = _traf_module(side_effect=RuntimeError('extraction failed'))
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'


# ── Stage 3: both fail, innerText fallback ─────────────────

@pytest.mark.asyncio
async def test_both_fail_innertext_fallback():
    """Trafilatura and Readability both fail — innerText fallback."""
    readability_data = json.dumps({
        'title': 'Dashboard',
        'markdown': 'Loading...',
        'fallback': True,
        'pageTextLength': 100,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com'}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'innerText'
    assert result['warning'] is not None
    assert 'fell back to innerText' in result['warning']


@pytest.mark.asyncio
async def test_fallback_with_error_triggers_warning():
    """Error during browser extraction — still falls back cleanly."""
    readability_data = json.dumps({
        'title': 'Broken Page',
        'markdown': 'Some text',
        'fallback': True,
        'error': 'Unexpected token',
        'pageTextLength': 100,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com'}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'innerText'
    assert 'fell back' in result['warning']


# ── Ratio warnings ────────────────────────────────────────

@pytest.mark.asyncio
async def test_readability_low_ratio_warning():
    """Readability output is <10% of page text — warning fires."""
    readability_data = json.dumps({
        'title': 'Cookie Banner Page',
        'markdown': 'Accept cookies',  # 14 chars out of 5000
        'length': 14,
        'pageTextLength': 5000,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 5000, 'url': 'http://example.com'}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    assert result['warning'] is not None
    assert 'incomplete' in result['warning']
    assert '0.3%' in result['warning']


@pytest.mark.asyncio
async def test_borderline_ratio_no_warning():
    """Extraction at exactly 10% — no warning."""
    readability_data = json.dumps({
        'title': 'Just Enough',
        'markdown': 'A' * 100,
        'length': 100,
        'pageTextLength': 1000,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 1000, 'url': 'http://example.com'}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    assert result['warning'] is None


@pytest.mark.asyncio
async def test_zero_page_text_no_divide_by_zero():
    """Empty page — no ZeroDivisionError."""
    readability_data = json.dumps({
        'title': 'Empty',
        'markdown': '',
        'pageTextLength': 0,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 0, 'url': 'http://example.com'}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    # Empty markdown is falsy → falls to 'All extractors returned empty'
    assert result['source'] == 'innerText'
    assert 'empty' in result['warning'].lower()


@pytest.mark.asyncio
async def test_warning_written_to_file_still_warns(tmp_path):
    """Warning fires even when writing to file."""
    readability_data = json.dumps({
        'title': 'Test',
        'markdown': 'tiny',
        'fallback': True,
        'pageTextLength': 1000,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 1000, 'url': 'http://example.com'}),
        readability_data,
    )
    outfile = str(tmp_path / 'out.md')
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client, path=outfile)

    assert result['warning'] is not None
    with open(outfile) as f:
        assert f.read() == 'tiny'
