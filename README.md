# Unattended Upgrades Slack Notifier

Processes unattended upgrade emails and sends notifications to Slack with configurable alerting rules.

## What it does

- Parses unattended upgrade emails for update status and package details
- Sends structured Slack notifications using Block Kit
- Supports different mention rules for various update states (FAILED, WARNING, SUCCESS, etc.)
- Handles both file input and stdin for mail system integration
- Logs everything with daily rotation

## Installation

1. Clone the repository
2. Run the setup script:
```bash
./scripts/setup.sh
```

## Configuration

Copy the sample config and edit it:
```bash
cp src/config.ini.sample config.ini
```

Required settings in `config.ini`:
```ini
[slack]
token = xoxb-your-actual-slack-token
channel = #your-channel
bot_username = UpdateBot

[system]
hostname = your-server-hostname
username = root
```

Environment variables work too: `SLACK_TOKEN`, `SLACK_CHANNEL`, `HOSTNAME`, `USERNAME`, `BOT_USERNAME`

## Usage

Process an email file:
```bash
python src/notifyslack.py /path/to/email.txt
```

Process from stdin:
```bash
cat email.txt | python src/notifyslack.py
```

## Build

The build script processes Jinja2 templates and generates environment-specific versions:
```bash
python build.py
```

## Dependencies

- Python 3.10+
- requests>=2.25.0

## Project Structure

```
src/
├── notifyslack.py    # Main script
├── config.py         # Configuration management
└── config.ini.sample # Configuration template
build/
├── blocks/           # Jinja2 template blocks
└── build.py          # Build script
scripts/
└── setup.sh          # Setup script
tests/
└── data/             # Test email samples
```

## License

MIT License - see LICENSE file for details.

## Link
https://app.slack.com/block-kit-builder
https://docs.slack.dev/reference/block-kit/blocks/rich-text-block/