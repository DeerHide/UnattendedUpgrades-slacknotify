"""Configuration management."""

import configparser
import os
from typing import TypedDict


class SlackConfigsDict(TypedDict):
    """Slack configuration dictionary."""
    SLACK_TOKEN: str
    SLACK_CHANNEL: str
    BOT_USERNAME: str

class SystemConfigsDict(TypedDict):
    """System configuration dictionary."""
    HOSTNAME: str
    USERNAME: str

class ConfigsDict(SystemConfigsDict, SlackConfigsDict):
    """Combined configuration dictionary."""


def load_config_from_file(config_path: str | None = None) -> ConfigsDict:
    """Load configuration from file.

    Args:
        config_path: The path to the config file

    Returns:
        ConfigsDict: The configuration dictionary

    Raises:
        ValueError: If the config file does not exist
        or does not contain both slack and system sections
    """
    if config_path is None:
        config_path = "config.ini"

    if not os.path.exists(config_path):
        raise ValueError(f"Config file {config_path} does not exist")

    try:
        parser: configparser.ConfigParser = configparser.ConfigParser()
        parser.read(config_path)
    except Exception as e: # pylint: disable=broad-exception-caught
        raise ValueError(f"Could not parse config file {config_path}: {e}")


    if not (parser.has_section('slack') and parser.has_section('system')):
        raise ValueError("Config file must contain both slack and system sections")

    slack_config: SlackConfigsDict = SlackConfigsDict(
        SLACK_TOKEN=parser.get('slack', 'token', fallback=''),
        SLACK_CHANNEL=parser.get('slack', 'channel', fallback=''),
        BOT_USERNAME=parser.get('slack', 'bot_username', fallback='')
    )

    system_config: SystemConfigsDict = SystemConfigsDict(
        HOSTNAME=parser.get('system', 'hostname', fallback=''),
        USERNAME=parser.get('system', 'username', fallback='')
    )

    return ConfigsDict(**slack_config, **system_config)


def get_config_value(key: str, default: str = "") -> str:
    """Get configuration value from environment or file."""
    value = os.environ.get(key)

    if value:
        return value

    config: SlackConfigsDict | SystemConfigsDict | ConfigsDict = load_config_from_file()
    return str(config.get(key, default))
