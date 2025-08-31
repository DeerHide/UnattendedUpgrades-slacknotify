#!/bin/python3

from dataclasses import dataclass
from enum import Enum
import sys
import tempfile
import os
import re
import requests
import json # noqa: F401 
import logging
from datetime import datetime
from typing import Optional, List, Tuple, Dict, Any

# BUILD::LOG_DIR::REPLACE
BASE_LOG_DIR = "./logs/notifyslack"
# BUILD::LOG_DIR::END

# BUILD::LOG_LEVEL::REPLACE
LOG_LEVEL = logging.DEBUG
# BUILD::LOG_LEVEL::END

# user id is prefixed with @, e.g. @U076T6095FG
# group id is prefixed with !subteam^, e.g. !subteam^SAZ94GDB8
# you can also use !here or !channel to mention the entire channel
# BUILD::MENTION_IDS::REPLACE
MENTION_IDS = {
    'FAILED':   [],
    'WARNING':  [],
    'NO_UPDATES_REBOOT_PENDING': [],
    'SUCCESS': [],
    'INFO': [],
    'NO_UPDATES': [],
}
# BUILD::MENTION_IDS::END

# BUILD::SLACK_CONFIG::REPLACE
import config
SLACK_TOKEN = config.SLACK_TOKEN  # Bot User OAuth Token
SLACK_CHANNEL = config.SLACK_CHANNEL  # Channel ID or name
HOSTNAME = config.HOSTNAME  # Hostname of the machine
USERNAME = config.USERNAME  # Username running the update
BOT_USERNAME = config.BOT_USERNAME  # Bot username for Slack
# BUILD::SLACK_CONFIG::END

# Slack message limits
SLACK_MAX_CHARS = 12000  # Slack's actual character limit per message

# BUILD::DEBUG_CODE::REMOVE
# This debug code will be removed during build
print("Debug: log level set to", LOG_LEVEL)
# BUILD::DEBUG_CODE::END


