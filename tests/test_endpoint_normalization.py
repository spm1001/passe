"""Scheme-less CDP endpoints normalize to http:// (passe-lesohu).

Users type `--cdp localhost:9223`; before normalization, urlparse read
'localhost' as the scheme and urlopen rejected the URL outright — and
passe's own error alternatives suggested the same broken form.
"""

import json
import os
from io import BytesIO
from unittest.mock import MagicMock, patch

import pytest

import passe.connection as conn
from passe.connection import _cdp_base_url, _normalize_endpoint, discover_chrome


class TestNormalizeEndpoint:
    def test_schemeless_gets_http(self):
        assert _normalize_endpoint('localhost:9223') == 'http://localhost:9223'

    def test_http_unchanged(self):
        assert _normalize_endpoint('http://localhost:9223') == 'http://localhost:9223'

    def test_https_unchanged(self):
        assert _normalize_endpoint('https://remote:9222') == 'https://remote:9222'

    def test_empty_unchanged(self):
        assert _normalize_endpoint('') == ''

    def test_bare_host_port_with_ip(self):
        assert _normalize_endpoint('100.124.115.49:9222') == 'http://100.124.115.49:9222'


class TestCdpBaseUrlNormalization:
    def test_schemeless_override(self):
        original = conn._cdp_override
        try:
            conn.set_cdp_override('localhost:9223')
            assert _cdp_base_url() == 'http://localhost:9223'
        finally:
            conn.set_cdp_override(original)

    def test_schemeless_env(self):
        original = conn._cdp_override
        try:
            conn.set_cdp_override(None)
            with patch.dict(os.environ, {'PASSE_CDP': 'localhost:9223'}):
                assert _cdp_base_url() == 'http://localhost:9223'
        finally:
            conn.set_cdp_override(original)

    def test_default_unchanged(self):
        original = conn._cdp_override
        try:
            conn.set_cdp_override(None)
            with patch.dict(os.environ, {'PASSE_CDP': ''}):
                assert _cdp_base_url() == 'http://localhost:9222'
        finally:
            conn.set_cdp_override(original)


class TestDiscoverChromeSchemeless:
    def test_schemeless_arg_connects_and_reports_loopback(self):
        version_json = json.dumps({
            'webSocketDebuggerUrl': 'ws://localhost:9223/devtools/browser/abc',
            'Browser': 'Chrome/150',
        }).encode()
        mock_resp = MagicMock()
        mock_resp.read.return_value = version_json
        mock_resp.__enter__ = MagicMock(return_value=mock_resp)
        mock_resp.__exit__ = MagicMock(return_value=False)
        with patch('passe.connection.urllib.request.urlopen',
                   return_value=mock_resp) as mock_open:
            ws_url, info = discover_chrome('localhost:9223')
        assert mock_open.call_args[0][0] == 'http://localhost:9223/json/version'
        assert info['cdp'] == 'http://localhost:9223'
        assert info['remote'] is False
        assert ws_url == 'ws://localhost:9223/devtools/browser/abc'


class TestLogStartSchemeless:
    def test_cmd_log_start_normalizes_before_preflight(self):
        from passe.log_lifecycle import cmd_log_start
        with patch('passe.log_lifecycle._check_chrome',
                   return_value=None) as mock_check:
            with pytest.raises(SystemExit):
                cmd_log_start([], cdp_url='localhost:9223')
        assert mock_check.call_args[0][0] == 'http://localhost:9223'
