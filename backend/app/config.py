"""Configuration loader.

Every algorithm constant in SPEC §9/§10 comes from `config.yaml` so the viva can
point at one file and say "that is where the numbers live". Nothing here is
hard-coded twice.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml

BASE_DIR = Path(__file__).resolve().parent.parent          # backend/
ROOT_DIR = BASE_DIR.parent                                 # repository root
CONFIG_PATH = Path(os.environ.get("TRUVEL_CONFIG", ROOT_DIR / "config.yaml"))
MEDIA_DIR = Path(os.environ.get("TRUVEL_MEDIA_DIR", BASE_DIR / "media"))
DATA_DIR = Path(os.environ.get("TRUVEL_DATA_DIR", ROOT_DIR / "data"))
DB_PATH = Path(os.environ.get("TRUVEL_DB", BASE_DIR / "truvel.db"))


@lru_cache(maxsize=1)
def load_config() -> dict[str, Any]:
    """Read config.yaml once per process."""
    with CONFIG_PATH.open("r", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def cfg(path: str, default: Any = None) -> Any:
    """Read a dotted path out of the config, e.g. cfg("deck.prox_tau_km").

    Returning a default rather than raising keeps a missing optional key from
    taking the whole app down, but every key used in SPEC §9/§10 is present.
    """
    node: Any = load_config()
    for part in path.split("."):
        if not isinstance(node, dict) or part not in node:
            return default
        node = node[part]
    return node


# --- flags that must never be on in production (SPEC §8.7, AC-25) -----------

def dev_allow_fake_location() -> bool:
    """The dev location simulator is off unless the server is started with it."""
    return os.environ.get("DEV_ALLOW_FAKE_LOCATION") == "1"


def is_https() -> bool:
    """Set when the app is served over TLS, so session cookies get Secure."""
    return os.environ.get("TRUVEL_HTTPS") == "1"


def regional_langs(state: str | None) -> list[str]:
    """Regional languages for a state/UT (SPEC §7.2). Unknown state -> English."""
    if not state:
        return ["en"]
    table = cfg("state_languages", {}) or {}
    return list(table.get(state, ["en"]))
