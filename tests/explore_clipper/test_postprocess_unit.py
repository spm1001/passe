#!/usr/bin/env python3
"""Unit tests for passe._postprocess module."""
import sys
sys.path.insert(0, 'src')

from passe._postprocess import resolve_relative_urls, strip_links, truncate_words


def test_resolve_relative_urls():
    md = 'See [schlep](schlep.html) and [marginal](marginal.html) for more.'
    result = resolve_relative_urls(md, 'https://paulgraham.com/startupideas.html')
    assert 'https://paulgraham.com/schlep.html' in result, f'Expected absolute URL, got: {result}'
    assert 'https://paulgraham.com/marginal.html' in result
    print('✓ resolve_relative_urls: basic relative URLs')

    # Absolute URLs should be untouched
    md2 = 'Visit [Google](https://google.com) for search.'
    result2 = resolve_relative_urls(md2, 'https://example.com/')
    assert 'https://google.com' in result2
    print('✓ resolve_relative_urls: absolute URLs preserved')

    # Root-relative URLs
    md3 = 'See [docs](/docs/api.html) for the API.'
    result3 = resolve_relative_urls(md3, 'https://example.com/page.html')
    assert 'https://example.com/docs/api.html' in result3
    print('✓ resolve_relative_urls: root-relative URLs')

    # Anchors should be untouched
    md4 = 'Jump to [section](#overview).'
    result4 = resolve_relative_urls(md4, 'https://example.com/page.html')
    assert '#overview' in result4
    print('✓ resolve_relative_urls: anchors preserved')

    # Images
    md5 = 'Logo: ![logo](images/logo.png)'
    result5 = resolve_relative_urls(md5, 'https://example.com/page.html')
    assert 'https://example.com/images/logo.png' in result5
    print('✓ resolve_relative_urls: relative image URLs')

    # Empty base URL
    md6 = 'See [link](relative.html).'
    result6 = resolve_relative_urls(md6, '')
    assert 'relative.html' in result6  # unchanged
    print('✓ resolve_relative_urls: empty base URL is no-op')


def test_strip_links():
    md = 'Visit [the docs](https://docs.example.com) and ![img](logo.png) here.'
    result = strip_links(md)
    assert 'the docs' in result
    assert 'https://docs.example.com' not in result
    assert '![' not in result
    print('✓ strip_links: removes links and images')


def test_truncate_words():
    md = 'one two three four five six seven eight nine ten eleven'
    result = truncate_words(md, 5)
    assert result == 'one two three four five...'
    print('✓ truncate_words: truncates to N words')

    # Short text should be unchanged
    short = 'hello world'
    assert truncate_words(short, 10) == short
    print('✓ truncate_words: short text unchanged')


if __name__ == '__main__':
    test_resolve_relative_urls()
    test_strip_links()
    test_truncate_words()
    print('\nAll tests passed.')
