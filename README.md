# Unattended Upgrades Slack Notifier

Parses unattended upgrade emails and sends Slack notifications.

## Features

- Email parsing for update status and package details
- Slack notifications using Block Kit
- Configurable mention rules for different update states
- File input and stdin support


## Setup

```bash
./scripts/setup.sh
```

## Configuration

```bash
cp src/config.ini.sample config.ini
```

Edit `config.ini`:
```ini
[slack]
token = xoxb-your-actual-slack-token
channel = #your-channel
bot_username = UpdateBot

[system]
hostname = your-server-hostname
username = root
```

Environment variables: `SLACK_TOKEN`, `SLACK_CHANNEL`, `HOSTNAME`, `USERNAME`, `BOT_USERNAME`

## Usage

File input:
```bash
python src/notifyslack.py /path/to/email.txt
```

Stdin:
```bash
cat email.txt | python src/notifyslack.py
```

## Build

Two build options available:

**Jinja2 templates for Ansible:**
```bash
python build.py
```

**Direct Python usage:**
Use the generated script directly without Ansible.

## Postfix Integration

Configure unattended-upgrades to send emails to postfix:

1. Edit `/etc/apt/apt.conf.d/50unattended-upgrades`:
```plaintext
Unattended-Upgrade::Mail "root@localhost";
```

2. Configure postfix to pipe emails to the script:
```plaintext
# In /etc/postfix/master.cf
notifyslack unix - n n - - pipe
  flags=F user=root argv=/path/to/notifyslack.py
```

3. Add transport rule in `/etc/postfix/main.cf`:
```plaintext
transport_maps = hash:/etc/postfix/transport
```

4. Create `/etc/postfix/transport`:
```plaintext
root@localhost notifyslack:
```

## Requirements

- Python 3.10+
- requests>=2.25.0

## License

MIT

_Generated documentation_
