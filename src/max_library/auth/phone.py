"""
Phone & SMS/Push verification authentication flow for MAX Messenger.
Provides programmatic and interactive CLI login via Opcode 17 & 18.
"""

import asyncio
import inspect
import logging
from typing import Any, Awaitable, Callable, Optional, Union
from uuid import uuid4

from max_library.exceptions import AuthError, MaxAPIError, MaxClientError
from max_library.models.user import User
from max_library.transport.websocket import DEFAULT_WS_URL, MaxTransport

logger = logging.getLogger("max_library.auth")



async def login_by_phone(
    phone: str,
    code_callback: Optional[Callable[[], Union[Awaitable[str], str]]] = None,
    base_ws_url: str = DEFAULT_WS_URL,
    app_version: str = "26.11.9",
) -> tuple[str, User]:
    """
    Performs full authentication flow by phone number via SMS/Push verification code.

    :param phone: Phone number in international format, e.g. "+79991234567".
    :param code_callback: Optional sync or async function returning the verification code.
                          If None, prompts interactively in the terminal.
    :param base_ws_url: WebSocket URL to connect to.
    :param app_version: Client app version string.
    :return: Tuple of (token, User).
    """
    clean_phone = phone.strip()
    if not clean_phone.startswith("+"):
        clean_phone = "+" + clean_phone

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

        # Step 2: Request SMS/Push verification code (Opcode 17)
        logger.info(f"Requesting verification code for {clean_phone}...")
        
        captcha_token = None
        try:
            resp_17 = await transport.send_request(
                opcode=17,
                payload={
                    "phone": clean_phone,
                    "type": "START_AUTH",
                    "language": "ru",
                },
            )
        except MaxAPIError as e:
            if "captcha" in str(e).lower():
                raise AuthError(
                    error="captcha_required",
                    message=(
                        f"MAX server requires VK SmartCaptcha validation for {clean_phone}. "
                        "Interactive headless CAPTCHA is not supported in CLI. "
                        "Please extract your token from browser using:\n"
                        "  python -m max_library auth --browser\n"
                        "or copy MAX_TOKEN from https://web.max.ru (Application -> Local Storage -> __oneme_auth)."
                    ),
                    payload={"phone": clean_phone},
                )
            raise

        p17 = resp_17.get("payload", {})
        temp_token = p17.get("token")
        if not temp_token:
            raise AuthError(
                error="no_auth_token",
                message="Failed to obtain temporary authentication token from MAX server",
                payload=p17,
            )

        # Informative hint about delivery
        channel = p17.get("deliveryChannel") or "SMS / Push"
        print(f"\n📩 Код подтверждения отправлен на {clean_phone} ({channel})")

        # Step 3 & 4: Enter and verify code (with retries on typo)
        max_attempts = 3
        login_token = None
        user_profile = None

        for attempt in range(1, max_attempts + 1):
            if code_callback is not None:
                try:
                    # Support callbacks accepting attempt number or no args
                    if inspect.iscoroutinefunction(code_callback):
                        code = await code_callback()
                    else:
                        code = code_callback()
                        if inspect.isawaitable(code):
                            code = await code
                except TypeError:
                    code = await code_callback(attempt) if inspect.iscoroutinefunction(code_callback) else code_callback(attempt)
            else:
                prompt = (
                    f"👉 Введите проверочный код: "
                    if attempt == 1
                    else f"❌ Неверный код. Попробуйте снова ({attempt}/{max_attempts}): "
                )
                code = input(prompt)

            code = str(code).strip()
            if not code:
                continue

            try:
                resp_18 = await transport.send_request(
                    opcode=18,
                    payload={
                        "token": temp_token,
                        "verifyCode": code,
                        "authTokenType": "CHECK_CODE",
                    },
                )
                p18 = resp_18.get("payload", {})
                login_token = (
                    p18.get("tokenAttrs", {}).get("LOGIN", {}).get("token")
                    or p18.get("token")
                )
                user_profile = p18.get("profile") or {}
                break  # Verification succeeded!
            except (VerifyCodeWrong, MaxAPIError) as e:
                err_str = str(e).lower()
                is_wrong_code = "wrong" in err_str or "invalid" in err_str or "code" in err_str
                if is_wrong_code and attempt < max_attempts:
                    logger.warning(f"Verification code attempt #{attempt} failed. Retrying...")
                    continue
                raise

        if not login_token:
            raise AuthError(
                error="no_login_token",
                message="Code verified, but login token was missing in response",
                payload=p18,
            )

        user = User.model_validate(user_profile)
        logger.info(f"Authentication successful for: {user.display_name} (ID: {user.id})")
        return login_token, user

    finally:
        await transport.close()


async def verify_token(
    token: str,
    base_ws_url: str = DEFAULT_WS_URL,
    app_version: str = "26.11.9",
) -> Optional[User]:
    """
    Verifies if a MAX token is valid by performing handshake and session initialization (Opcode 19).

    :param token: The MAX token string to test.
    :param base_ws_url: WebSocket URL to connect to.
    :param app_version: Client app version.
    :return: User profile if valid, None if invalid or expired.
    """
    from max_library.client import MaxClient
    client = MaxClient(
        token=token.strip(),
        base_ws_url=base_ws_url,
        app_version=app_version,
        auto_reconnect=False,
    )
    try:
        await client.start()
        return client.me
    except Exception as e:
        logger.debug(f"Token verification failed: {e}")
        return None
    finally:
        await client.close()

