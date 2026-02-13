"""
Aperture Science Passe Parser Enrichment Center
================================================

"The Enrichment Center reminds you that the parse_script function
 will never threaten to stab you and, in fact, cannot speak."

These tests exercise the pure parse_script() function — no browser,
no WebSocket, no cake. Just text in, (verb, args) tuples out.

Test chambers are grouped by protocol: basic parsing, quoting semantics,
the raw-rest escape hatch, and edge cases that would make a lesser
parser question its own existence.
"""

import pytest

from passe.cli import parse_script


# ── Chamber 01: The Basics ────────────────────────────────
# "This is the part where I test you."


class TestBasicParsing:
    """Verify that simple, well-formed input produces correct output.
    Science isn't about WHY — it's about WHY NOT."""

    def test_single_verb_no_args(self):
        assert parse_script("back") == [("back", [])]

    def test_single_verb_one_arg(self):
        assert parse_script("goto https://example.com") == [
            ("goto", ["https://example.com"])
        ]

    def test_single_verb_two_args(self):
        assert parse_script("fill #email user@test.com") == [
            ("fill", ["#email", "user@test.com"])
        ]

    def test_multiple_lines(self):
        script = "goto https://example.com\nscreenshot /tmp/out.png"
        result = parse_script(script)
        assert result == [
            ("goto", ["https://example.com"]),
            ("screenshot", ["/tmp/out.png"]),
        ]

    def test_all_zero_arg_verbs(self):
        for verb in ("back", "forward", "wait-navigation"):
            assert parse_script(verb) == [(verb, [])]

    def test_verb_case_insensitive(self):
        """Verbs are lowercased. GOTO, Goto, gOtO — all the same to us."""
        assert parse_script("GOTO https://example.com") == [
            ("goto", ["https://example.com"])
        ]
        assert parse_script("Screenshot /tmp/x.png") == [
            ("screenshot", ["/tmp/x.png"])
        ]

    def test_wait_with_milliseconds(self):
        assert parse_script("wait 500") == [("wait", ["500"])]

    def test_wait_for_with_timeout(self):
        assert parse_script("wait-for .results 5000") == [
            ("wait-for", [".results", "5000"])
        ]

    def test_scroll_two_coords(self):
        assert parse_script("scroll 0 500") == [("scroll", ["0", "500"])]

    def test_viewport_dimensions(self):
        assert parse_script("viewport 1024 768") == [
            ("viewport", ["1024", "768"])
        ]

    def test_press_key_name(self):
        assert parse_script("press Enter") == [("press", ["Enter"])]


# ── Chamber 02: The Void ──────────────────────────────────
# "When the testing is over, you will be missed."


class TestEmptyAndComments:
    """Lines that produce nothing. Like promises about cake."""

    def test_empty_string(self):
        assert parse_script("") == []

    def test_only_whitespace(self):
        assert parse_script("   \n  \n\t\n") == []

    def test_comment_lines(self):
        assert parse_script("# this is a comment") == []

    def test_comments_with_leading_whitespace(self):
        assert parse_script("  # indented comment") == []

    def test_mixed_comments_and_verbs(self):
        script = """# Navigate to the test subject
goto https://example.com
# Take evidence
screenshot /tmp/out.png"""
        result = parse_script(script)
        assert result == [
            ("goto", ["https://example.com"]),
            ("screenshot", ["/tmp/out.png"]),
        ]

    def test_blank_lines_between_verbs(self):
        script = "goto https://example.com\n\n\nscreenshot /tmp/out.png"
        result = parse_script(script)
        assert len(result) == 2


# ── Chamber 03: The Quoting Gauntlet ─────────────────────
# "Speedy thing goes in, speedy thing comes out."