class LoggerManager:
    
    def __init__(self, base_dir: str = BASE_LOG_DIR):
        self.base_dir = base_dir
        self.logger = None
        self.setup()
    
    def setup(self) -> logging.Logger:
        now = datetime.now()
        date_str = now.strftime("%Y%m%d")  

        os.makedirs(self.base_dir, exist_ok=True)
        log_file = os.path.join(self.base_dir, f"{date_str}_notifyslack.log")

        logging.basicConfig(
            level=LOG_LEVEL,
            format='%(asctime)s [%(levelname)s] %(funcName)s:%(lineno)d %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
        return self.logger
    
    def get_logger(self) -> logging.Logger:
        if self.logger is None:
            return self.setup()
        return self.logger

_logger = LoggerManager(BASE_LOG_DIR).get_logger()

class ContentParser:
    """Handles parsing and validation of email input from unattended-upgrades"""
    
    def __init__(self):
        pass
    
    def process_input(self) -> Tuple[str, Optional[str]]:
        """Process input from command (arg vs stdin)"""
        if len(sys.argv) < 2:
            with tempfile.NamedTemporaryFile(delete=False, mode='w+') as tmp:
                tmp.write(sys.stdin.read())
                return tmp.name, tmp.name
        return sys.argv[1], None
    
    def extract_lines(self, filepath: str) -> Optional[List[str]]:
        """Read and extract lines from the input file"""
        try:
            with open(filepath, 'r') as f:
                lines = f.readlines()
                _logger.info(f"Successfully read {len(lines)} lines from {filepath}")
                return lines
        except IOError as e:
            _logger.error(f"IOError reading file {filepath}: {e}")
            return None
    
    def find_last_subject(self, lines: List[str]) -> Optional[str]:
        """Find the last Subject line in the email content"""
        for i in reversed(range(len(lines))):
            if lines[i].startswith("Subject:"):
                subject = lines[i].strip().split("Subject:", 1)[1].strip()
                _logger.info(f"Found subject: {subject}")
                return subject
        _logger.warning("No Subject line found in the file")
        return None
    
    def find_content_indices(self, lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
        """Find the start and end indices of the main content section"""
        start = end = None

        # Pre-compile regex patterns
        start_patterns = [
            re.compile(r"^Unattended upgrade"),
            re.compile(r"^unattended upgrades"), 
            re.compile(r"^No packages found"),
            re.compile(r"^Starting unattended upgrades script")
        ]
        
        end_patterns = [
            re.compile(r"^Package installation log:"),
            re.compile(r"^unattended-upgrades log:")
        ]
        
        # Iterate over the list in reverse
        start = end = None
        for i in reversed(range(len(lines))):
            line = lines[i]
            
            if start is None:
                for pattern in start_patterns:
                    if pattern.match(line):
                        start = i
                        break
            
            if end is None:
                for pattern in end_patterns:
                    if pattern.match(line):
                        end = i - 1
                        break
            
            if start is not None and end is not None:
                break

        # If no end pattern found, go with the last non-empty line
        if start is not None and end is None:
            for i in reversed(range(len(lines))):
                if lines[i].strip():  # Find the last non-empty line
                    end = i
                    break

        if start is not None and end is not None:
            _logger.info(f"Content section found: lines {start} to {end}")
        else:
            _logger.warning("Could not determine content section boundaries")

        return start, end
    
    def find_log_indices(self, lines: List[str]) -> Tuple[Optional[int], Optional[int]]:
        """Find the start and end indices of the package installation log"""
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
            _logger.info(f"Log section found: lines {start} to {end}")
        else:
            _logger.warning("Could not determine log section boundaries")

        return start, end

class UpdateStatus(Enum):
    """Enumeration of possible update statuses"""
    NO_UPDATES  = 1
    NO_UPDATES_REBOOT_PENDING = 2
    SUCCESS     = 3
    FAILED      = 4
    WARNING     = 5
    INFO        = 6

@dataclass(frozen=True, slots=True)
class UpdateResult:
    """Data class containing status information"""
    status: UpdateStatus
    emoji: str
    text: str
    patterns: List[str]
    mention_ids: str = None

    def matches(self, text: str) -> bool:
        text_casefold = text.casefold()
        return any(pattern.casefold() in text_casefold for pattern in self.patterns)
    
    def matches_all(self, text: str) -> bool:
        """Check if ALL patterns match (for more specific statuses)"""
        text_casefold = text.casefold()
        return all(pattern.casefold() in text_casefold for pattern in self.patterns)

class ResultDeterminer:
    """Determines the status of unattended upgrades based on email content"""

    STATUS_MAPPINGS = {
        UpdateStatus.NO_UPDATES: UpdateResult(
            status=UpdateStatus.NO_UPDATES,
            emoji=":information_source:",
            text="No Updates Available",
            patterns=["no packages found", "no packages found that can be upgraded"],
            mention_ids=MENTION_IDS['NO_UPDATES']
        ),
        UpdateStatus.NO_UPDATES_REBOOT_PENDING: UpdateResult(
            status=UpdateStatus.NO_UPDATES_REBOOT_PENDING,
            emoji=":warning:",  # Override emoji
            text="No Updates/Reboot Pending",  # Override text
            patterns=["no packages found that can be upgraded", "reboot required"],  # More specific patterns
            mention_ids=MENTION_IDS['NO_UPDATES_REBOOT_PENDING'] # Override mentions
        ),
        UpdateStatus.SUCCESS: UpdateResult(
            status=UpdateStatus.SUCCESS,
            emoji=":white_check_mark:",
            text="Success",
            patterns=["success", "all upgrades installed"],
            mention_ids=MENTION_IDS['SUCCESS']
        ),
        UpdateStatus.FAILED: UpdateResult(
            status=UpdateStatus.FAILED,
            emoji=":red_circle:",
            text="Failed",
            patterns=["failed", "error"],
            mention_ids=MENTION_IDS['FAILED']
        ),
        UpdateStatus.WARNING: UpdateResult(
            status=UpdateStatus.WARNING,
            emoji=":warning:",
            text="Warning",
            patterns=["warning"],
            mention_ids=MENTION_IDS['WARNING']
        ),
        UpdateStatus.INFO: UpdateResult(
            status=UpdateStatus.INFO,
            emoji=":information_source:",
            text="Info",
            patterns=[],
            mention_ids=MENTION_IDS['INFO']
        )
    }

    @classmethod
    def get_status(cls, subject: str, content: str) -> UpdateResult:
        """Determine the status based on email subject and content with priority"""
        subject_casefold = subject.casefold()
        content_casefold = content.casefold()
        
        # Check the more specific NO_UPDATES_REBOOT_PENDING case first (requires both patterns)
        combined_text = f"{subject_casefold} {content_casefold}"
        if cls.STATUS_MAPPINGS[UpdateStatus.NO_UPDATES_REBOOT_PENDING].matches_all(combined_text):
            return cls.STATUS_MAPPINGS[UpdateStatus.NO_UPDATES_REBOOT_PENDING]
        
        # Check other statuses in priority order
        for status in [UpdateStatus.FAILED, UpdateStatus.WARNING, UpdateStatus.SUCCESS, UpdateStatus.NO_UPDATES, UpdateStatus.INFO]:
            if cls.STATUS_MAPPINGS[status].matches(subject_casefold) or cls.STATUS_MAPPINGS[status].matches(content_casefold):
                return cls.STATUS_MAPPINGS[status]
        
        return cls.STATUS_MAPPINGS[UpdateStatus.INFO]

    @classmethod
    def is_reboot_required(cls, subject: str, content: str) -> bool:
        subject_casefold = subject.casefold()
        content_casefold = content.casefold()
        
        reboot_patterns = [
            "reboot required",
            "reboot-required", 
            "reboot_required",
            "reboot is required"
        ]
        
        return any(pattern in subject_casefold or pattern in content_casefold 
                   for pattern in reboot_patterns)

class SlackMessageFormatter:
    """Creates and formats Slack message blocks"""
    
    def __init__(self, max_chars: int = SLACK_MAX_CHARS):
        self.max_chars = max_chars
    
    def create_main_message_blocks(self, subject: str, content: str) -> List[Dict[str, Any]]:
        """Create rich formatted blocks for main message"""

        status_info = ResultDeterminer.get_status(subject, content)
        status_emoji = status_info.emoji
        status_text = status_info.text
        reboot_required = ResultDeterminer.is_reboot_required(subject, content)
        reboot_emoji = ":arrows_counterclockwise:" if reboot_required else ""

        reboot_required_str = "Required"
        if status_info.status == UpdateStatus.FAILED:
            reboot_emoji = ":warning:"

        if status_info.mention_ids and len(status_info.mention_ids) > 0:
            mentions = []
            for mention_id in status_info.mention_ids:
                mentions.append(f"<{mention_id}>")
            mention_text = ", ".join(mentions)
        else:
            mention_text = ""

        blocks = [
            {
                "type": "header",
                "text": 
                {
                    "type": "plain_text",
                    "text": "Package Update"
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
                        "text": f"*Reboot:*\n{reboot_emoji} {reboot_required_str if reboot_required else 'Not Required'}\n"
                    }
                ]
            },
            {
                "type": "context",
                "elements": [
                    {
                        "type": "plain_text",
                        "text": f"info: HOSTNAME: {config.HOSTNAME}, USERNAME: {config.USERNAME}, BOT_USERNAME: {config.BOT_USERNAME}"
                    }
                ]
            },
        ]
        _logger.debug(f"Blocks: {blocks}")
        _logger.debug(f"Mention Text: {mention_text}")
        if mention_text:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"*Notify:* {mention_text}"
                }
            })
        return blocks
    
    def create_update_details_blocks(self, content: str) -> List[Dict[str, Any]]:
        """Create blocks for update details section"""
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":pencil: Update Details"
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
    
    def create_log_blocks(self, log_content: str) -> List[Dict[str, Any]]:
        """Create blocks for package installation log section"""
        return [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": ":clipboard: Package Installation Log"
                }
            },
            {
                "type": "rich_text",
                "elements": [
                    {
                        "type": "rich_text_preformatted",
                        "elements": [
                            {
                                "type": "text",
                                "text": f"```{log_content}```"
                            }
                        ]
                    }
                ]
            }
        ]

