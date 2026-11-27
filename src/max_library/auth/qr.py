"""
QR Code authentication flow for MAX Messenger (web.max.ru / web.oneme.ru).
Provides programmatic and interactive CLI login via Opcode 288, 289, and 291.
Eliminates VK Captcha and SMS verification by using trusted mobile app confirmation.
Supports both terminal display and web/app integration (raw URL, SVG, and Data URL).
"""

import asyncio
import base64
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


def generate_qr_svg(data: str, border: int = 2) -> str:
    """
    Generates a clean standalone SVG XML string for a given URL or data.
    Requires no external imaging libraries (pure vector XML).

    :param data: The text or URL to encode.
    :param border: Width of the quiet zone border in modules (default 2).
    :return: SVG XML string.
    """
    import qrcode
    import qrcode.image.svg

    factory = qrcode.image.svg.SvgPathImage
    img = qrcode.make(data, image_factory=factory, border=border)
    return img.to_string(encoding="unicode")


def generate_qr_data_url(data: str, border: int = 2) -> str:
    """
    Generates a Base64-encoded SVG data URL suitable for direct use in <img src="...">
    tags on websites, dashboards, or mobile webviews.

    :param data: The text or URL to encode.
    :param border: Quiet zone border width (default 2).
    :return: Data URL string, e.g. 'data:image/svg+xml;base64,...'
    """
    svg_code = generate_qr_svg(data, border=border)
    b64 = base64.b64encode(svg_code.encode("utf-8")).decode("ascii")
    return f"data:image/svg+xml;base64,{b64}"


class QRAuthSession:
    """
    Represents an active QR authentication session for MAX Messenger.
    Allows web applications, bots, and services to decouple QR code generation
    (sending URL, SVG, or data URL to frontend) from awaiting user confirmation.
    """

    def __init__(
        self,
        transport: MaxTransport,
        track_id: str,
        qr_link: str,
        ttl_ms: int = 120000,
        polling_interval_ms: int = 5000,
        expires_at: Optional[int] = None,
    ):
        self.transport = transport
        self.track_id = track_id
        self.qr_link = qr_link
        self.ttl = ttl_ms / 1000.0
        self.polling_interval = max(1.0, polling_interval_ms / 1000.0)
        self.expires_at = expires_at

    def to_svg(self, border: int = 2) -> str:
        """Returns the QR code as standalone SVG XML string for websites."""
        return generate_qr_svg(self.qr_link, border=border)

    def to_data_url(self, border: int = 2) -> str:
        """Returns a base64-encoded SVG Data URL for direct use in <img src="...">."""
        return generate_qr_data_url(self.qr_link, border=border)

    def to_ascii(self, border: int = 2) -> str:
        """Returns the high-contrast terminal ANSI representation."""
        return render_qr_ascii(self.qr_link, border=border)

    async def wait_for_login(
        self,
        timeout: Optional[float] = None,
        password_callback: Optional[Callable[[], Union[Awaitable[str], str]]] = None,
    ) -> tuple[str, User]:
        """
        Polls the MAX server until user scans the QR code on mobile and returns (token, user).

        :param timeout: Maximum seconds to wait (defaults to session TTL, usually 120s).
        :param password_callback: Optional callback if 2FA password is required.
        :return: Tuple of (login_token, User).
        :raises AuthError: If QR code expired, rejected, or 2FA failed.
        """
        effective_timeout = timeout if timeout is not None else self.ttl
        start_time = time.monotonic()
        login_available = False

        while time.monotonic() - start_time < effective_timeout:
            await asyncio.sleep(self.polling_interval)
            try:
                resp_289 = await self.transport.send_request(opcode=289, payload={"trackId": self.track_id})
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
                payload={"trackId": self.track_id},
            )

        logger.info("QR confirmation received! Exchanging trackId for session token (Opcode 291)...")

        resp_291 = await self.transport.send_request(opcode=291, payload={"trackId": self.track_id})
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

            resp_101 = await self.transport.send_request(
                opcode=101,
                payload={"trackId": self.track_id, "password": str(pwd).strip()},
            )
            p291 = resp_101.get("payload", {})

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

    async def close(self) -> None:
        """Closes the underlying WebSocket transport connection."""
        await self.transport.close()

    async def __aenter__(self) -> "QRAuthSession":
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()


async def create_qr_session(
    base_ws_url: str = DEFAULT_WS_URL,
    app_version: str = "26.11.9",
) -> QRAuthSession:
    """
    Creates and initiates a new QR authentication session with MAX server (Opcode 288).
    Returns a QRAuthSession object containing `qr_link`, `track_id`, and helpers
    for rendering SVG / data URL or waiting for login.

    :param base_ws_url: WebSocket URL to connect to.
    :param app_version: Client app version string.
    :return: Initialized QRAuthSession instance.
    :raises AuthError: If handshake or QR generation fails.
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
        expires_at = p288.get("expiresAt")

        if not track_id or not qr_link:
            raise AuthError(
                error="no_qr_track_id",
                message="Failed to obtain QR session trackId from MAX server",
                payload=p288,
            )

        logger.debug(f"QR session created: trackId={track_id}, ttl={ttl_ms}ms, qrLink={qr_link}")

        return QRAuthSession(
            transport=transport,
            track_id=track_id,
            qr_link=qr_link,
            ttl_ms=ttl_ms,
            polling_interval_ms=polling_interval_ms,
            expires_at=expires_at,
        )
    except Exception:
        await transport.close()
        raise


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
    session = await create_qr_session(base_ws_url=base_ws_url, app_version=app_version)

    try:
        if qr_callback is not None:
            res = qr_callback(session.qr_link, session.track_id)
            if inspect.isawaitable(res):
                await res
        else:
            print("\n" + "=" * 58)
            print(" 📱 Авторизация через мобильное приложение MAX")
            print("=" * 58)
            print("1. Откройте приложение MAX на смартфоне")
            print("2. Перейдите в: Настройки -> Устройства -> Привязать устройство")
            print("3. Наведите камеру на QR-код в терминале:\n")
            print(session.to_ascii())
            print(f"👉 Прямая ссылка: {session.qr_link}\n")
            print("⏳ Ожидание подтверждения с мобильного устройства...")

        return await session.wait_for_login(timeout=timeout, password_callback=password_callback)
    finally:
        await session.close()
