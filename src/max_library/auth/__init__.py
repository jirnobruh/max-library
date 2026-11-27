"""
MAX Messenger Authentication and Token Discovery Package.
"""

from max_library.auth.browser import (
    BrowserTokenResult,
    extract_token_from_browser,
    get_browser_search_paths,
)
from max_library.auth.phone import login_by_phone, verify_token
from max_library.auth.qr import (
    QRAuthSession,
    create_qr_session,
    generate_qr_data_url,
    generate_qr_svg,
    login_by_qr,
    render_qr_ascii,
)
from max_library.auth.storage import save_token_to_env

__all__ = [
    "BrowserTokenResult",
    "extract_token_from_browser",
    "get_browser_search_paths",
    "login_by_phone",
    "login_by_qr",
    "create_qr_session",
    "QRAuthSession",
    "render_qr_ascii",
    "generate_qr_svg",
    "generate_qr_data_url",
    "verify_token",
    "save_token_to_env",
]

