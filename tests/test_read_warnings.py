"""
Test Chamber 9: Read Extraction Quality Warnings
================================================

"The Enrichment Center is required to remind you that extraction
 quality is not guaranteed. The warning system exists for your safety."

Tests for the warning logic in do_read — verifying that incomplete
extractions and fallbacks are flagged without blocking success.
No browser needed: we test the Python-side logic directly.
"""

import json
from unittest.mock import AsyncMock, patch

import pytest

from passe.cli import do_read


def _mock_client(extract_json: dict) -> AsyncMock:
    """Create a mock CDPClient that returns the given extraction result."""
    client = AsyncMock()
    client.send = AsyncMock(return_value={
        'result': {
            'result': {
                'value': json.dumps(extract_json)
            }
        }
    })
    return client


@pytest.mark.asyncio
async def test_clean_extraction_no_warning():
    """Normal extraction — ratio well above 10%, no fallback."""
    data = {
        'title': 'Test Article',
        'markdown': 'A' * 500,
        'length': 500,
        'pageTextLength': 600,
    }
    client = _mock_client(data)
    result = await do_read(client)
    assert result['warning'] is None
    assert len(result['markdown']) == 500


@pytest.mark.asyncio
async def test_fallback_triggers_warning():
    """Readability returned null — fallback to innerText."""
    data = {
        'title': 'Dashboard',
        'markdown': 'Loading...',
        'fallback': True,
        'pageTextLength': 10,
    }
    client = _mock_client(data)
    result = await do_read(client)
    assert result['warning'] is not None
    assert 'fell back to innerText' in result['warning']


@pytest.mark.asyncio
async def test_low_ratio_triggers_warning():
    """Extraction captured < 10% of page text."""
    data = {
        'title': 'Cookie Banner Page',
        'markdown': 'Accept cookies',  # 14 chars
        'length': 14,
        'pageTextLength': 5000,  # 0.28% ratio
    }
    client = _mock_client(data)
    result = await do_read(client)
    assert result['warning'] is not None
    assert 'incomplete' in result['warning']
    assert '0.3%' in result['warning']


@pytest.mark.asyncio
async def test_borderline_ratio_no_warning():
    """Extraction at exactly 10% — no warning."""
    data = {
        'title': 'Just Enough',
        'markdown': 'A' * 100,
        'length': 100,
        'pageTextLength': 1000,
    }
    client = _mock_client(data)
    result = await do_read(client)
    assert result['warning'] is None


@pytest.mark.asyncio
async def test_zero_page_text_no_warning():
    """Empty page — don't divide by zero."""
    data = {
        'title': 'Empty',
        'markdown': '',
        'pageTextLength': 0,
    }
    client = _mock_client(data)
    result = await do_read(client)
    assert result['warning'] is None


@pytest.mark.asyncio
async def test_fallback_with_error_triggers_warning():
    """Error during extraction — fallback with error field."""
    data = {
        'title': 'Broken Page',
        'markdown': 'Some text',
        'fallback': True,
        'error': 'Unexpected token',
        'pageTextLength': 100,
    }
    client = _mock_client(data)
    result = await do_read(client)
    assert result['warning'] is not None
    assert 'fell back' in result['warning']


@pytest.mark.asyncio
async def test_warning_written_to_file_still_warns(tmp_path):
    """Warning fires even when writing to file."""
    data = {
        'title': 'Test',
        'markdown': 'tiny',
        'fallback': True,
        'pageTextLength': 1000,
    }
    client = _mock_client(data)
    outfile = str(tmp_path / 'out.md')
    result = await do_read(client, path=outfile)
    assert result['warning'] is not None
    # File should still be written
    with open(outfile) as f:
        assert f.read() == 'tiny'