class TestShlexQuoting:
    """Standard verbs use shlex. Quotes matter. Aperture Science
    is not responsible for any injuries sustained during quoting."""

    def test_quoted_selector_with_spaces(self):
        """click-text needs quoted labels with spaces."""
        result = parse_script('click-text "Accept Cookies"')
        assert result == [("click-text", ["Accept Cookies"])]

    def test_single_quoted_selector(self):
        result = parse_script("click-text 'Reject All'")
        assert result == [("click-text", ["Reject All"])]

    def test_quoted_css_selector(self):
        result = parse_script('''click "div.modal > button:nth-of-type(2)"''')
        assert result == [("click", ["div.modal > button:nth-of-type(2)"])]

    def test_type_selector_and_text(self):
        """type needs two args: selector and text. Both can be quoted."""
        result = parse_script('type "#search" "hello world"')
        assert result == [("type", ["#search", "hello world"])]

    def test_fill_with_quoted_value(self):
        result = parse_script('fill "input[name=email]" "test@example.com"')
        assert result == [("fill", ["input[name=email]", "test@example.com"])]

    def test_url_with_query_params(self):
        """URLs have &, =, ? — shlex should handle these without quotes."""
        url = "https://example.com/search?q=test&page=1"
        result = parse_script(f"goto {url}")
        assert result == [("goto", [url])]

    def test_selector_with_attribute_brackets(self):
        result = parse_script('click input[name="email"]')
        assert result == [("click", ['input[name=email]'])]

    def test_shlex_fallback_on_unmatched_quotes(self):
        """Unmatched quotes trigger ValueError fallback to str.split().
        We don't crash. We never crash. That's not a protocol."""
        result = parse_script("click it's-fine")
        assert result == [("click", ["it's-fine"])]


# ── Chamber 04: The Raw Rest Escape Hatch ─────────────────
# "This next test is impossible. Make no attempt to solve it."


class TestRawRestVerbs:
    """eval, assert, log take the raw rest-of-line. No shlex.
    This is the fix for the JS-quotes-getting-stripped bug.
    The previous parser was... unsatisfactory."""

    def test_eval_preserves_js_quotes(self):
        """THE critical regression test. shlex would turn "h1" into h1,
        making V8 look for a variable instead of a string literal."""
        result = parse_script('eval document.querySelector("h1").textContent')
        assert result == [
            ("eval", ['document.querySelector("h1").textContent'])
        ]

    def test_eval_preserves_single_quotes(self):
        result = parse_script("eval document.querySelector('h1').textContent")
        assert result == [
            ("eval", ["document.querySelector('h1').textContent"])
        ]

    def test_eval_preserves_template_literals(self):
        result = parse_script("eval `${1 + 2}`")
        assert result == [("eval", ["`${1 + 2}`"])]

    def test_eval_preserves_json_stringify(self):
        expr = 'JSON.stringify({"key": "value"})'
        result = parse_script(f"eval {expr}")
        assert result == [("eval", [expr])]

    def test_eval_complex_expression(self):
        expr = 'Array.from(document.querySelectorAll("a")).map(a => a.href).join("\\n")'
        result = parse_script(f"eval {expr}")
        assert result == [("eval", [expr])]

    def test_eval_no_args(self):
        result = parse_script("eval")
        assert result == [("eval", [])]

    def test_assert_preserves_js(self):
        result = parse_script('assert document.title === "Expected Title"')
        assert result == [
            ("assert", ['document.title === "Expected Title"'])
        ]

    def test_assert_comparison_operators(self):
        result = parse_script("assert document.querySelectorAll('li').length > 5")
        assert result == [
            ("assert", ["document.querySelectorAll('li').length > 5"])
        ]

    def test_log_preserves_message(self):
        result = parse_script('log Step 1: navigating to "the page"')
        assert result == [("log", ['Step 1: navigating to "the page"'])]

    def test_log_with_special_chars(self):
        result = parse_script("log Testing with $pecial & <chars>")
        assert result == [("log", ["Testing with $pecial & <chars>"])]


# ── Chamber 05: eval-to — The Hybrid ─────────────────────
# "Two plus two is... ten. IN BASE FOUR! I'M FINE!"


