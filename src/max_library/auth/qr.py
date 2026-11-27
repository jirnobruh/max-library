"""
QR Code authentication flow for MAX Messenger (web.max.ru / web.oneme.ru).
Provides programmatic and interactive CLI login via Opcode 288, 289, and 291.
Eliminates VK Captcha and SMS verification by using trusted mobile app confirmation.
"""

import asyncio
import getpass
import inspect
import logging
import time
from typing import Any, Awaitable, Callable, Optional, Union
from uuid import uuid4

from max_library.exceptions import AuthError, MaxAPIError, MaxClientError
from max_library.models.user import User
from max_library.transport.websocket import DEFAULT_WS_URL, MaxTransport

logger = logging.getLogger("max_library.auth")


def render_qr_ascii(data: str, border: int = 2) -> str:
    """
    Renders a URL as a high-contrast black-on-white QR code in the terminal.
    Uses ANSI background/foreground colors with Unicode half-blocks so that
    smartphone cameras can immediately scan it on both dark and light terminal themes.

    :param data: The text or URL to encode.
    :param border: Width of the quiet zone border in modules (default 2).
    :return: String representing the QR code in terminal ANSI format.
    """
    try:
        try:
            import colorama

            colorama.just_fix_windows_console()
        except Exception:
            pass

        import qrcode

        qr = qrcode.QRCode(border=border)
        qr.add_data(data)
        qr.make(fit=True)
        matrix = qr.modules
        modcount = qr.modules_count

        def is_dark(r: int, c: int) -> bool:
            if 0 <= r < modcount and 0 <= c < modcount:
                return bool(matrix[r][c])
            return False

        lines = []
        for r in range(-border, modcount + border, 2):
            row_chars = []
            for c in range(-border, modcount + border):
                top = is_dark(r, c)
                bot = is_dark(r + 1, c) if r + 1 < modcount + border else False
                if top and bot:
                    # Both black
                    row_chars.append("\x1b[30;40m \x1b[0m")
                elif top and not bot:
                    # Top black, bottom white
                    row_chars.append("\x1b[30;47m▀\x1b[0m")
                elif not top and bot:
                    # Top white, bottom black
                    row_chars.append("\x1b[30;47m▄\x1b[0m")
                else:
                    # Both white
                    row_chars.append("\x1b[37;47m \x1b[0m")
            lines.append("".join(row_chars))

        return "\n".join(lines)
    except ImportError:
        return f"[qrcode library not installed. Install with: pip install qrcode]\nURL: {data}"


