"""
Top-level entry point for python -m max_library.
Delegates to CLI tools like auth.
"""

import sys

def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "auth":
        from max_library.auth.cli import main as auth_main
        sys.argv.pop(1)
        auth_main()
    else:
        print("Usage: python -m max_library auth [options]")
        print("Run 'python -m max_library auth --help' for available arguments.")

if __name__ == "__main__":
    main()
