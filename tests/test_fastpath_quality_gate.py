"""Tests for fastpath.py quality gate and detection functions.

Each detector in the quality gate is a pure function (text/HTML in,
bool/score out), making them straightforward to unit test. Regressions
here affect whether ~87% of fetches skip Chrome or not — false
negatives waste Chrome launches, false positives serve bad content.
"""

import json

import pytest

from passe.fastpath import (
    QUALITY_THRESHOLD,
    MIN_WORDS,
    SUSPICIOUS_WORDS,
    _count_words,
    _stop_words_ratio,
    _link_density,
    _detect_captcha,
    _detect_paywall,
    _detect_spa_shell,
    _try_next_data,
    _extract_text_from_props,
    _count_html_elements,
    quality_gate,
)


# ---------------------------------------------------------------------------
# _count_words
# ---------------------------------------------------------------------------

class TestCountWords:
    def test_simple_sentence(self):
        assert _count_words('hello world foo bar') == 4

    def test_empty_string(self):
        assert _count_words('') == 0

    def test_markdown_formatting(self):
        # Markdown symbols like # and * shouldn't count as words
        assert _count_words('# Hello **world**') == 2

    def test_hyphenated_words(self):
        # "well-known" has two word chars separated by hyphen
        assert _count_words('well-known pattern') == 3

    def test_numbers_count_as_words(self):
        assert _count_words('there are 42 items') == 4


# ---------------------------------------------------------------------------
# _stop_words_ratio
# ---------------------------------------------------------------------------

class TestStopWordsRatio:
    def test_all_stop_words(self):
        ratio = _stop_words_ratio('the and of to in that is')
        assert ratio > 0.8

    def test_technical_content(self):
        # Technical/code content should have low stop-word ratio
        ratio = _stop_words_ratio(
            'kubectl apply deployment nginx replicas selector matchLabels'
        )
        assert ratio < 0.15

    def test_natural_prose(self):
        # Sentences heavy with function words score high
        ratio = _stop_words_ratio(
            'The company said that it would not be able to make the changes '
            'that were needed for the new product to work as expected'
        )
        assert ratio > 0.40

    def test_empty_string(self):
        assert _stop_words_ratio('') == 0.0


# ---------------------------------------------------------------------------
# _link_density
# ---------------------------------------------------------------------------

class TestLinkDensity:
    def test_no_links(self):
        html = '<p>This is plain text content without any links at all.</p>'
        assert _link_density(html) == 0.0

    def test_all_links(self):
        html = '<a href="/foo">This is all link text</a>'
        density = _link_density(html)
        assert density > 0.9

    def test_nav_heavy_page(self):
        # A page dominated by navigation links
        links = ''.join(f'<a href="/{i}">Link {i}</a> ' for i in range(20))
        html = f'<nav>{links}</nav><p>Short body.</p>'
        density = _link_density(html)
        assert density > 0.5

    def test_article_with_some_links(self):
        body = '<p>' + ' '.join(['word'] * 100) + '</p>'
        link = '<a href="/ref">reference link</a>'
        html = body + link
        density = _link_density(html)
        assert density < 0.1

    def test_empty_html(self):
        assert _link_density('') == 0.0


# ---------------------------------------------------------------------------
# _detect_captcha
# ---------------------------------------------------------------------------

