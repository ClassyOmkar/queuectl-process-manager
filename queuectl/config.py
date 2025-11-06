"""Configuration management utilities"""

from typing import Optional


# Default configuration values
DEFAULTS = {
    "max_retries": "3",
    "backoff_base": "2",
    "worker_poll_interval": "1",
    "db_path": "./data/queuectl.db"
}


# Mapping from hyphen to underscore format (for CLI compatibility)
KEY_MAPPING = {
    "max-retries": "max_retries",
    "backoff-base": "backoff_base",
    "worker-poll-interval": "worker_poll_interval",
    "db-path": "db_path"
}


def normalize_config_key(key: str) -> str:
    """Normalize config key: convert hyphen to underscore format"""
    # Check if key is in hyphen format, map to underscore
    if key in KEY_MAPPING:
        return KEY_MAPPING[key]
    # If already underscore format, return as-is
    return key


def get_config(store, key: str) -> Optional[str]:
    """Get configuration value with fallback to defaults"""
    # Normalize key (convert hyphen to underscore)
    normalized_key = normalize_config_key(key)
    value = store.get_config(normalized_key)
    if value is None:
        return DEFAULTS.get(normalized_key)
    return value


def get_config_int(store, key: str) -> int:
    """Get configuration value as integer"""
    value = get_config(store, key)
    return int(value) if value else 0


def get_config_float(store, key: str) -> float:
    """Get configuration value as float"""
    value = get_config(store, key)
    return float(value) if value else 0.0
