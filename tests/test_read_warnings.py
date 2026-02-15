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


def _make_client(*values, content_type='text/html'):
    """Mock CDPClient where each send() returns a different value string.

    do_read calls client.send (via do_eval) for:
      1. document.contentType (content-type sniffing)
      2. outerHTML (shadow DOM flattened)
      3. metadata JSON (textLength + url)
      4+ optionally Readability fallback, DOM structure eval, etc.
    Each call returns the next value from the sequence.
    The content_type parameter is prepended automatically.
    """
    all_values = (content_type, *values)
    client = AsyncMock()
    client.send = AsyncMock(side_effect=[
        {'result': {'result': {'value': v}}} for v in all_values
    ])
    return client


def _traf_module(return_value=None, side_effect=None):
    """Create a mock trafilatura module injected via sys.modules."""
    mod = MagicMock()
    mod.extract = MagicMock(return_value=return_value, side_effect=side_effect)
    return mod


# ── Stage 1: trafilatura succeeds ──────────────────────────

NO_STRUCTURE = json.dumps({'dataRows': 0, 'codeBlocks': 0})


@pytest.mark.asyncio
async def test_trafilatura_succeeds():
    """Trafilatura extracts good content — used as primary."""
    content = 'A' * 500
    client = _make_client(
        '<html><body><article>' + content + '</article></body></html>',
        json.dumps({'textLength': 600, 'url': 'http://example.com'}),
        NO_STRUCTURE,
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
        NO_STRUCTURE,
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
        NO_STRUCTURE,
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
async def test_trafilatura_exception_falls_to_readability(capsys):
    """Trafilatura throws — falls through with warning to stderr."""
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
    stderr = capsys.readouterr().err
    assert 'trafilatura failed: extraction failed' in stderr
    assert 'falling back to Readability' in stderr


@pytest.mark.asyncio
async def test_trafilatura_import_error_warns(capsys):
    """Trafilatura not installed — warning on stderr, falls to Readability."""
    readability_data = json.dumps({
        'title': 'Test',
        'markdown': 'E' * 500,
        'length': 500,
        'pageTextLength': 600,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 600, 'url': 'http://example.com'}),
        readability_data,
    )
    # Remove trafilatura from sys.modules so the import fails
    with patch.dict(sys.modules, {'trafilatura': None}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    stderr = capsys.readouterr().err
    assert 'trafilatura not installed' in stderr


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
        'markdown': 'A' * 300,
        'length': 300,
        'pageTextLength': 3000,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 3000, 'url': 'http://example.com'}),
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


# ── Structural quality gate ──────────────────────────────

@pytest.mark.asyncio
async def test_table_loss_triggers_readability_fallback(capsys):
    """Page has 10 data rows but trafilatura output has no tables → reject."""
    content = 'A plain text summary without any tables or pipes'
    readability_data = json.dumps({
        'title': 'Country Codes',
        'markdown': '| Code | Country |\n|---|---|\n| US | United States |',
        'length': 50,
        'pageTextLength': 200,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 200, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 10, 'codeBlocks': 0}),  # DOM signals
        readability_data,  # Readability fallback
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    assert '|' in result['markdown']
    stderr = capsys.readouterr().err
    assert 'quality gate' in stderr
    assert 'table rows' in stderr


@pytest.mark.asyncio
async def test_code_loss_triggers_readability_fallback(capsys):
    """Page has 3 code blocks but trafilatura output has none → reject."""
    content = 'Just prose about Python asyncio patterns'
    readability_data = json.dumps({
        'title': 'Asyncio Docs',
        'markdown': '```python\nawait asyncio.sleep(1)\n```',
        'length': 40,
        'pageTextLength': 200,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 200, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 0, 'codeBlocks': 3}),  # DOM signals
        readability_data,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    assert '```' in result['markdown']
    stderr = capsys.readouterr().err
    assert 'quality gate' in stderr
    assert 'code blocks' in stderr