class TestDetectCaptcha:
    def test_cloudflare_challenge(self):
        html = '''<html><head></head><body>
        <div class="challenge-running">
            <div id="cf-challenge">Checking your browser...</div>
        </div>
        </body></html>'''
        assert _detect_captcha(html) is True

    def test_recaptcha_page(self):
        html = '''<html><body>
        <div class="g-recaptcha" data-sitekey="abc"></div>
        <p>Please verify you are human.</p>
        </body></html>'''
        assert _detect_captcha(html) is True

    def test_hcaptcha_page(self):
        html = '''<html><body>
        <div class="hcaptcha">Verify</div>
        </body></html>'''
        assert _detect_captcha(html) is True

    def test_turnstile_page(self):
        html = '''<html><body>
        <div class="cf-turnstile">Loading...</div>
        </body></html>'''
        assert _detect_captcha(html) is True

    def test_normal_page_not_flagged(self):
        body_text = ' '.join(['content'] * 200)
        html = f'<html><body><p>{body_text}</p></body></html>'
        assert _detect_captcha(html) is False

    def test_captcha_keyword_in_long_page_not_flagged(self):
        # A real article mentioning CAPTCHAs shouldn't trigger detection.
        # The check requires visible text < 2000 chars.
        body_text = ' '.join(['word'] * 500)
        html = f'''<html><body>
        <p>{body_text}</p>
        <p>We use recaptcha to prevent abuse.</p>
        </body></html>'''
        assert _detect_captcha(html) is False

    def test_captcha_in_script_tag_not_flagged(self):
        # CAPTCHA patterns inside <script> should be stripped before checking
        html = '''<html><body>
        <script>var config = {captcha: "g-recaptcha", key: "abc"};</script>
        <p>''' + ' '.join(['Normal content'] * 100) + '''</p>
        </body></html>'''
        assert _detect_captcha(html) is False

    def test_ddos_protection_page(self):
        html = '''<html><body>
        <div class="ddos-protection">DDoS protection by Cloudflare</div>
        </body></html>'''
        assert _detect_captcha(html) is True

    def test_no_body_tag(self):
        html = '<html><head><title>Test</title></head></html>'
        assert _detect_captcha(html) is False


# ---------------------------------------------------------------------------
# _detect_paywall
# ---------------------------------------------------------------------------

class TestDetectPaywall:
    def test_subscribe_to_read(self):
        assert _detect_paywall('Subscribe to read the full article') is True

    def test_subscribe_to_continue(self):
        assert _detect_paywall('Subscribe to continue reading') is True

    def test_premium_content(self):
        assert _detect_paywall('This is premium content') is True

    def test_members_only(self):
        assert _detect_paywall('This article is for members only') is True

    def test_member_only_singular(self):
        assert _detect_paywall('Member only access required') is True

    def test_sign_in_to_read(self):
        assert _detect_paywall('Sign in to read this article') is True

    def test_sign_in_to_continue(self):
        assert _detect_paywall('Please sign in to continue') is True

    def test_create_free_account(self):
        assert _detect_paywall('Create a free account to access') is True

    def test_create_free_account_no_article(self):
        assert _detect_paywall('Create free account now') is True

    def test_already_subscriber(self):
        assert _detect_paywall('Already a subscriber? Log in') is True

    def test_already_member(self):
        assert _detect_paywall('Already a member? Sign in here') is True

    def test_unlock_article(self):
        assert _detect_paywall('Unlock this article with a subscription') is True

    def test_unlock_full_story(self):
        assert _detect_paywall('Unlock full story') is True

    def test_sign_in_to_view(self):
        assert _detect_paywall('Sign in to view this content') is True

    def test_normal_content(self):
        assert _detect_paywall(
            'The company reported strong quarterly earnings yesterday'
        ) is False

    def test_case_insensitive(self):
        assert _detect_paywall('SUBSCRIBE TO READ MORE') is True


# ---------------------------------------------------------------------------
# _detect_spa_shell
# ---------------------------------------------------------------------------

class TestDetectSpaShell:
    def test_react_spa(self):
        html = '<html><body><div id="root"></div></body></html>'
        result = _detect_spa_shell(html)
        assert result is not None
        assert 'React' in result

    def test_vue_spa(self):
        html = '<html><body><div id="app"></div></body></html>'
        result = _detect_spa_shell(html)
        assert result is not None
        assert 'Vue' in result

    def test_angular_spa(self):
        html = '<html><body><app-root></app-root></body></html>'
        result = _detect_spa_shell(html)
        assert result is not None
        assert 'Angular' in result

    def test_nextjs_spa(self):
        html = '<html><body><div id="__next"></div></body></html>'
        result = _detect_spa_shell(html)
        assert result is not None
        assert 'Next.js' in result

    def test_react_with_content_not_flagged(self):
        # If the div#root has substantial content, it's server-rendered
        body_text = ' '.join(['content'] * 100)
        html = f'<html><body><div id="root"><p>{body_text}</p></div></body></html>'
        assert _detect_spa_shell(html) is None

    def test_normal_page(self):
        html = '<html><body><div id="content"><p>Hello world</p></div></body></html>'
        assert _detect_spa_shell(html) is None

    def test_no_body(self):
        html = '<html><head><title>Test</title></head></html>'
        # No body means the body text check won't match, should return None
        assert _detect_spa_shell(html) is None


