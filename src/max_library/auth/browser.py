"""
Browser Local Storage token extraction for MAX Messenger (web.max.ru / web.oneme.ru).
Scans LevelDB data of Chromium-based browsers across Windows, macOS, and Linux.
"""

from dataclasses import dataclass
import glob
import os
import re
import sys
from typing import Optional


@dataclass
class BrowserTokenResult:
    token: str
    viewer_id: Optional[int]
    browser: str
    profile: str
    source_file: str

    def __repr__(self) -> str:
        masked = self.token[:12] + "..." + self.token[-6:] if len(self.token) > 18 else "..."
        return f"<BrowserTokenResult browser={self.browser!r} profile={self.profile!r} viewer_id={self.viewer_id} token={masked!r}>"


def get_browser_search_paths() -> dict[str, list[str]]:
    """Returns mapping of browser name to user data directory candidates based on the current OS."""
    paths: dict[str, list[str]] = {}

    if sys.platform == "win32":
        local_app = os.environ.get("LOCALAPPDATA", "")
        app_data = os.environ.get("APPDATA", "")

        paths = {
            "Yandex": [
                os.path.join(local_app, "Yandex", "YandexBrowser", "User Data"),
            ],
            "Chrome": [
                os.path.join(local_app, "Google", "Chrome", "User Data"),
            ],
            "Edge": [
                os.path.join(local_app, "Microsoft", "Edge", "User Data"),
            ],
            "Opera": [
                os.path.join(app_data, "Opera Software", "Opera Stable"),
            ],
            "Opera GX": [
                os.path.join(app_data, "Opera Software", "Opera GX Stable"),
            ],
            "Brave": [
                os.path.join(local_app, "BraveSoftware", "Brave-Browser", "User Data"),
            ],
            "Chromium": [
                os.path.join(local_app, "Chromium", "User Data"),
            ],
            "Vivaldi": [
                os.path.join(local_app, "Vivaldi", "User Data"),
            ],
        }

    elif sys.platform == "darwin":  # macOS
        home = os.path.expanduser("~")
        app_supp = os.path.join(home, "Library", "Application Support")

        paths = {
            "Chrome": [os.path.join(app_supp, "Google", "Chrome")],
            "Yandex": [os.path.join(app_supp, "Yandex", "YandexBrowser")],
            "Edge": [os.path.join(app_supp, "Microsoft Edge")],
            "Opera": [os.path.join(app_supp, "com.operasoftware.Opera")],
            "Brave": [os.path.join(app_supp, "BraveSoftware", "Brave-Browser")],
            "Chromium": [os.path.join(app_supp, "Chromium")],
            "Vivaldi": [os.path.join(app_supp, "Vivaldi")],
        }

    else:  # Linux / FreeBSD / other UNIX
        home = os.path.expanduser("~")
        config = os.environ.get("XDG_CONFIG_HOME", os.path.join(home, ".config"))

        paths = {
            "Chrome": [
                os.path.join(config, "google-chrome"),
                os.path.join(config, "google-chrome-beta"),
            ],
            "Yandex": [
                os.path.join(config, "yandex-browser"),
                os.path.join(config, "yandex-browser-beta"),
            ],
            "Edge": [
                os.path.join(config, "microsoft-edge"),
                os.path.join(config, "microsoft-edge-dev"),
            ],
            "Opera": [
                os.path.join(config, "opera"),
            ],
            "Brave": [
                os.path.join(config, "BraveSoftware", "Brave-Browser"),
            ],
            "Chromium": [
                os.path.join(config, "chromium"),
            ],
            "Vivaldi": [
                os.path.join(config, "vivaldi"),
            ],
        }

    return paths