async def login_by_qr(
    qr_callback: Optional[Callable[[str, str], Union[Awaitable[None], None]]] = None,
    password_callback: Optional[Callable[[], Union[Awaitable[str], str]]] = None,
    base_ws_url: str = DEFAULT_WS_URL,
    app_version: str = "26.11.9",
    timeout: float = 120.0,
) -> tuple[str, User]:
    """
    Performs full authentication flow by generating and polling a QR code in the terminal.

    :param qr_callback: Optional sync or async callback called with (qr_link, track_id).
                        If None, prints QR code and instructions to terminal.
    :param password_callback: Optional callback to provide 2FA password if required.
                              If None, prompts via getpass in the terminal.
    :param base_ws_url: WebSocket URL to connect to.
    :param app_version: Client app version string.
    :param timeout: Maximum seconds to wait for confirmation (default 120s).
    :return: Tuple of (token, User).
    :raises AuthError: If QR code expired, rejected, or 2FA failed.
    """
    transport = MaxTransport(ws_url=base_ws_url, auto_reconnect=False)
    await transport.connect()

    try:
        # Step 1: Handshake (Opcode 6)
        handshake_payload = {
            "userAgent": {
                "deviceType": "WEB",
                "pushDeviceType": "WEBPUSH",
                "locale": "ru",
                "deviceLocale": "ru",
                "osVersion": "Windows",
                "deviceName": "Chrome",
                "headerUserAgent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
                "appVersion": app_version,
                "screen": "1920x1080 1.0x",
                "timezone": "Europe/Moscow",
            },
            "deviceId": str(uuid4()),
        }
        await transport.send_request(opcode=6, payload=handshake_payload)

        # Step 2: Request QR Code session (Opcode 288)
        logger.info("Requesting QR code session from MAX server (Opcode 288)...")
        resp_288 = await transport.send_request(opcode=288, payload={})
        p288 = resp_288.get("payload", {})

        track_id = p288.get("trackId")
        qr_link = p288.get("qrLink")
        ttl_ms = p288.get("ttl", 120000)
        polling_interval_ms = p288.get("pollingInterval", 5000)

        if not track_id or not qr_link:
            raise AuthError(
                error="no_qr_track_id",
                message="Failed to obtain QR session trackId from MAX server",
                payload=p288,
            )

        logger.debug(f"QR session created: trackId={track_id}, ttl={ttl_ms}ms, qrLink={qr_link}")

        # Step 3: Present QR code
        if qr_callback is not None:
            res = qr_callback(qr_link, track_id)
            if inspect.isawaitable(res):
                await res
        else:
            print("\n" + "=" * 58)
            print(" 📱 Авторизация через мобильное приложение MAX")
            print("=" * 58)
            print("1. Откройте приложение MAX на смартфоне")
            print("2. Перейдите в: Настройки -> Устройства -> Привязать устройство")
            print("3. Наведите камеру на QR-код в терминале:\n")
            print(render_qr_ascii(qr_link))
            print(f"👉 Прямая ссылка: {qr_link}\n")
            print("⏳ Ожидание подтверждения с мобильного устройства...")

        # Step 4: Poll status (Opcode 289)
        poll_interval = max(1.0, polling_interval_ms / 1000.0)
        effective_timeout = min(timeout, ttl_ms / 1000.0)
        start_time = time.monotonic()
        login_available = False

        while time.monotonic() - start_time < effective_timeout:
            await asyncio.sleep(poll_interval)
            try:
                resp_289 = await transport.send_request(opcode=289, payload={"trackId": track_id})
                p289 = resp_289.get("payload", {})
                status_obj = p289.get("status", {})
                if status_obj.get("loginAvailable"):
                    login_available = True
                    break
            except MaxAPIError as e:
                logger.debug(f"Opcode 289 polling error: {e}")
                pass

        if not login_available:
            raise AuthError(
                error="qr_expired",
                message="QR-код устарел или время ожидания подтверждения истекло (120 сек)",
                payload={"trackId": track_id},
            )

        logger.info("QR confirmation received! Exchanging trackId for session token (Opcode 291)...")

        # Step 5: Finalize authentication (Opcode 291)
        resp_291 = await transport.send_request(opcode=291, payload={"trackId": track_id})
        p291 = resp_291.get("payload", {})

        # Handle 2FA password challenge if configured on user's account
        if p291.get("passwordChallenge"):
            logger.info("2FA Password is required for this MAX account.")
            if password_callback is not None:
                pwd = (
                    await password_callback()
                    if inspect.iscoroutinefunction(password_callback)
                    else password_callback()
                )
                if inspect.isawaitable(pwd):
                    pwd = await pwd
            else:
                pwd = getpass.getpass("🔐 Введите пароль двухфакторной аутентификации (2FA): ")

            resp_101 = await transport.send_request(
                opcode=101,
                payload={"trackId": track_id, "password": str(pwd).strip()},
            )
            p291 = resp_101.get("payload", {})

        # Extract login token
        token_attrs = p291.get("tokenAttrs", {})
        login_token = token_attrs.get("LOGIN", {}).get("token") or p291.get("token")
        user_profile = p291.get("profile") or {}

        if not login_token:
            raise AuthError(
                error="no_login_token",
                message="QR confirmed, but login token was missing in Opcode 291 response",
                payload=p291,
            )

        user = User.model_validate(user_profile)
        logger.info(f"QR authentication successful for: {user.display_name} (ID: {user.id})")
        return login_token, user

    finally:
        await transport.close()
