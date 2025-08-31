#!/bin/python3

import sys
import tempfile
import os
import re
import requests
import json
import logging
from datetime import datetime

# <<< BUILD.CONFIG.LOGDIR
# this block will be replaced by the BUILD.CONFIG.REPLACE during the build process
base_log_dir = "./logs/notifyslack"
# >>> BUILD.CONFIG.LOGDIR

# <<< BUILD.CONFIG.SLACK
# this block will be replaced by the BUILD.CONFIG.REPLACE during the build process
import config
SLACK_TOKEN = config.SLACK_TOKEN  # Bot User OAuth Token
SLACK_CHANNEL = config.SLACK_CHANNEL  # Channel ID or name
HOSTNAME = config.HOSTNAME  # Hostname of the machine
USERNAME = config.USERNAME  # Username running the update
BOT_USERNAME = config.BOT_USERNAME  # Bot username for Slack
# >>> BUILD.CONFIG.SLACK

# Slack message limits
SLACK_MAX_CHARS = 12000  # Slack's actual character limit per message

# Create log directory structure
def setup_logging() -> logging.Logger:
    """Setup logging with daily files organized by month"""
    now = datetime.now()
    month_name = now.strftime("%B").lower()  # Full month name in lowercase (e.g., "august")
    date_str = now.strftime("%Y-%m-%d")  # YYYY-MM-DD format

    # Create base log directory in user's home
    month_dir = os.path.join(base_log_dir, month_name)

    # Create directories if they don't exist
    os.makedirs(month_dir, exist_ok=True)

    # Create log file path
    log_file = os.path.join(month_dir, f"{date_str}_notifyslack.log")

    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file),
            logging.StreamHandler()
        ]
    )

    return logging.getLogger(__name__)

# Initialize logger
logger = setup_logging()

def split_long_message(content: str, max_chars: int = SLACK_MAX_CHARS) -> list[str]:
    """Split long content into chunks that fit Slack's limits"""
    if len(content) <= max_chars:
        return [content]

    chunks = []
    current_chunk = ""

    for line in content.split('\n'):
        if len(current_chunk) + len(line) + 1 <= max_chars:
            current_chunk += line + '\n'
        else:
            if current_chunk:
                chunks.append(current_chunk.strip())
            current_chunk = line + '\n'

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks

def send_to_slack_blocks(blocks: list[dict], username: str | None = None, thread_ts: str | None = None) -> str | None:
    """Send message with rich formatting using Slack blocks"""
    logger.info(f"Sending Slack message with {len(blocks)} blocks")

    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "channel": SLACK_CHANNEL,
        "blocks": blocks
    }

    if username:
        payload["username"] = username

    if thread_ts:
        payload["thread_ts"] = thread_ts

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            logger.info("Slack message sent successfully")
            return result.get("ts")  # Return timestamp for threading
        else:
            logger.error(f"Slack API error: {result.get('error')}")
            return None
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return None

def send_simple_message(text: str, username: str | None = None, thread_ts: str | None = None) -> str | None:
    """Send simple text message"""
    logger.info(f"Sending simple Slack message: {text[:100]}...")

    # Split long messages if needed
    if len(text) > SLACK_MAX_CHARS:
        logger.info(f"Message too long ({len(text)} chars), splitting into chunks")
        chunks = split_long_message(text)
        timestamps = []

        for i, chunk in enumerate(chunks):
            chunk_text = f"*Part {i+1}/{len(chunks)}*\n{chunk}"
            ts = send_simple_message_chunk(chunk_text, username, thread_ts)
            if ts:
                timestamps.append(ts)
                thread_ts = ts  # Use the last timestamp for threading

        return timestamps[0] if timestamps else None
    else:
        return send_simple_message_chunk(text, username, thread_ts)