# ---------------------------------------------------------------------------
# _try_next_data
# ---------------------------------------------------------------------------

class TestTryNextData:
    def _wrap_next_data(self, data: dict) -> str:
        """Wrap data in a __NEXT_DATA__ script tag within an HTML page."""
        return (
            '<html><body>'
            f'<script id="__NEXT_DATA__" type="application/json">'
            f'{json.dumps(data)}'
            '</script>'
            '</body></html>'
        )

    def test_extracts_content_field(self):
        data = {
            'props': {
                'pageProps': {
                    'content': 'A' * 200  # >100 chars
                }
            }
        }
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        assert result == 'A' * 200

    def test_extracts_body_field(self):
        data = {
            'props': {
                'pageProps': {
                    'body': 'B' * 200
                }
            }
        }
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        assert result == 'B' * 200

    def test_extracts_article_field(self):
        data = {
            'props': {
                'pageProps': {
                    'article': 'C' * 200
                }
            }
        }
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        assert result == 'C' * 200

    def test_extracts_markdown_body_field(self):
        data = {
            'props': {
                'pageProps': {
                    'markdownBody': 'D' * 200
                }
            }
        }
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        assert result == 'D' * 200

    def test_extracts_html_field(self):
        data = {
            'props': {
                'pageProps': {
                    'html': '<p>' + 'E' * 200 + '</p>'
                }
            }
        }
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        assert result == '<p>' + 'E' * 200 + '</p>'

    def test_short_content_ignored(self):
        data = {
            'props': {
                'pageProps': {
                    'content': 'too short'  # <100 chars
                }
            }
        }
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        # Should fall through to recursive extraction
        assert result is None

    def test_no_page_props(self):
        data = {'props': {}}
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        assert result is None

    def test_invalid_json(self):
        html = (
            '<html><body>'
            '<script id="__NEXT_DATA__" type="application/json">'
            '{invalid json here}'
            '</script>'
            '</body></html>'
        )
        assert _try_next_data(html, 'https://example.com') is None

    def test_no_next_data_tag(self):
        html = '<html><body><p>Normal page</p></body></html>'
        assert _try_next_data(html, 'https://example.com') is None

    def test_recursive_text_extraction(self):
        # When no named field matches, tries recursive extraction
        long_text = 'This is a substantial piece of text with enough words ' * 5
        data = {
            'props': {
                'pageProps': {
                    'sections': [
                        {'paragraph': long_text},
                        {'paragraph': long_text},
                    ]
                }
            }
        }
        result = _try_next_data(self._wrap_next_data(data), 'https://example.com')
        assert result is not None
        assert long_text.strip() in result


# ---------------------------------------------------------------------------
# _extract_text_from_props
# ---------------------------------------------------------------------------

class TestExtractTextFromProps:
    def test_short_strings_excluded(self):
        # Strings <50 chars or without spaces are excluded (IDs, dates)
        result = _extract_text_from_props({'id': 'abc123', 'date': '2026-01-01'})
        assert result == []

    def test_long_strings_included(self):
        long = 'This is a substantial piece of text that should be included in the output'
        result = _extract_text_from_props({'content': long})
        assert long in result

    def test_depth_limit(self):
        # Should not recurse deeper than 5 levels
        nested = {'a': {'b': {'c': {'d': {'e': {'f': 'deep ' * 20}}}}}}
        result = _extract_text_from_props(nested)
        assert result == []

    def test_list_extraction(self):
        long = 'This is paragraph one with enough words to pass the threshold'
        result = _extract_text_from_props([long])
        assert long in result