class TestEvalTo:
    """eval-to takes a shlex'd path then raw-rest expression.
    First arg is a path. Everything after is JS. No exceptions."""

    def test_path_and_expression(self):
        result = parse_script('eval-to /tmp/out.txt document.title')
        assert result == [("eval-to", ["/tmp/out.txt", "document.title"])]

    def test_expression_with_js_quotes(self):
        result = parse_script(
            'eval-to /tmp/data.json JSON.stringify({"key": "value"})'
        )
        assert result == [
            ("eval-to", ["/tmp/data.json", 'JSON.stringify({"key": "value"})'])
        ]

    def test_path_only_no_expression(self):
        result = parse_script("eval-to /tmp/out.txt")
        assert result == [("eval-to", ["/tmp/out.txt"])]

    def test_no_args(self):
        result = parse_script("eval-to")
        assert result == [("eval-to", [])]

    def test_complex_expression_after_path(self):
        expr = 'Array.from(document.querySelectorAll("a")).map(a => a.href)'
        result = parse_script(f"eval-to /tmp/links.json {expr}")
        assert result == [("eval-to", ["/tmp/links.json", expr])]


# ── Chamber 06: Real Scripts ──────────────────────────────
# "Remember, the Aperture Science 'Bring Your Daughter to
#  Work Day' is the perfect time to have her tested."


class TestRealWorldScripts:
    """Full scripts as they'd be written. Integration-level parsing
    without the integration. Like testing a gun turret without bullets."""

    def test_scout_then_act(self):
        """The canonical passe pattern: discover then interact."""
        script = """goto https://example.com
snapshot /tmp/elements.txt"""
        result = parse_script(script)
        assert result == [
            ("goto", ["https://example.com"]),
            ("snapshot", ["/tmp/elements.txt"]),
        ]

    def test_cookie_banner_flow(self):
        script = """goto https://example.com
click-text "Reject"
wait 500
screenshot /tmp/after-cookies.png"""
        result = parse_script(script)
        assert len(result) == 4
        assert result[0] == ("goto", ["https://example.com"])
        assert result[1] == ("click-text", ["Reject"])
        assert result[2] == ("wait", ["500"])
        assert result[3] == ("screenshot", ["/tmp/after-cookies.png"])

    def test_form_fill_flow(self):
        script = """goto https://example.com/login
type "input[name='email']" "test@example.com"
type "input[name='password']" "hunter2"
click "#submit"
wait-for .dashboard 15000
screenshot /tmp/logged-in.png"""
        result = parse_script(script)
        assert len(result) == 6
        assert result[1] == ("type", ["input[name='email']", "test@example.com"])
        assert result[2] == ("type", ["input[name='password']", "hunter2"])
        assert result[4] == ("wait-for", [".dashboard", "15000"])

    def test_inline_semicolon_converted(self):
        """cmd_run converts semicolons to newlines before parse_script.
        parse_script itself sees newlines. Verify it handles the result."""
        # Simulate what cmd_run does: replace ; with \n
        inline = "goto https://example.com; screenshot /tmp/out.png"
        text = inline.replace(";", "\n")
        result = parse_script(text)
        assert result == [
            ("goto", ["https://example.com"]),
            ("screenshot", ["/tmp/out.png"]),
        ]

    def test_script_with_eval_and_assert(self):
        """Mixed standard and raw-rest verbs in one script."""
        script = """goto https://example.com
eval document.querySelector("h1").textContent
assert document.title !== ""
log All tests passed for "example.com"
screenshot /tmp/final.png"""
        result = parse_script(script)
        assert len(result) == 5
        assert result[1] == ("eval", ['document.querySelector("h1").textContent'])
        assert result[2] == ("assert", ['document.title !== ""'])
        assert result[3] == ("log", ['All tests passed for "example.com"'])

    def test_screenshot_viewport_flag(self):
        result = parse_script("screenshot /tmp/out.png --viewport")
        assert result == [("screenshot", ["/tmp/out.png", "--viewport"])]

    def test_screenshot_viewport_only(self):
        result = parse_script("screenshot --viewport")
        assert result == [("screenshot", ["--viewport"])]


# ── Chamber 07: Edge Cases ────────────────────────────────
# "I'm not even angry. I'm being so sincere right now."


