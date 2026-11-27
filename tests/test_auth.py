"""
Unit tests for max_library.auth (browser extraction, phone login, and .env storage).
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from max_library import MaxClient, auth
from max_library.auth.browser import (
    BrowserTokenResult,
    _scan_leveldb_dir,
    extract_token_from_browser,
    get_browser_search_paths,
)
from max_library.auth.phone import login_by_phone, verify_token
from max_library.auth.qr import login_by_qr, render_qr_ascii
from max_library.auth.storage import save_token_to_env
from max_library.models.user import User


def test_browser_search_paths():
    paths = get_browser_search_paths()
    assert isinstance(paths, dict)
    assert "Chrome" in paths
    assert "Yandex" in paths
    assert "Edge" in paths


def test_scan_leveldb_dir_structured_json(tmp_path):
    ldb_dir = tmp_path / "leveldb"
    ldb_dir.mkdir()
    sample_ldb = ldb_dir / "000100.ldb"

    dummy_token = "An_" + "A" * 350
    content = f'some_prefix_{{"viewerId":12345678,"token":"{dummy_token}"}}_some_suffix'.encode("utf-8")
    sample_ldb.write_bytes(content)

    res = _scan_leveldb_dir(str(ldb_dir), "TestBrowser", "Default")
    assert res is not None
    assert isinstance(res, BrowserTokenResult)
    assert res.token == dummy_token
    assert res.viewer_id == 12345678
    assert res.browser == "TestBrowser"
    assert res.profile == "Default"


def test_scan_leveldb_dir_raw_auth_pattern(tmp_path):
    ldb_dir = tmp_path / "leveldb"
    ldb_dir.mkdir()
    sample_log = ldb_dir / "000101.log"

    dummy_token = "An_" + "B" * 350
    content = b'header_web.max.ru_key___oneme_auth_data_"' + dummy_token.encode("utf-8") + b'"_tail'
    sample_log.write_bytes(content)

    res = _scan_leveldb_dir(str(ldb_dir), "TestBrowser", "Profile 1")
    assert res is not None
    assert res.token == dummy_token
    assert res.browser == "TestBrowser"
    assert res.profile == "Profile 1"


def test_scan_leveldb_dir_not_found(tmp_path):
    ldb_dir = tmp_path / "empty_leveldb"
    ldb_dir.mkdir()
    (ldb_dir / "000001.ldb").write_bytes(b"nothing interesting here")

    res = _scan_leveldb_dir(str(ldb_dir), "Chrome", "Default")
    assert res is None


def test_save_token_to_env(tmp_path):
    env_file = tmp_path / ".env"

    # 1. Create fresh .env
    token1 = "An_Token_111111111"
    assert save_token_to_env(token1, str(env_file)) is True
    assert f"MAX_TOKEN={token1}" in env_file.read_text(encoding="utf-8")

    # 2. Update existing .env and preserve other lines
    env_file.write_text(
        f"# Header comment\nOTHER_VAR=123\nMAX_TOKEN={token1}\n# Footer comment\n",
        encoding="utf-8",
    )
    token2 = "An_Token_222222222"
    assert save_token_to_env(token2, str(env_file)) is True

    updated_content = env_file.read_text(encoding="utf-8")
    assert "# Header comment" in updated_content
    assert "OTHER_VAR=123" in updated_content
    assert f"MAX_TOKEN={token2}" in updated_content
    assert "# Footer comment" in updated_content
    assert token1 not in updated_content


@pytest.mark.asyncio
async def test_verify_token_success():
    with patch("max_library.client.MaxTransport") as mock_transport_cls:
        mock_transport = MagicMock()
        mock_transport.connect = AsyncMock()
        mock_transport.close = AsyncMock()
        mock_transport.send_request = AsyncMock(
            side_effect=[
                {"opcode": 6, "payload": {}},  # Handshake
                {
                    "opcode": 19,
                    "payload": {
                        "profile": {
                            "id": 55555,
                            "name": "Тестовый Пользователь",
                            "phone": "+79991234567",
                        }
                    },
                },  # Init session
            ]
        )
        mock_transport_cls.return_value = mock_transport

        user = await verify_token("An_FakeToken123")
        assert user is not None
        assert isinstance(user, User)
        assert user.id == 55555
        assert user.display_name == "Тестовый Пользователь"


@pytest.mark.asyncio
async def test_verify_token_invalid():
    with patch("max_library.client.MaxTransport") as mock_transport_cls:
        mock_transport = MagicMock()
        mock_transport.connect = AsyncMock()
        mock_transport.close = AsyncMock()
        mock_transport.send_request = AsyncMock(
            side_effect=[
                {"opcode": 6, "payload": {}},
                {"opcode": 19, "payload": {}},  # No profile
            ]
        )
        mock_transport_cls.return_value = mock_transport

        user = await verify_token("An_InvalidToken")
        assert user is None


@pytest.mark.asyncio
async def test_login_by_phone_flow():
    with patch("max_library.auth.phone.MaxTransport") as mock_transport_cls:
        mock_transport = MagicMock()
        mock_transport.connect = AsyncMock()
        mock_transport.close = AsyncMock()
        mock_transport.send_request = AsyncMock(
            side_effect=[
                {"opcode": 6, "payload": {}},  # Handshake
                {"opcode": 17, "payload": {"token": "temp_auth_token_999"}},  # Opcode 17 START_AUTH
                {
                    "opcode": 18,
                    "payload": {
                        "tokenAttrs": {"LOGIN": {"token": "An_RealFinalLoginToken_888"}},
                        "profile": {
                            "id": 77777,
                            "name": "Алексей",
                            "phone": "+79991234567",
                        },
                    },
                },  # Opcode 18 CHECK_CODE
            ]
        )
        mock_transport_cls.return_value = mock_transport

        async def dummy_code():
            return "123456"

        token, user = await login_by_phone("+79991234567", code_callback=dummy_code)
        assert token == "An_RealFinalLoginToken_888"
        assert user.id == 77777
        assert user.display_name == "Алексей"


def test_max_client_classmethods(monkeypatch, tmp_path):
    dummy_res = BrowserTokenResult(
        token="An_BrowserToken123",
        viewer_id=123,
        browser="Chrome",
        profile="Default",
        source_file="test.ldb",
    )
    monkeypatch.setattr(
        "max_library.auth.browser.extract_token_from_browser",
        lambda **kwargs: dummy_res,
    )

    token = MaxClient.get_token_from_browser()
    assert token == "An_BrowserToken123"

    env_file = tmp_path / ".env"
    client = MaxClient.from_browser(auto_save_env=True, env_file_path=str(env_file))
    assert isinstance(client, MaxClient)
    assert client.token == "An_BrowserToken123"
    assert "MAX_TOKEN=An_BrowserToken123" in env_file.read_text(encoding="utf-8")


def test_render_qr_ascii():
    ascii_art = render_qr_ascii("https://max.ru/:auth/test-track-123")
    assert isinstance(ascii_art, str)
    assert len(ascii_art) > 50


@pytest.mark.asyncio
async def test_login_by_qr_flow():
    with patch("max_library.auth.qr.MaxTransport") as mock_transport_cls:
        mock_transport = MagicMock()
        mock_transport.connect = AsyncMock()
        mock_transport.close = AsyncMock()
        mock_transport.send_request = AsyncMock(
            side_effect=[
                {"opcode": 6, "payload": {}},  # Handshake
                {
                    "opcode": 288,
                    "payload": {
                        "trackId": "track-uuid-123",
                        "qrLink": "https://max.ru/:auth/track-uuid-123",
                        "ttl": 120000,
                        "pollingInterval": 50,  # fast for testing
                    },
                },  # Opcode 288
                {
                    "opcode": 289,
                    "payload": {"status": {"loginAvailable": True}},
                },  # Opcode 289
                {
                    "opcode": 291,
                    "payload": {
                        "tokenAttrs": {"LOGIN": {"token": "An_QRLoginToken_999"}},
                        "profile": {
                            "id": 99999,
                            "name": "QR User",
                            "phone": "+79998887766",
                        },
                    },
                },  # Opcode 291
            ]
        )
        mock_transport_cls.return_value = mock_transport

        qr_links_received = []

        def on_qr(link, track_id):
            qr_links_received.append((link, track_id))

        token, user = await login_by_qr(qr_callback=on_qr, timeout=5.0)
        assert token == "An_QRLoginToken_999"
        assert user.id == 99999
        assert user.display_name == "QR User"
        assert len(qr_links_received) == 1
        assert qr_links_received[0] == ("https://max.ru/:auth/track-uuid-123", "track-uuid-123")


@pytest.mark.asyncio
async def test_login_by_qr_with_2fa():
    with patch("max_library.auth.qr.MaxTransport") as mock_transport_cls:
        mock_transport = MagicMock()
        mock_transport.connect = AsyncMock()
        mock_transport.close = AsyncMock()
        mock_transport.send_request = AsyncMock(
            side_effect=[
                {"opcode": 6, "payload": {}},  # Handshake
                {
                    "opcode": 288,
                    "payload": {
                        "trackId": "track-uuid-2fa",
                        "qrLink": "https://max.ru/:auth/track-uuid-2fa",
                        "ttl": 120000,
                        "pollingInterval": 50,
                    },
                },  # Opcode 288
                {
                    "opcode": 289,
                    "payload": {"status": {"loginAvailable": True}},
                },  # Opcode 289
                {
                    "opcode": 291,
                    "payload": {
                        "passwordChallenge": {"trackId": "track-uuid-2fa"},
                    },
                },  # Opcode 291 (requests 2FA)
                {
                    "opcode": 101,
                    "payload": {
                        "tokenAttrs": {"LOGIN": {"token": "An_QRToken_2FA_Passed"}},
                        "profile": {
                            "id": 88888,
                            "name": "2FA User",
                            "phone": "+79991112233",
                        },
                    },
                },  # Opcode 101 (password check)
            ]
        )
        mock_transport_cls.return_value = mock_transport

        token, user = await login_by_qr(
            qr_callback=lambda l, t: None,
            password_callback=lambda: "my_secret_2fa",
            timeout=5.0,
        )
        assert token == "An_QRToken_2FA_Passed"
        assert user.id == 88888
        assert user.display_name == "2FA User"


@pytest.mark.asyncio
async def test_max_client_from_qr(tmp_path):
    with patch("max_library.auth.qr.login_by_qr") as mock_login_qr:
        mock_login_qr.return_value = (
            "An_ClientQRToken123",
            User.model_validate({"id": 111, "name": "FromQR User"}),
        )

        env_file = tmp_path / ".env"
        client = await MaxClient.from_qr(auto_save_env=True, env_file_path=str(env_file))
        assert isinstance(client, MaxClient)
        assert client.token == "An_ClientQRToken123"
        assert client.me.display_name == "FromQR User"
        assert "MAX_TOKEN=An_ClientQRToken123" in env_file.read_text(encoding="utf-8")