@pytest.mark.asyncio
async def test_both_table_and_code_loss(capsys):
    """Page has both tables and code, trafilatura drops both → reject."""
    content = 'A' * 200  # Long enough to pass 10% ratio check
    readability_data = json.dumps({
        'title': 'Rich Page',
        'markdown': '| A | B |\n```\ncode\n```',
        'length': 30,
        'pageTextLength': 200,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 200, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 8, 'codeBlocks': 4}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    stderr = capsys.readouterr().err
    assert 'table rows' in stderr
    assert 'code blocks' in stderr


@pytest.mark.asyncio
async def test_quality_gate_passes_when_output_has_tables():
    """Trafilatura preserves table markers → gate passes (small table, binary check)."""
    content = 'Title\n\n| Code | Country |\n|---|---|\n| US | United States |'
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 200, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 5, 'codeBlocks': 0}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'


@pytest.mark.asyncio
async def test_quality_gate_passes_when_output_has_code():
    """Trafilatura preserves code fences → gate passes."""
    content = 'Example:\n\n```python\nprint("hello")\n```\n'
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 200, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 0, 'codeBlocks': 3}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'


@pytest.mark.asyncio
async def test_quality_gate_skips_when_page_has_little_structure():
    """Page has <5 table rows — gate doesn't reject even if output lacks tables."""
    content = 'A' * 200
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 200, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 3, 'codeBlocks': 1}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'


@pytest.mark.asyncio
async def test_proportional_table_loss_triggers_fallback(capsys):
    """Page has 100 data rows, output has 5 table rows (<25%) → reject."""
    # 5 pipe-table rows with word chars — passes binary check but fails proportional
    rows = '\n'.join(f'| {i} | data |' for i in range(5))
    content = 'A' * 200 + '\n' + rows
    readability_data = json.dumps({
        'title': 'Big Table',
        'markdown': '| full | table |',
        'length': 50,
        'pageTextLength': 500,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 500, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 100, 'codeBlocks': 0}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    stderr = capsys.readouterr().err
    assert 'quality gate' in stderr
    assert '100 table rows' in stderr
    assert 'got 5' in stderr


@pytest.mark.asyncio
async def test_proportional_check_passes_when_enough_rows():
    """Page has 20 data rows, output has 15 (75%) → pass."""
    rows = '\n'.join(f'| {i} | data |' for i in range(15))
    content = 'A' * 100 + '\n' + rows
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 200, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 20, 'codeBlocks': 0}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'


@pytest.mark.asyncio
async def test_quality_gate_no_dom_eval_when_output_rich():
    """Output has 20+ table rows AND 5+ code blocks → DOM eval skipped (only 2 send calls)."""
    rows = '\n'.join(f'| {i} | data |' for i in range(25))
    code = '\n\n'.join(f'```\ncode block {i}\n```' for i in range(6))
    content = rows + '\n\n' + code
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 500, 'url': 'http://example.com'}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'
    # Only 2 calls: outerHTML + meta. No DOM signal eval.
    assert client.send.call_count == 3  # content-type + outerHTML + meta


@pytest.mark.asyncio
async def test_quality_gate_proportional_code_loss(capsys):
    """Page has 120 <pre> blocks but output has only 3 → gate fires (Effective Go scenario)."""
    code = '\n\n'.join(f'```\nblock {i}\n```' for i in range(3))
    content = 'A' * 200 + '\n' + code
    readability_data = json.dumps({
        'title': 'Test', 'markdown': '# Fallback\n```\ncode\n```',
        'pageTextLength': 500,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 500, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 0, 'codeBlocks': 120}),
        readability_data,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'readability'
    stderr = capsys.readouterr().err
    assert 'quality gate' in stderr
    assert '120 code blocks' in stderr
    assert 'got 3' in stderr


@pytest.mark.asyncio
async def test_proportional_code_check_passes_when_enough():
    """Page has 10 <pre> blocks, output has 8 (80%) → pass."""
    code = '\n\n'.join(f'```\nblock {i}\n```' for i in range(8))
    content = 'A' * 200 + '\n' + code
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 500, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 0, 'codeBlocks': 10}),
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'