class TestEdgeCases:
    """The kind of input that makes you wonder if the test subject
    is even trying. Spoiler: they aren't."""

    def test_leading_whitespace_stripped(self):
        result = parse_script("   goto https://example.com")
        assert result == [("goto", ["https://example.com"])]

    def test_trailing_whitespace_ignored(self):
        result = parse_script("goto https://example.com   ")
        assert result == [("goto", ["https://example.com"])]

    def test_tab_indentation(self):
        result = parse_script("\tgoto https://example.com")
        assert result == [("goto", ["https://example.com"])]

    def test_multiple_spaces_between_args(self):
        """shlex handles multiple spaces. It's not picky. Unlike me."""
        result = parse_script('type   "#email"   "test@test.com"')
        assert result == [("type", ["#email", "test@test.com"])]

    def test_unknown_verb_still_parsed(self):
        """parse_script doesn't validate verbs — that's run_script's job.
        Separation of concerns. A concept lost on most test subjects."""
        result = parse_script("defenestrate window")
        assert result == [("defenestrate", ["window"])]

    def test_verb_only_no_trailing_space(self):
        result = parse_script("back")
        assert result == [("back", [])]

    def test_click_if_css_selector(self):
        result = parse_script('click-if ".cookie-banner .dismiss"')
        assert result == [("click-if", [".cookie-banner .dismiss"])]

    def test_hover_selector(self):
        result = parse_script('hover "nav > a:first-child"')
        assert result == [("hover", ["nav > a:first-child"])]

    def test_select_dropdown(self):
        result = parse_script('select "#country" "GB"')
        assert result == [("select", ["#country", "GB"])]

    def test_read_with_path(self):
        result = parse_script("read /tmp/article.md")
        assert result == [("read", ["/tmp/article.md"])]

    def test_read_no_path(self):
        result = parse_script("read")
        assert result == [("read", [])]

    def test_snapshot_no_path(self):
        result = parse_script("snapshot")
        assert result == [("snapshot", [])]

    def test_eval_with_parentheses_and_dots(self):
        """JS expressions have more punctuation than a passive-aggressive
        email. Make sure none of it gets mangled."""
        expr = "window.performance.getEntriesByType('navigation')[0].loadEventEnd"
        result = parse_script(f"eval {expr}")
        assert result == [("eval", [expr])]

    def test_very_long_line(self):
        long_url = "https://example.com/" + "a" * 2000
        result = parse_script(f"goto {long_url}")
        assert result == [("goto", [long_url])]


# ── Chamber 08: Regression Vault ──────────────────────────
# "Did you know you can donate one or all of your vital organs
#  to the Aperture Science Self-Esteem Fund for Girls?"


class TestRegressions:
    """Specific bugs that were found and fixed. Each test is a scar.
    We keep them so nobody forgets."""

    def test_shlex_strips_js_quotes_in_eval(self):
        """THE original bug. If eval went through shlex:
          eval document.querySelector("h1")
        shlex sees "h1" as a quoted string → strips quotes → h1
        V8 then interprets h1 as a variable → ReferenceError.

        This test exists because someone shipped a parser that
        treated JavaScript like shell arguments. We do not speak
        of that parser."""
        result = parse_script('eval document.querySelector("h1")')
        verb, args = result[0]
        assert verb == "eval"
        # The quotes MUST survive
        assert '"h1"' in args[0]

    def test_shlex_strips_nested_quotes_in_assert(self):
        """Same bug, assert variant."""
        result = parse_script('assert document.title === "My Page"')
        verb, args = result[0]
        assert '"My Page"' in args[0]

    def test_log_quotes_survive(self):
        """And log."""
        result = parse_script('log Clicked on "Submit" button')
        verb, args = result[0]
        assert '"Submit"' in args[0]

    def test_eval_to_expression_quotes_survive(self):
        """eval-to's expression portion is also raw."""
        result = parse_script('eval-to /tmp/out.txt document.querySelector("h1").textContent')
        verb, args = result[0]
        assert args[0] == "/tmp/out.txt"
        assert '"h1"' in args[1]

    def test_semicolon_in_js_expression(self):
        """Semicolons in JS expressions within eval shouldn't break.
        cmd_run does semicolon→newline for inline mode, but parse_script
        sees the text AFTER that transform. If you're passing raw text
        with semicolons to parse_script, they're part of the expression."""
        result = parse_script('eval var x = 1; x + 1')
        # This is a single eval with the full raw rest
        assert result == [("eval", ["var x = 1; x + 1"])]
