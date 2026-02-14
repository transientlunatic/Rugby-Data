"""
Shared configuration for rugby-data and rugby-ranking packages.

Config file location: ~/.config/rugby/config.toml
"""

import os
import sys
from pathlib import Path
from typing import Optional

if sys.version_info >= (3, 11):
    import tomllib
else:
    try:
        import tomllib
    except ImportError:
        import tomli as tomllib


CONFIG_DIR = Path.home() / ".config" / "rugby"
CONFIG_FILE = CONFIG_DIR / "config.toml"


def get_config_path() -> Path:
    """Return the path to the config file."""
    return CONFIG_FILE


def load_config() -> dict:
    """Load and parse the config file. Returns empty dict if missing."""
    config_path = get_config_path()
    if not config_path.exists():
        return {}
    try:
        with open(config_path, "rb") as f:
            return tomllib.load(f)
    except Exception:
        return {}


def get_data_dir() -> Optional[Path]:
    """
    Return the configured data_dir path.

    Priority:
    1. RUGBY_DATA_DIR environment variable
    2. Config file paths.data_dir
    3. None (caller should fall back to defaults)
    """
    env_dir = os.environ.get("RUGBY_DATA_DIR")
    if env_dir:
        return Path(env_dir)

    config = load_config()
    data_dir = config.get("paths", {}).get("data_dir")
    if data_dir:
        return Path(data_dir)

    return None


def get_squads_dir() -> Optional[Path]:
    """
    Return the configured squads_dir path.

    Priority:
    1. RUGBY_SQUADS_DIR environment variable
    2. Config file paths.squads_dir
    3. {data_dir}/squads if data_dir is set
    4. None
    """
    env_dir = os.environ.get("RUGBY_SQUADS_DIR")
    if env_dir:
        return Path(env_dir)

    config = load_config()
    squads_dir = config.get("paths", {}).get("squads_dir")
    if squads_dir:
        return Path(squads_dir)

    data_dir = get_data_dir()
    if data_dir:
        return data_dir / "squads"

    return None


def save_config(config: dict):
    """Write config dict to the config file in TOML format."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    lines = []
    for section, values in config.items():
        lines.append(f"[{section}]")
        if isinstance(values, dict):
            for key, val in values.items():
                if isinstance(val, str):
                    lines.append(f'{key} = "{val}"')
                elif isinstance(val, bool):
                    lines.append(f'{key} = {"true" if val else "false"}')
                elif isinstance(val, (int, float)):
                    lines.append(f'{key} = {val}')
        lines.append("")

    with open(CONFIG_FILE, "w") as f:
        f.write("\n".join(lines))
