import os
from functools import lru_cache
from typing import Any

import tomllib


@lru_cache
def load_config() -> dict[str, Any]:
    default_config_dir = os.path.dirname(os.path.abspath(__file__))
    default_config_file = os.path.join(default_config_dir, "..", "config.toml")
    config_file = os.getenv("CANONICAL_SERVICE_CONFIG_FILE", default_config_file)
    with open(config_file) as f:
        data = tomllib.load(f)
    return data


config = load_config()