def send_simple_message_chunk(text: str, username: str | None = None, thread_ts: str | None = None) -> str | None:
    """Send a single chunk of a simple text message"""
    url = "https://slack.com/api/chat.postMessage"
    headers = {
        "Authorization": f"Bearer {SLACK_TOKEN}",
        "Content-Type": "application/json"
    }

    payload = {
        "channel": SLACK_CHANNEL,
        "text": text
    }

    if username:
        payload["username"] = username

    if thread_ts:
        payload["thread_ts"] = thread_ts

    try:
        response = requests.post(url, headers=headers, json=payload)
        response.raise_for_status()
        result = response.json()

        if result.get("ok"):
            logger.info("Simple message chunk sent successfully")
            return result.get("ts")
        else:
            logger.error(f"Slack API error: {result.get('error')}")
            return None
    except requests.RequestException as e:
        logger.error(f"Request error: {e}")
        return None

def read_input() -> tuple[str, str | None]:
    if len(sys.argv) < 2:
        with tempfile.NamedTemporaryFile(delete=False, mode='w+') as tmp:
            tmp.write(sys.stdin.read())
            return tmp.name, tmp.name
    return sys.argv[1], None

def extract_lines(filepath: str) -> list[str] | None:
    try:
        with open(filepath, 'r') as f:
            lines = f.readlines()
            logger.info(f"Successfully read {len(lines)} lines from {filepath}")
            return lines
    except IOError as e:
        logger.error(f"IOError reading file {filepath}: {e}")
        msg = f":large_red_square: *Error:* File {filepath} does not exist or is not readable"
        send_simple_message(msg, BOT_USERNAME)
        return None

def find_last_subject(lines: list[str]) -> str | None:
    for i in reversed(range(len(lines))):
        if lines[i].startswith("Subject:"):
            subject = lines[i].strip().split("Subject:", 1)[1].strip()
            logger.info(f"Found subject: {subject}")
            return subject
    logger.warning("No Subject line found in the file")
    return None

def find_content_indices(lines: list[str]) -> tuple[int | None, int | None]:
    start = end = None

    # Look for different possible patterns
    for i in reversed(range(len(lines))):
        if re.match(r"^Unattended upgrade", lines[i]) or re.match(r"^unattended upgrades", lines[i]):
            start = i
            break
        elif re.match(r"^No packages found", lines[i]):
            start = i
            break
        elif re.match(r"^Starting unattended upgrades script", lines[i]):
            start = i
            break

    # Look for end patterns
    for i in reversed(range(len(lines))):
        if re.match(r"^Package installation log:", lines[i]):
            end = i - 1
            break
        elif re.match(r"^unattended-upgrades log:", lines[i]):
            end = i - 1
            break

    # If no end pattern found, use the last non-empty line
    if start is not None and end is None:
        for i in reversed(range(len(lines))):
            if lines[i].strip():  # Find last non-empty line
                end = i
                break

    if start is not None and end is not None:
        logger.info(f"Content section found: lines {start} to {end}")
    else:
        logger.warning("Could not determine content section boundaries")

    return start, end

def find_log_indices(lines: list[str]) -> tuple[int | None, int | None]:
    start = end = None
    for i in range(len(lines)):
        if re.match(r"^Package installation log:", lines[i]):
            start = i  # Start at the "Package installation log:" line
            break
    for i in reversed(range(len(lines))):
        if re.match(r"^Log ended:", lines[i]):
            end = i - 1  # End before the "Log ended:" line
            break

    if start is not None and end is not None:
        logger.info(f"Log section found: lines {start} to {end}")
    else:
        logger.warning("Could not determine log section boundaries")

    return start, end

