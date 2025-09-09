"""Test configuration management."""

from collections.abc import Generator
from pathlib import Path

import pytest

from config import ConfigsDict, load_config_from_file

CONFIG_FILE_CONTENT_VALID = """
[slack]
token = test_token
channel = test_channel
bot_username = test_bot_username
[system]
hostname = test_hostname
username = test_username
"""

CONFIG_FILE_CONTENT_INVALID = """
[system]
hostname = test_hostname
username = test_username
"""


class TestConfig:
    """Test configuration management."""

    @pytest.fixture(name="config_file_valid")
    def fixture_config_file(self, tmp_path: Path) -> Generator[Path, None, None]:
        """Fixture to create a config file."""
        config_file: Path = tmp_path / "config.ini"
        config_file.write_text(data=CONFIG_FILE_CONTENT_VALID, encoding="utf-8")
        yield config_file
        config_file.unlink()

    @pytest.fixture(name="config_file_invalid")
    def fixture_config_file_invalid(self, tmp_path: Path) -> Generator[Path, None, None]:
        """Fixture to create a config file."""
        config_file: Path = tmp_path / "config.ini"
        config_file.write_text(data=CONFIG_FILE_CONTENT_INVALID, encoding="utf-8")
        yield config_file
        config_file.unlink()

    def test_load_config_from_file(
        self,
        config_file_valid: Path,
    ):
        """Test loading configuration from file."""
        config: ConfigsDict = load_config_from_file(config_path=config_file_valid)

        assert config["SLACK_TOKEN"] == "test_token"
        assert config["SLACK_CHANNEL"] == "test_channel"
        assert config["BOT_USERNAME"] == "test_bot_username"
        assert config["HOSTNAME"] == "test_hostname"
        assert config["USERNAME"] == "test_username"

    def test_config_file_not_found(self):
        """Test loading configuration from file that does not exist."""
        with pytest.raises(ValueError):
            load_config_from_file(Path("not_found.ini"))

    def test_config_file_not_valid(self, config_file_invalid: Path):
        """Test loading configuration from file that is not valid."""
        with pytest.raises(ValueError):
            load_config_from_file(config_path=config_file_invalid)
