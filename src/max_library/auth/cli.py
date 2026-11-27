"""
Command Line Interface (CLI) for MAX token discovery and authentication.
Supports automatic browser extraction and interactive phone/SMS login.
"""

import argparse
import asyncio
import json
import os
import sys
from typing import Optional

from max_library.auth.browser import extract_token_from_browser
from max_library.auth.phone import login_by_phone, verify_token
from max_library.auth.qr import login_by_qr
from max_library.auth.storage import save_token_to_env


def print_banner() -> None:
    print(r"""
===========================================================
 🚀 MAX Messenger Token Tool (max-library)
===========================================================
""")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="max-auth",
        description="Automated Token Discovery & Authentication for MAX Messenger",
    )

    mode_group = parser.add_mutually_exclusive_group()
    mode_group.add_argument(
        "--qr",
        action="store_true",
        help="Interactive QR-code login scanned via mobile MAX app",
    )
    mode_group.add_argument(
        "-b",
        "--browser",
        nargs="?",
        const="all",
        help="Extract token from browser Local Storage (all, yandex, chrome, edge, opera, brave)",
    )
    mode_group.add_argument(
        "-p",
        "--phone",
        type=str,
        help="Interactive login by phone number (+79991234567)",
    )


    parser.add_argument(
        "-c",
        "--check",
        action="store_true",
        help="Verify the obtained token against MAX WebSocket API",
    )
    parser.add_argument(
        "-s",
        "--save",
        nargs="?",
        const=".env",
        help="Save token to .env file (default: .env)",
    )
    parser.add_argument(
        "--var",
        type=str,
        default="MAX_TOKEN",
        help="Environment variable name for --save (default: MAX_TOKEN)",
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Print only the token string without decorations",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result in JSON format",
    )

    return parser


async def run_cli(args: argparse.Namespace) -> int:
    token: Optional[str] = None
    source_info: dict[str, str] = {}
    user_info: Optional[dict[str, str]] = None

    is_quiet = args.quiet or args.json

    if not is_quiet:
        print_banner()

    # Case 1: QR-code authentication mode
    if args.qr:
        if not is_quiet:
            print("📱 Запуск авторизации по QR-коду...")
        try:
            token, user = await login_by_qr()
            source_info = {"method": "qr"}
            user_info = {
                "id": str(user.id),
                "name": user.display_name,
                "phone": user.phone or "",
            }
            if not is_quiet:
                print(f"✅ Успешная авторизация! Пользователь: {user.display_name} (ID: {user.id})")
        except Exception as e:
            if not is_quiet:
                print(f"❌ Ошибка авторизации по QR-коду: {e}")
            else:
                sys.stderr.write(f"Error: {e}\n")
            return 1

    # Case 2: Phone authentication mode
    elif args.phone:
        if not is_quiet:
            print(f"📱 Запуск авторизации по номеру: {args.phone}")
        try:
            token, user = await login_by_phone(args.phone)
            source_info = {"method": "phone", "phone": args.phone}
            user_info = {
                "id": str(user.id),
                "name": user.display_name,
                "phone": user.phone or args.phone,
            }
            if not is_quiet:
                print(f"✅ Успешная авторизация! Пользователь: {user.display_name} (ID: {user.id})")
        except Exception as e:
            if not is_quiet:
                print(f"❌ Ошибка авторизации по телефону: {e}")
            else:
                sys.stderr.write(f"Error: {e}\n")
            return 1

    # Case 3: Browser extraction mode (explicit or default if no mode given)
    else:
        browser_name = None if args.browser == "all" or not args.browser else args.browser
        if not is_quiet:
            target = f"'{browser_name}'" if browser_name else "всех поддерживаемых браузерах"
            print(f"🔍 Поиск токена в {target}...")

        browser_res = extract_token_from_browser(browser_name=browser_name)
        if browser_res:
            token = browser_res.token
            source_info = {
                "method": "browser",
                "browser": browser_res.browser,
                "profile": browser_res.profile,
                "file": browser_res.source_file,
            }
            if not is_quiet:
                print(f"🎉 Токен найден в {browser_res.browser} (профиль: {browser_res.profile})!")
        else:
            if not is_quiet:
                print("❌ Токен не найден в локальном хранилище браузеров.")
                print("💡 Вы можете легко авторизоваться по QR-коду через приложение MAX:")
                print("   python -m max_library auth --qr")
                print("   или по номеру телефона: python -m max_library auth --phone +79991234567")
            else:
                sys.stderr.write("Token not found in browser storage.\n")
            return 1

    if not token:
        return 1

    # Optional check
    if args.check or (args.browser and not is_quiet):
        if not is_quiet:
            print("⏳ Проверка валидности токена через MAX API...")
        verified_user = await verify_token(token)
        if verified_user:
            user_info = {
                "id": str(verified_user.id),
                "name": verified_user.display_name,
                "phone": verified_user.phone or "",
            }
            if not is_quiet:
                print(f"✅ Токен активен! Аккаунт: {verified_user.display_name} (ID: {verified_user.id})")
        else:
            if not is_quiet:
                print("⚠️ Предупреждение: Сервер MAX не подтвердил активность сессии (возможно, токен устарел).")

    # Optional save to .env
    saved_path = None
    if args.save:
        target_path = args.save
        try:
            save_token_to_env(token, env_file_path=target_path, var_name=args.var)
            saved_path = os.path.abspath(target_path)
            if not is_quiet:
                print(f"💾 Токен успешно сохранён в {saved_path} ({args.var})")
        except Exception as e:
            if not is_quiet:
                print(f"❌ Не удалось сохранить в {target_path}: {e}")

    # Output formatting
    if args.json:
        data = {
            "token": token,
            "source": source_info,
            "user": user_info,
            "saved_to": saved_path,
        }
        print(json.dumps(data, ensure_ascii=False, indent=2))
    elif args.quiet:
        print(token)
    else:
        print("\n" + "=" * 59)
        print("🔑 ВАШ MAX_TOKEN:")
        print(token)
        print("=" * 59 + "\n")

    return 0


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    code = asyncio.run(run_cli(args))
    sys.exit(code)


if __name__ == "__main__":
    main()