# ---------------------------------------------------------------------------
# _count_html_elements
# ---------------------------------------------------------------------------

class TestCountHtmlElements:
    def test_count_tables(self):
        html = '<table><tr><td>1</td></tr></table><table><tr><td>2</td></tr></table>'
        assert _count_html_elements(html, 'table') == 2

    def test_count_pre(self):
        html = '<pre>code1</pre><pre>code2</pre><pre>code3</pre>'
        assert _count_html_elements(html, 'pre') == 3

    def test_no_matches(self):
        assert _count_html_elements('<p>hello</p>', 'table') == 0

    def test_case_insensitive(self):
        html = '<TABLE><tr><td>1</td></tr></TABLE>'
        assert _count_html_elements(html, 'table') == 1


# ---------------------------------------------------------------------------
# quality_gate (composite)
# ---------------------------------------------------------------------------

class TestQualityGate:
    def _make_html(self, body_content: str) -> str:
        return f'<html><body>{body_content}</body></html>'

    def test_good_article_passes(self):
        """A well-extracted article with natural prose should pass."""
        words = (
            'The company reported strong quarterly earnings yesterday. '
            'Revenue grew by twelve percent compared to the same period '
            'last year, driven by increased demand for cloud services. '
        ) * 10  # ~300 words of natural prose
        html = self._make_html(f'<p>{words}</p>')
        score, signals = quality_gate(words, html, 'https://example.com/article')
        assert score >= QUALITY_THRESHOLD
        assert signals['word_count'] >= 200

    def test_too_few_words_rejected(self):
        """Content below MIN_WORDS should be instantly rejected."""
        short = ' '.join(['word'] * (MIN_WORDS - 1))
        html = self._make_html(f'<p>{short}</p>')
        score, signals = quality_gate(short, html, 'https://example.com')
        assert score == 0.0
        assert signals['reject'] == 'too_few_words'

    def test_suspicious_word_count_penalised(self):
        """Content between MIN_WORDS and SUSPICIOUS_WORDS gets penalised."""
        medium = ' '.join(['word'] * (MIN_WORDS + 10))
        html = self._make_html(f'<p>{medium}</p>')
        score, signals = quality_gate(medium, html, 'https://example.com')
        assert 'word_penalty' in signals
        assert signals['word_penalty'] < 1.0

    def test_paywall_content_heavily_penalised(self):
        """Paywall text should drive the score well below threshold."""
        text = (
            'Subscribe to read the full article. Already a subscriber? '
            'Sign in to continue reading. This premium content is available '
            'to members only. ' + ' '.join(['filler'] * 100)
        )
        html = self._make_html(f'<p>{text}</p>')
        score, signals = quality_gate(text, html, 'https://example.com')
        assert signals.get('paywall_detected') is True
        assert score < QUALITY_THRESHOLD

    def test_high_link_density_penalised(self):
        """Pages dominated by links (nav pages, indexes) should be penalised."""
        links = ''.join(f'<a href="/{i}">Navigation link number {i} here</a> ' for i in range(50))
        html = self._make_html(links + '<p>Small body text.</p>')
        # The markdown from such a page would be mostly link text
        markdown = ' '.join(f'Navigation link number {i} here' for i in range(50))
        markdown += ' Small body text.'
        score, signals = quality_gate(markdown, html, 'https://example.com')
        assert signals['link_density'] > 0.33
        assert 'link_density_penalty' in signals

    def test_tables_lost_penalised(self):
        """If HTML has tables but markdown has none, penalise."""
        tables = '<table><tr><td>data</td></tr></table>' * 3
        body = '<p>' + ' '.join(['content'] * 100) + '</p>'
        html = self._make_html(tables + body)
        markdown = ' '.join(['content'] * 100)  # no markdown tables
        score, signals = quality_gate(markdown, html, 'https://example.com')
        assert signals.get('tables_lost') is True

    def test_code_blocks_lost_penalised(self):
        """If HTML has <pre> blocks but markdown has none, penalise."""
        pre_blocks = '<pre>code example</pre>' * 2
        body = '<p>' + ' '.join(['content'] * 100) + '</p>'
        html = self._make_html(pre_blocks + body)
        markdown = ' '.join(['content'] * 100)  # no code blocks
        score, signals = quality_gate(markdown, html, 'https://example.com')
        assert signals.get('code_blocks_lost') is True

    def test_tables_preserved_no_penalty(self):
        """If markdown has tables, no penalty even if HTML has them too."""
        tables = '<table><tr><td>data</td></tr></table>' * 3
        body = '<p>' + ' '.join(['content'] * 100) + '</p>'
        html = self._make_html(tables + body)
        markdown = '| col1 | col2 |\n| --- | --- |\n| data | data |\n' + ' '.join(['content'] * 100)
        score, signals = quality_gate(markdown, html, 'https://example.com')
        assert signals.get('tables_lost') is not True

    def test_low_text_to_html_ratio_penalised(self):
        """Very low text-to-HTML ratio suggests mostly boilerplate."""
        # Giant HTML with enough extracted words to pass MIN_WORDS
        filler_divs = '<div class="widget sidebar nav footer">' * 1000 + '</div>' * 1000
        words = ' '.join(['content'] * 60)  # >MIN_WORDS to avoid instant reject
        html = self._make_html(filler_divs + f'<p>{words}</p>')
        score, signals = quality_gate(words, html, 'https://example.com')
        assert signals['text_to_html_ratio'] < 0.02
        assert 'text_ratio_penalty' in signals

    def test_captcha_page_heavily_penalised(self):
        """CAPTCHA detection should drive score near zero."""
        html = '''<html><body>
        <div class="challenge-running">
            <div id="cf-challenge">Checking your browser</div>
        </div>
        </body></html>'''
        # Markdown from such a page would be minimal
        markdown = 'Checking your browser ' * 30
        score, signals = quality_gate(markdown, html, 'https://example.com')
        assert signals.get('captcha_detected') is True
        assert score < QUALITY_THRESHOLD

    def test_stop_words_penalty_only_for_short_content(self):
        """Stop words penalty should not apply to long content (>500 words)."""
        # Technical content with low stop words but >500 words
        technical = 'kubectl deployment replicas nginx selector ' * 120
        html = self._make_html(f'<p>{technical}</p>')
        score, signals = quality_gate(technical, html, 'https://example.com')
        assert signals.get('stop_words_penalty') is None

    def test_multiple_penalties_stack_multiplicatively(self):
        """A page hitting several penalties at once should score very low."""
        # Paywall text + high link density + CAPTCHA in a short page
        paywall_text = 'Subscribe to read the full article. '
        links = ''.join(f'<a href="/{i}">nav {i}</a>' for i in range(30))
        html = (
            '<html><body>'
            f'<div class="cf-turnstile">check</div>'
            f'{links}'
            f'<p>{paywall_text}</p>'
            '</body></html>'
        )
        markdown = paywall_text + ' '.join(f'nav {i}' for i in range(30))
        # Enough words to pass MIN_WORDS but everything else is bad
        markdown += ' filler content word ' * 10
        score, signals = quality_gate(markdown, html, 'https://example.com')
        assert score < QUALITY_THRESHOLD
        # Multiple penalty signals should be present
        penalty_count = sum(1 for k in signals if 'penalty' in k or 'detected' in k)
        assert penalty_count >= 2

    def test_score_always_between_zero_and_one(self):
        """Score should never exceed 1.0 or go below 0.0."""
        # Perfect content
        good = 'The quick brown fox jumps over the lazy dog. ' * 50
        html = self._make_html(f'<p>{good}</p>')
        score, _ = quality_gate(good, html, 'https://example.com')
        assert 0.0 <= score <= 1.0

        # Terrible content
        bad = 'x ' * MIN_WORDS
        html_bad = self._make_html(f'<p>{bad}</p>' + '<a href="/">link</a>' * 100)
        score_bad, _ = quality_gate(bad, html_bad, 'https://example.com')
        assert 0.0 <= score_bad <= 1.0