@pytest.mark.asyncio
async def test_gate_reject_readability_fail_keeps_trafilatura(capsys):
    """Gate rejects trafilatura, Readability also fails → keep trafilatura (not innerText)."""
    content = 'A' * 200 + '\n```\nonly block\n```'
    readability_fallback = json.dumps({
        'title': 'Test', 'markdown': 'raw innerText here',
        'fallback': True, 'pageTextLength': 500,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 500, 'url': 'http://example.com'}),
        json.dumps({'dataRows': 30, 'codeBlocks': 0}),
        readability_fallback,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'
    assert result['markdown'] == content
    stderr = capsys.readouterr().err
    assert 'quality gate' in stderr
    assert 'Readability also failed' in stderr


@pytest.mark.asyncio
async def test_no_gate_reject_readability_fail_uses_innertext(capsys):
    """No gate rejection + Readability fails → innerText (no trafilatura to restore)."""
    readability_fallback = json.dumps({
        'title': 'Test', 'markdown': 'raw innerText here',
        'fallback': True, 'pageTextLength': 500,
    })
    client = _make_client(
        '<html></html>',
        json.dumps({'textLength': 500, 'url': 'http://example.com'}),
        readability_fallback,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'innerText'
    stderr = capsys.readouterr().err
    assert 'fell back to innerText' in stderr


# ── force_source (--source flag) ──────────────────────────────


@pytest.mark.asyncio
async def test_force_source_trafilatura():
    """--source trafilatura skips cascade, uses trafilatura only."""
    client = _make_client(
        '<html><body>hello</body></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com'}),
    )
    mock_traf = _traf_module(return_value='# Forced trafilatura')
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client, force_source='trafilatura')

    assert result['source'] == 'trafilatura'
    assert result['markdown'] == '# Forced trafilatura'
    # Only 2 send calls (outerHTML + meta), no Readability or DOM eval
    assert client.send.call_count == 3  # content-type + outerHTML + meta


@pytest.mark.asyncio
async def test_force_source_readability():
    """--source readability skips trafilatura, uses Readability directly."""
    readability_data = json.dumps({
        'title': 'Test', 'markdown': '# From Readability',
        'pageTextLength': 100,
    })
    client = _make_client(
        '<html><body>hello</body></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com'}),
        readability_data,
    )
    result = await do_read(client, force_source='readability')

    assert result['source'] == 'readability'
    assert result['markdown'] == '# From Readability'


@pytest.mark.asyncio
async def test_force_source_innertext():
    """--source innertext skips everything, returns raw innerText."""
    client = _make_client(
        '<html><body>hello</body></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com'}),
        'Raw text content here',
    )
    result = await do_read(client, force_source='innertext')

    assert result['source'] == 'innerText'
    assert result['markdown'] == 'Raw text content here'


@pytest.mark.asyncio
async def test_force_source_unknown(capsys):
    """--source bogus warns about unknown source."""
    client = _make_client(
        '<html><body>hello</body></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com'}),
    )
    result = await do_read(client, force_source='bogus')

    assert result['markdown'] == ''
    stderr = capsys.readouterr().err
    assert 'Unknown source' in stderr


# ── Content-type sniffing: raw passthrough ────────────────


def _make_raw_client(content_type, body_text):
    """Mock client for content-type sniffing tests.

    Returns content_type for document.contentType, then body_text for innerText.
    """
    client = AsyncMock()
    client.send = AsyncMock(side_effect=[
        {'result': {'result': {'value': content_type}}},
        {'result': {'result': {'value': body_text}}},
    ])
    return client


@pytest.mark.asyncio
async def test_json_content_type_raw_passthrough():
    """application/json triggers raw passthrough with pretty-printing."""
    raw_json = '{"name":"test","value":42}'
    client = _make_raw_client('application/json', raw_json)
    result = await do_read(client)

    assert result['source'] == 'raw'
    assert result['content_type'] == 'application/json'
    # Should be pretty-printed
    parsed = json.loads(result['markdown'])
    assert parsed == {'name': 'test', 'value': 42}
    assert '\n' in result['markdown']  # indented


@pytest.mark.asyncio
async def test_plain_text_raw_passthrough():
    """text/plain triggers raw passthrough, no transformation."""
    text = 'Just some plain text\nwith newlines.'
    client = _make_raw_client('text/plain', text)
    result = await do_read(client)

    assert result['source'] == 'raw'
    assert result['content_type'] == 'text/plain'
    assert result['markdown'] == text


