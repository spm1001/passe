"""Tests for cmd_fetch fast-path inline content routing."""

import json
import os
import sys
import tempfile
from io import StringIO
from unittest.mock import patch

import pytest

from passe.commands import cmd_fetch
from passe.fastpath import FastPathResult


def _fp_result(markdown: str, **kwargs) -> FastPathResult:
    defaults = {
        'url': 'https://example.com/',
        'source': 'trafilatura',
        'quality_score': 0.85,
        'word_count': len(markdown.split()),
        'fetch_ms': 42.0,
        'content_type': 'text/html',
        'escalate_reason': None,
    }
    defaults.update(kwargs)
    return FastPathResult(markdown=markdown, **defaults)


@pytest.mark.asyncio
async def test_fast_path_short_content_inlined():
    """Short fast-path content appears as summary['content'], not 'files'."""
    md = 'Hello world, this is short content.'
    fp = _fp_result(md)

    with patch('passe.fastpath.try_http_fetch', return_value=fp), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_fetch('https://example.com')

    result = json.loads(out.getvalue())
    assert result['ok'] is True
    assert result['fast_path'] is True
    assert result['content'] == md
    assert result['word_count'] == len(md.split())
    assert 'files' not in result


@pytest.mark.asyncio
async def test_fast_path_long_content_creates_temp_file():
    """Long fast-path content (>2000 words) creates a temp file."""
    md = ' '.join(['word'] * 2500)
    fp = _fp_result(md)

    with patch('passe.fastpath.try_http_fetch', return_value=fp), \
         patch('sys.stdout', new_callable=StringIO) as out, \
         patch('sys.stderr', new_callable=StringIO):
        await cmd_fetch('https://example.com')

    result = json.loads(out.getvalue())
    assert result['ok'] is True
    assert result['fast_path'] is True
    assert 'content' not in result
    assert len(result['files']) == 1
    f = result['files'][0]
    assert f['verb'] == 'fetch'
    assert f['source'] == 'trafilatura'
    assert os.path.exists(f['path'])
    with open(f['path']) as fh:
        assert fh.read() == md
    os.unlink(f['path'])


@pytest.mark.asyncio
async def test_fast_path_explicit_path_writes_file():
    """Fast-path with explicit path writes content to that path."""
    md = 'Short content but explicit path given.'
    fp = _fp_result(md)

    with tempfile.NamedTemporaryFile(suffix='.md', delete=False) as tmp:
        tmp_path = tmp.name

    try:
        with patch('passe.fastpath.try_http_fetch', return_value=fp), \
             patch('sys.stdout', new_callable=StringIO) as out, \
             patch('sys.stderr', new_callable=StringIO):
            await cmd_fetch('https://example.com', path=tmp_path)

        result = json.loads(out.getvalue())
        assert result['ok'] is True
        assert result['fast_path'] is True
        assert 'content' not in result
        assert len(result['files']) == 1
        assert result['files'][0]['path'] == tmp_path
        with open(tmp_path) as fh:
            assert fh.read() == md
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
