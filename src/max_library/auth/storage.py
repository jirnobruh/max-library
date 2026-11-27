"""
Utility functions to persist and manage MAX tokens in .env files.
"""

import os
from pathlib import Path
import re


def save_token_to_env(
    token: str,
    env_file_path: str = ".env",
    var_name: str = "MAX_TOKEN",
) -> bool:
    """
    Saves or updates MAX_TOKEN in the specified .env file.
    Preserves all existing comments, formatting, and other variables.

    :param token: The MAX token string.
    :param env_file_path: Path to the .env file (default: ".env").
    :param var_name: Name of the environment variable (default: "MAX_TOKEN").
    :return: True if successfully written, False otherwise.
    """
    path = Path(env_file_path)
    new_line = f"{var_name}={token.strip()}"

    if not path.exists():
        # Create new .env
        path.write_text(f"{new_line}\n", encoding="utf-8")
        return True

    content = path.read_text(encoding="utf-8")
    lines = content.splitlines()
    replaced = False

    # Regex matching VAR_NAME=...
    pattern = re.compile(rf"^\s*{re.escape(var_name)}\s*=.*$")

    new_lines = []
    for line in lines:
        if pattern.match(line):
            new_lines.append(new_line)
            replaced = True
        else:
            new_lines.append(line)

    if not replaced:
        # Append to the end
        if new_lines and new_lines[-1].strip() != "":
            new_lines.append("")
        new_lines.append(new_line)

    result_text = "\n".join(new_lines) + "\n"
    path.write_text(result_text, encoding="utf-8")
    return True