@pytest.mark.asyncio
async def test_xml_content_type_raw_passthrough():
    """text/xml triggers raw passthrough."""
    xml = '<root><item>hello</item></root>'
    client = _make_raw_client('text/xml', xml)
    result = await do_read(client)

    assert result['source'] == 'raw'
    assert result['content_type'] == 'text/xml'
    assert result['markdown'] == xml


@pytest.mark.asyncio
async def test_csv_content_type_raw_passthrough():
    """text/csv triggers raw passthrough."""
    csv_data = 'name,value\nfoo,1\nbar,2'
    client = _make_raw_client('text/csv', csv_data)
    result = await do_read(client)

    assert result['source'] == 'raw'
    assert result['content_type'] == 'text/csv'
    assert result['markdown'] == csv_data


@pytest.mark.asyncio
async def test_content_type_with_charset_still_matches():
    """Content-type with ;charset=utf-8 suffix still triggers raw."""
    client = AsyncMock()
    client.send = AsyncMock(side_effect=[
        {'result': {'result': {'value': 'application/json; charset=utf-8'}}},
        {'result': {'result': {'value': '{"ok": true}'}}},
    ])
    result = await do_read(client)

    assert result['source'] == 'raw'
    assert result['content_type'] == 'application/json'


@pytest.mark.asyncio
async def test_html_content_type_uses_cascade():
    """text/html does NOT trigger raw passthrough — uses extraction cascade."""
    content = 'A' * 500
    client = _make_client(
        '<html><body>' + content + '</body></html>',
        json.dumps({'textLength': 600, 'url': 'http://example.com'}),
        NO_STRUCTURE,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['source'] == 'trafilatura'
    assert 'content_type' not in result


@pytest.mark.asyncio
async def test_force_source_raw_overrides_html():
    """--source raw forces raw passthrough even on text/html."""
    body_text = '<h1>Hello</h1><p>World</p>'
    client = _make_raw_client('text/html', body_text)
    result = await do_read(client, force_source='raw')

    assert result['source'] == 'raw'
    assert result['content_type'] == 'text/html'
    assert result['markdown'] == body_text


@pytest.mark.asyncio
async def test_force_source_trafilatura_overrides_json():
    """--source trafilatura on a JSON page skips raw, uses trafilatura."""
    client = _make_client(
        '<html><body>{"data": true}</body></html>',
        json.dumps({'textLength': 100, 'url': 'http://example.com/api'}),
        content_type='application/json',
    )
    mock_traf = _traf_module(return_value='extracted content')
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client, force_source='trafilatura')

    assert result['source'] == 'trafilatura'


@pytest.mark.asyncio
async def test_json_raw_passthrough_writes_file(tmp_path):
    """Raw JSON passthrough writes pretty-printed content to file."""
    raw_json = '{"items":[1,2,3]}'
    client = _make_raw_client('application/json', raw_json)
    outfile = str(tmp_path / 'out.json')
    result = await do_read(client, path=outfile)

    assert result['source'] == 'raw'
    with open(outfile) as f:
        written = f.read()
    assert json.loads(written) == {'items': [1, 2, 3]}
    assert '\n' in written


@pytest.mark.asyncio
async def test_invalid_json_returned_as_is():
    """If body claims JSON but isn't valid, return raw text without crashing."""
    client = _make_raw_client('application/json', 'not valid json {{{')
    result = await do_read(client)

    assert result['source'] == 'raw'
    assert result['markdown'] == 'not valid json {{{'


# ── Thin-read diagnostics ────────────────────────────────


def _make_thin_client(html, meta_dict, *extra_values, content_type='text/html'):
    """Mock client for thin-read tests.

    Provides content_type, outerHTML, meta JSON, then any extra values
    (e.g. Readability fallback response).
    """
    meta_json = json.dumps(meta_dict)
    all_values = (content_type, html, meta_json, *extra_values)
    client = AsyncMock()
    client.send = AsyncMock(side_effect=[
        {'result': {'result': {'value': v}}} for v in all_values
    ])
    return client