class SlackClient:
    """Handles communication with Slack API"""
    
    def __init__(self, token: str, channel: str):
        self.token = token
        self.channel = channel
        self.base_url = "https://slack.com/api/chat.postMessage"
        self.headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
    
    def send_blocks(self, blocks: List[Dict[str, Any]], username: Optional[str] = None, 
                    thread_ts: Optional[str] = None) -> Optional[str]:
        """Send message with rich formatting using Slack blocks"""
        _logger.info(f"Sending Slack message with {len(blocks)} blocks")

        payload = {
            "channel": self.channel,
            "blocks": blocks
        }

        if username:
            payload["username"] = username

        if thread_ts:
            payload["thread_ts"] = thread_ts

        return self._send_request(payload)
    
    def send_simple_message(self, text: str, username: Optional[str] = None, 
                           thread_ts: Optional[str] = None) -> Optional[str]:
        """Send simple text message with automatic splitting for long content"""

        _logger.info(f"Sending simple Slack message: {text[:100]}...")

        # Split long messages if needed
        if len(text) > SLACK_MAX_CHARS:
            _logger.info(f"Message too long ({len(text)} chars), splitting into chunks")
            chunks = self._split_message(text)
            timestamps = []

            for i, chunk in enumerate(chunks):
                chunk_text = f"*Part {i+1}/{len(chunks)}*\n{chunk}"
                ts = self._send_simple_chunk(chunk_text, username, thread_ts)
                if ts:
                    timestamps.append(ts)
                    thread_ts = ts  # Use the last timestamp for threading

            return timestamps[0] if timestamps else None
        else:
            return self._send_simple_chunk(text, username, thread_ts)
    
    def _split_message(self, text: str) -> List[str]:
        """Split message into chunks that fit Slack limits"""
        if len(text) <= SLACK_MAX_CHARS:
            return [text]

        chunks = []
        current_chunk = ""

        for line in text.split('\n'):
            if len(current_chunk) + len(line) + 1 <= SLACK_MAX_CHARS:
                current_chunk += line + '\n'
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = line + '\n'

        if current_chunk:
            chunks.append(current_chunk.strip())

        return chunks
    
    def _send_simple_chunk(self, text: str, username: Optional[str] = None, 
                           thread_ts: Optional[str] = None) -> Optional[str]:
        """Send a single chunk of a simple text message"""
        payload = {
            "channel": self.channel,
            "text": text
        }

        if username:
            payload["username"] = username

        if thread_ts:
            payload["thread_ts"] = thread_ts

        return self._send_request(payload)
    
    def _send_request(self, payload: Dict[str, Any]) -> Optional[str]:
        """Send request to Slack API and handle response"""
        
        _logger.debug(f"Sending request to Slack API")
        _logger.debug(f"{payload}")

        try:
            response = requests.post(self.base_url, headers=self.headers, json=payload)
            response.raise_for_status()
            result = response.json()

            if result.get("ok"):
                _logger.info("Slack message sent successfully")
                return result.get("ts")  # Return timestamp for threading
            else:
                _logger.error(f"Slack API error: {result.get('error')}")
                return None
        except requests.RequestException as e:
            _logger.error(f"Request error: {e}")
            return None
        except requests.HTTPError as e:
            _logger.error(f"HTTP error: {e}")
            return None
        except requests.Timeout as e:
            _logger.error(f"Timeout error: {e}")
            return None
        except Exception as e:
            _logger.error(f"Exception: {e}")
            return None


