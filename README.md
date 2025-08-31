# Unattended Upgrades Slack Notifier

Processes unattended upgrade emails and sends notifications to Slack.

## Installation

1. Clone the repository:

1. Run the setup script:
```bash
./scripts/setup.sh
```

## Configuration

Copy the sample configuration file:
```bash
cp src/config.ini.sample config.ini
```

Edit `config.ini` with your Slack credentials:
```ini
[slack]
token = xoxb-your-actual-slack-token
channel = #your-channel
bot_username = UpdateBot

[system]
hostname = your-server-hostname
username = root
```

## Usage

Process an email file:
```bash
python src/notifyslack.py /path/to/email.txt
```

Process from stdin:
```bash
cat email.txt | python src/notifyslack.py
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