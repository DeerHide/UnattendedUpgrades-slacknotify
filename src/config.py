import os
from pathlib import Path
from typing import Optional


def load_config_from_file(config_path: Optional[str] = None) -> dict:
    if config_path is None:
        config_path = "config.ini"
    
    config = {}
    
    if os.path.exists(config_path):
        try:
            import configparser
            parser = configparser.ConfigParser()
            parser.read(config_path)
            
            if 'slack' in parser:
                config['SLACK_TOKEN'] = parser.get('slack', 'token', fallback='')
                config['SLACK_CHANNEL'] = parser.get('slack', 'channel', fallback='')
                config['BOT_USERNAME'] = parser.get('slack', 'bot_username', fallback='')
            
            if 'system' in parser:
                config['HOSTNAME'] = parser.get('system', 'hostname', fallback='')
                config['USERNAME'] = parser.get('system', 'username', fallback='')
                
        except Exception as e:
            print(f"Warning: Could not parse config file {config_path}: {e}")
    
    return config


def get_config_value(key: str, default: str = "") -> str:
    env_key = key
    value = os.environ.get(env_key)
    
    if value:
        return value
    
    config = load_config_from_file()
    return config.get(key, default)

# Load configuration values
SLACK_TOKEN = get_config_value("SLACK_TOKEN")
SLACK_CHANNEL = get_config_value("SLACK_CHANNEL")
HOSTNAME = get_config_value("HOSTNAME")
USERNAME = get_config_value("USERNAME")
BOT_USERNAME = get_config_value("BOT_USERNAME")