class UpdateNotifier:
    """Main orchestrator class that coordinates the notification process"""
    
    def __init__(self, config: Dict[str, str]):
        self.config = config
        self.email_parser = ContentParser()
        self.message_formatter = SlackMessageFormatter()
        self.slack_client = SlackClient(
            config['SLACK_TOKEN'], 
            config['SLACK_CHANNEL']
        )
    
    def process_and_notify(self) -> None:
        """Main workflow for processing updates and sending notifications"""
        _logger.info("Starting notification process")

        # Process input
        input_file, tmp_file = self.email_parser.process_input()
        _logger.info(f"Input file: {input_file}, Temporary file: {tmp_file}")

        try:
            # Extract and validate content
            lines = self._extract_log_blocks_and_validate_content(input_file)
            if lines is None:
                return

            subject = self._extract_subject(lines)
            if not subject:
                return

            content = self._extract_main_content(lines)
            if not content:
                return

            # Send notifications
            self._send_notifications(subject, content, lines)

        finally:
            # Cleanup
            if tmp_file:
                os.unlink(tmp_file)
                _logger.info("Cleaned up temporary file")

    def _send_error_message(self, message: str) -> None:
        """Send error message to Slack with fake UpdateStatus.FAILED"""
        _logger.error(f"Sending error message to Slack: {message}")
        
        # Create a fake UpdateResult with FAILED status
        failed_result = UpdateResult(
            status=UpdateStatus.FAILED,
            emoji=":red_circle:",
            text="Failed",
            patterns=["error"],
            mention_ids=MENTION_IDS['FAILED']
        )
        
        # Use the message formatter to create properly formatted blocks
        blocks = self.message_formatter.create_main_message_blocks(
            subject=f"ERROR: {message}",
            content=f"An error occurred during the update process: {message}"
        )
        
        # Add error details at the end
        error_block = {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Reason:* {message}"
            }
        }
        blocks.append(error_block)
        
        # Send the formatted message
        self.slack_client.send_blocks(blocks, self.config['BOT_USERNAME'])
    
    def _extract_log_blocks_and_validate_content(self, input_file: str) -> Optional[List[str]]:
        """Extract lines from input file with validation"""
        lines = self.email_parser.extract_lines(input_file)
        if lines is None:
            _logger.error("Failed to extract lines from input file")
            self._send_error_message(f"File {input_file} does not exist or is not readable")
            return None
        return lines
    
    def _extract_subject(self, lines: List[str]) -> Optional[str]:
        """Extract subject with error handling"""
        subject = self.email_parser.find_last_subject(lines)
        if not subject:
            _logger.error("No subject found, sending error message")
            self._send_error_message(f"No Subject line found in input file")
            return None
        return subject
    
    def _extract_main_content(self, lines: List[str]) -> Optional[str]:
        """Extract main content with error handling"""
        start, end = self.email_parser.find_content_indices(lines)
        if start is None or end is None:
            _logger.error("Could not determine content boundaries, sending error message")
            self._send_error_message(f"No valid content section found in input file")
            return None
        
        content = ''.join(lines[start:end + 1])
        _logger.info(f"Extracted content: {len(content)} characters")
        return content
    
    def _send_notifications(self, subject: str, content: str, lines: List[str]) -> None:
        """Send all notification messages"""
        # Send main message with rich formatting
        _logger.info("Sending main message")
        blocks = self.message_formatter.create_main_message_blocks(subject, content)
        thread_ts = self.slack_client.send_blocks(blocks, self.config['BOT_USERNAME'])

        if thread_ts:
            _logger.info(f"Main message sent successfully, thread timestamp: {thread_ts}")
            self._send_thread_messages(content, lines, thread_ts)
        else:
            _logger.error("Failed to send main message")
    
    def _send_thread_messages(self, content: str, lines: List[str], thread_ts: str) -> None:
        """Send additional messages in the thread"""
        # Send Update Details in thread
        _logger.info("Sending Update Details in thread")
        update_details_blocks = self.message_formatter.create_update_details_blocks(content)
        update_ts = self.slack_client.send_blocks(
            update_details_blocks, 
            self.config['BOT_USERNAME'], 
            thread_ts
        )
        if update_ts:
            _logger.info("Update Details sent successfully")
        else:
            _logger.warning("Failed to send Update Details")

        # Find and send log content in thread
        self._send_log_content(lines, thread_ts)
    
    def _send_log_content(self, lines: List[str], thread_ts: str) -> None:
        """Send package installation log in thread if available"""
        log_start, log_end = self.email_parser.find_log_indices(lines)
        if log_start is not None and log_end is not None and log_start <= log_end:
            log_content = ''.join(lines[log_start:log_end + 1])
            if log_content.strip():
                _logger.info("Sending Package Installation Log in thread")
                log_blocks = self.message_formatter.create_log_blocks(log_content)
                log_ts = self.slack_client.send_blocks(
                    log_blocks, 
                    self.config['BOT_USERNAME'], 
                    thread_ts
                )
                if log_ts:
                    _logger.info("Package Installation Log sent successfully")
                else:
                    _logger.warning("Failed to send Package Installation Log")
        else:
            _logger.info("No package installation logs found, sending info message")
            self.slack_client.send_simple_message(
                "*Note:* No package installation logs were found during this run",
                self.config['BOT_USERNAME'],
                thread_ts
            )


def main() -> None:
    """Main entry point"""
    # Initialize logging    
    _logger.info("Starting notification script")

    # Load configuration
    config_dict: Dict[str, str] = {
        'SLACK_TOKEN': SLACK_TOKEN,
        'SLACK_CHANNEL': SLACK_CHANNEL,
        'HOSTNAME': HOSTNAME,
        'USERNAME': USERNAME, 
        'BOT_USERNAME': BOT_USERNAME
    }

    # Create and run notifier
    notifier = UpdateNotifier(config_dict)
    notifier.process_and_notify()


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        _logger.error(f"Error: {e}")
        raise e
    finally:
        _logger.info("Notification script completed")