def create_main_message_blocks(subject: str, content: str) -> list[dict]:
    """Create rich formatted blocks for main message"""
    # Determine status and emoji based on subject and content
    status_emoji = "ℹ️"
    status_text = "Info"

    # Check content for different scenarios
    content_lower = content.lower()
    if 'no packages found' in content_lower or 'no packages found that can be upgraded' in content_lower:
        status_emoji = "ℹ️"
        status_text = "No Updates Available"
    elif 'success' in subject.lower() or 'all upgrades installed' in content_lower:
        status_emoji = "✅"
        status_text = "Success"
    elif 'failed' in subject.lower() or 'error' in subject.lower():
        status_emoji = "❌"
        status_text = "Failed"
    elif 'warning' in subject.lower():
        status_emoji = "⚠️"
        status_text = "Warning"

    # Check if reboot is required
    reboot_required = "reboot required" in subject.lower() or "reboot-required" in content_lower
    reboot_emoji = "🔄" if reboot_required else ""

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"System Update Notification"
            }
        },
        {
            "type": "section",
            "fields": [
                {
                    "type": "mrkdwn",
                    "text": f"*Status:*\n{status_emoji} {status_text}"
                },
                {
                    "type": "mrkdwn",
                    "text": f"*Reboot:*\n{reboot_emoji} {'Required' if reboot_required else 'Not Required'}"
                }
            ]
        }
    ]
    return blocks

def main() -> None:
    logger.info("Starting notification script")

    input_file, tmp_file = read_input()
    logger.info(f"Input file: {input_file}, Temporary file: {tmp_file}")

    lines = extract_lines(input_file)
    if lines is None:
        logger.error("Failed to extract lines from input file")
        if tmp_file:
            os.unlink(tmp_file)
            logger.info("Cleaned up temporary file")
        return

    subject = find_last_subject(lines)
    if not subject:
        logger.error("No subject found, sending error message")
        send_simple_message(f":large_red_square: *Error:* No Subject line found in {input_file}", BOT_USERNAME)
        if tmp_file:
            os.unlink(tmp_file)
            logger.info("Cleaned up temporary file")
        return

    start, end = find_content_indices(lines)
    if start is None or end is None:
        logger.error("Could not determine content boundaries, sending error message")
        send_simple_message(f":large_red_square: *Error:* No valid content section found in {input_file}", BOT_USERNAME)
        if tmp_file:
            os.unlink(tmp_file)
            logger.info("Cleaned up temporary file")
        return

    content = ''.join(lines[start:end + 1])
    logger.info(f"Extracted content: {len(content)} characters")

    # Send main message with rich formatting
    logger.info("Sending main message")
    blocks = create_main_message_blocks(subject, content)
    thread_ts = send_to_slack_blocks(blocks, BOT_USERNAME)

    if thread_ts:
        logger.info(f"Main message sent successfully, thread timestamp: {thread_ts}")

        # Send Update Details in a thread
        logger.info("Sending Update Details in thread")
        update_details_blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": "📝 Update Details"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"```{content}```"
                }
            }
        ]
        update_ts = send_to_slack_blocks(update_details_blocks, BOT_USERNAME, thread_ts)
        if update_ts:
            logger.info("Update Details sent successfully")
        else:
            logger.warning("Failed to send Update Details")

        # Find and send log content in thread
        log_start, log_end = find_log_indices(lines)
        if log_start is not None and log_end is not None and log_start <= log_end:
            log_content = ''.join(lines[log_start:log_end + 1])
            if log_content.strip():
                logger.info("Sending Package Installation Log in thread")
                # Send log as collapsible section in thread
                log_blocks = [
                    {
                        "type": "header",
                        "text": {
                            "type": "plain_text",
                            "text": "📋 Package Installation Log"
                        }
                    },
                    {
                        "type": "section",
                        "text": {
                            "type": "mrkdwn",
                            "text": f"```{log_content}```"
                        }
                    }
                ]
                log_ts = send_to_slack_blocks(log_blocks, BOT_USERNAME, thread_ts)
                if log_ts:
                    logger.info("Package Installation Log sent successfully")
                else:
                    logger.warning("Failed to send Package Installation Log")
        else:
            logger.info("No package installation log found, sending info message")
            # Send info message if no log found
            send_simple_message("ℹ️ *Note:* No package installation log found in this update", BOT_USERNAME, thread_ts)
    else:
        logger.error("Failed to send main message")

    if tmp_file:
        os.unlink(tmp_file)
        logger.info("Cleaned up temporary file")

    logger.info("Notification script completed")

if __name__ == "__main__":
    main()