@pytest.mark.asyncio
async def test_thin_read_js_hydration(capsys):
    """Large HTML but tiny extraction → JS hydration diagnosis."""
    big_html = '<html><body>' + '<div>' * 500 + '</div>' * 500 + '</body></html>'
    readability_data = json.dumps({
        'title': 'SPA Page',
        'markdown': 'Loading...',
        'length': 10,
        'pageTextLength': 500,
    })
    client = _make_thin_client(
        big_html,
        {'textLength': 500, 'htmlLength': len(big_html), 'title': 'SPA Page', 'url': 'http://example.com'},
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result.get('thin_read') is not None
    assert result['thin_read']['possible_cause'] == 'js_hydration'
    assert result['thin_read']['word_count'] == 1  # "Loading..."
    assert result['thin_read']['title'] == 'SPA Page'
    stderr = capsys.readouterr().err
    assert 'thin-read' in stderr
    assert 'js hydration' in stderr


@pytest.mark.asyncio
async def test_thin_read_auth_wall(capsys):
    """HTML with login form + auth keywords → auth wall diagnosis."""
    auth_html = '<html><body><form><input type="password"><p>Please log in</p></form></body></html>'
    readability_data = json.dumps({
        'title': 'Login Required',
        'markdown': 'Please log in',
        'length': 13,
        'pageTextLength': 13,
    })
    client = _make_thin_client(
        auth_html,
        {'textLength': 13, 'htmlLength': len(auth_html), 'title': 'Login Required', 'url': 'http://example.com/secret'},
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['thin_read']['possible_cause'] == 'auth_wall'
    stderr = capsys.readouterr().err
    assert 'auth wall' in stderr


@pytest.mark.asyncio
async def test_thin_read_empty_page(capsys):
    """Very little page text → empty page diagnosis."""
    readability_data = json.dumps({
        'title': 'Blank',
        'markdown': '',
        'length': 0,
        'pageTextLength': 0,
    })
    client = _make_thin_client(
        '<html><body></body></html>',
        {'textLength': 20, 'htmlLength': 50, 'title': 'Blank', 'url': 'http://example.com/empty'},
        readability_data,
    )
    mock_traf = _traf_module(return_value=None)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['thin_read']['possible_cause'] == 'empty_page'


@pytest.mark.asyncio
async def test_no_thin_read_on_normal_extraction():
    """Normal-sized extraction does NOT trigger thin-read."""
    content = 'A' * 500
    client = _make_client(
        '<html><body><article>' + content + '</article></body></html>',
        json.dumps({'textLength': 600, 'htmlLength': 2000, 'title': 'Article', 'url': 'http://example.com'}),
        NO_STRUCTURE,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result.get('thin_read') is None
    assert result['title'] == 'Article'


@pytest.mark.asyncio
async def test_no_thin_read_on_small_but_complete_page():
    """Small page with high extraction ratio — like example.com — no thin-read."""
    content = 'Example Domain. This domain is for use in illustrative examples in documents. ' \
              'You may use this domain in examples without prior coordination.'  # 142 chars
    client = _make_thin_client(
        '<html><body>' + content + '</body></html>',
        {'textLength': 180, 'htmlLength': 500, 'title': 'Example Domain', 'url': 'http://example.com'},
        NO_STRUCTURE,
    )
    mock_traf = _traf_module(return_value=content)
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    # 142 chars < 200 threshold, but extraction ratio is ~79% and page_text >= 100
    assert result.get('thin_read') is None


@pytest.mark.asyncio
async def test_thin_read_includes_title():
    """Thin-read diagnostic includes page title."""
    readability_data = json.dumps({
        'title': 'Developer Reference',
        'markdown': 'Error',
        'length': 5,
        'pageTextLength': 100,
    })
    client = _make_thin_client(
        '<html><body><div>' + 'x' * 5000 + '</div></body></html>',
        {'textLength': 100, 'htmlLength': 10000, 'title': 'Developer Reference', 'url': 'http://example.com'},
        readability_data,
    )
    mock_traf = _traf_module(return_value='Error')
    with patch.dict(sys.modules, {'trafilatura': mock_traf}):
        result = await do_read(client)

    assert result['thin_read']['title'] == 'Developer Reference'
    assert result['title'] == 'Developer Reference'