def _scan_leveldb_dir(leveldb_dir: str, browser_name: str, profile_name: str) -> Optional[BrowserTokenResult]:
    """Scans .ldb and .log files in a LevelDB directory for the MAX session token."""
    if not os.path.isdir(leveldb_dir):
        return None

    # Sort files by modification time (newest first)
    files = []
    for ext in ("*.ldb", "*.log"):
        files.extend(glob.glob(os.path.join(leveldb_dir, ext)))

    files.sort(key=lambda p: os.path.getmtime(p) if os.path.exists(p) else 0, reverse=True)

    for filepath in files:
        try:
            with open(filepath, "rb") as f:
                content = f.read()

                # Priority 1: Match structured JSON payload {"viewerId":...,"token":"An_..."}
                for match in re.finditer(rb'\{"viewerId":(\d+),"token":"([^"]+)"\}', content):
                    raw_id = match.group(1).decode("utf-8", errors="ignore")
                    token_str = match.group(2).decode("utf-8", errors="ignore")
                    if token_str.startswith("An_") and len(token_str) > 100:
                        return BrowserTokenResult(
                            token=token_str,
                            viewer_id=int(raw_id),
                            browser=browser_name,
                            profile=profile_name,
                            source_file=filepath,
                        )

                # Priority 2: Match web.max.ru / __oneme_auth context
                if b"__oneme_auth" in content or b"web.max.ru" in content or b"web.oneme.ru" in content:
                    for match in re.finditer(rb'["\'](An_[a-zA-Z0-9_\-]{100,})["\']', content):
                        token_str = match.group(1).decode("utf-8", errors="ignore")
                        # Try to extract viewerId if present nearby
                        viewer_id = None
                        start_pos = max(0, match.start() - 100)
                        nearby = content[start_pos : match.start()]
                        id_m = re.search(rb'viewerId"?\s*:\s*(\d+)', nearby)
                        if id_m:
                            try:
                                viewer_id = int(id_m.group(1).decode("ascii"))
                            except Exception:
                                pass

                        return BrowserTokenResult(
                            token=token_str,
                            viewer_id=viewer_id,
                            browser=browser_name,
                            profile=profile_name,
                            source_file=filepath,
                        )

                    for match in re.finditer(rb'[^a-zA-Z0-9_\-](An_[a-zA-Z0-9_\-]{100,})[^a-zA-Z0-9_\-]', content):
                        token_str = match.group(1).decode("utf-8", errors="ignore")
                        return BrowserTokenResult(
                            token=token_str,
                            viewer_id=None,
                            browser=browser_name,
                            profile=profile_name,
                            source_file=filepath,
                        )

        except Exception:
            continue

    return None


def extract_token_from_browser(
    browser_name: Optional[str] = None,
    profile_name: Optional[str] = None,
) -> Optional[BrowserTokenResult]:
    """
    Automatically discovers and extracts the MAX authorization token from local browser storage.

    :param browser_name: Filter by browser ('Chrome', 'Yandex', 'Edge', 'Opera', 'Brave', etc.).
    :param profile_name: Filter by profile ('Default', 'Profile 1', etc.).
    :return: BrowserTokenResult if found, otherwise None.
    """
    search_paths = get_browser_search_paths()

    # If specific browser requested
    if browser_name:
        matched_browser = None
        for b in search_paths:
            if b.lower() == browser_name.lower():
                matched_browser = b
                break
        if not matched_browser:
            search_paths = {browser_name: [browser_name]}
        else:
            search_paths = {matched_browser: search_paths[matched_browser]}

    # Profile search list
    profiles_to_check = [profile_name] if profile_name else ["Default"] + [f"Profile {i}" for i in range(1, 15)]

    for b_name, base_dirs in search_paths.items():
        for base_dir in base_dirs:
            if not os.path.exists(base_dir):
                continue

            # Check if base_dir is already a profile directory (e.g. Opera)
            direct_ldb = os.path.join(base_dir, "Local Storage", "leveldb")
            if os.path.exists(direct_ldb):
                res = _scan_leveldb_dir(direct_ldb, b_name, "Default")
                if res:
                    return res

            # Scan profiles inside base_dir
            for prof in profiles_to_check:
                ldb_dir = os.path.join(base_dir, prof, "Local Storage", "leveldb")
                if os.path.exists(ldb_dir):
                    res = _scan_leveldb_dir(ldb_dir, b_name, prof)
                    if res:
                        return res

    return None
