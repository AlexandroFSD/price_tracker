# src/notifiers.py

"""
Handles sending notifications through various channels (e.g., Email, Telegram).

Defines an abstract base class `Notifier` and concrete implementations
for different notification methods.
"""

import logging
import smtplib
from email.mime.text import MIMEText
import asyncio
from typing import Optional, List, Dict, Any
from abc import ABC, abstractmethod
from dotenv import dotenv_values # For loading environment variables directly in notifiers

# Import specific classes from aiogram
from aiogram import Bot as AiogramBot
# Import specific exceptions for better error handling if needed
from aiogram.exceptions import TelegramNetworkError, TelegramBadRequest, TelegramForbiddenError


logger = logging.getLogger(__name__)

# Load environment variables from .env file when the module is imported.
# This is an alternative to loading only in main.py and passing values.
# It works for simple cases but might reload the file if imported multiple times.
config_env = dotenv_values(".env")

# Default executor for running synchronous blocking I/O (like SMTP sending)
# in an asynchronous context. None uses the default ThreadPoolExecutor.
default_executor = None


class Notifier(ABC):
    """
    Abstract base class for all notification channels.

    Defines the required interface that every notifier must implement.
    """

    @abstractmethod
    async def send_notification(self, alerts: List[Dict[str, Any]]):
        """
        Sends a notification containing a list of price alerts asynchronously.

        This method must be implemented by concrete notifier subclasses.

        Args:
            alerts: A list of dictionaries, where each dictionary represents
                    a price alert with details like 'item_name', 'url',
                    'current_price', and 'target_price'.
        """
        pass

    @property
    @abstractmethod
    def channel_name(self) -> str:
        """
        Returns the unique name of the notification channel.

        This property must be implemented by concrete notifier subclasses.
        Examples: 'email', 'telegram', 'slack'.

        Returns:
            A string representing the channel's name.
        """
        pass

    @property
    @abstractmethod
    def is_configured(self) -> bool:
        """
        Checks if the notifier is properly configured and ready to send notifications.

        This property must be implemented by concrete notifier subclasses
        to check for necessary settings (e.g., API keys, recipient addresses).

        Returns:
            True if the notifier is configured and operational, False otherwise.
        """
        pass


class EmailNotifier(Notifier):
    """
    Handles sending email notifications using SMTP.

    Configuration details (host, port, user, password, recipient) are loaded
    from environment variables defined in the .env file.
    """

    def __init__(self):
        """Initializes the EmailNotifier by loading configuration from .env."""
        # Load email configuration from environment variables
        self._email_host: Optional[str] = config_env.get("EMAIL_HOST")
        self._email_port: Optional[int] = None # Initialize port as None
        port_str = config_env.get("EMAIL_PORT")

        # Attempt to convert the port string to an integer
        if port_str:
            try:
                self._email_port = int(port_str)
            except ValueError:
                # Log an error if the port is not a valid number
                logger.error(f"Invalid value for EMAIL_PORT in .env. Expected a number, got '{port_str}'. Email notifications disabled.")

        self._email_user: Optional[str] = config_env.get("EMAIL_USER")
        self._email_password: Optional[str] = config_env.get("EMAIL_PASSWORD")
        self._email_recipient: Optional[str] = config_env.get("EMAIL_RECIPIENT")

        # Determine if the email notifier is fully configured
        self._is_configured: bool = all([
            self._email_host,
            self._email_port is not None, # Port must be a valid number
            self._email_user,
            self._email_password,
            self._email_recipient # Recipient must be set
        ])

        # Log a warning if the notifier is not configured
        if not self._is_configured:
            logger.warning("Email configuration not fully loaded or invalid from .env. Email notifications will be disabled.")


    @property
    def channel_name(self) -> str:
        """Returns the channel name 'email'."""
        return "email"

    @property
    def is_configured(self) -> bool:
        """Checks if all required email configuration settings are loaded."""
        return self._is_configured

    def _send_email_sync(self, subject: str, body: str):
        """
        Internal synchronous method to send the email via SMTP.

        This method is designed to be run in a separate thread using run_in_executor
        because SMTP operations are blocking.

        Args:
            subject: The subject of the email.
            body: The body content of the email.
        """
        # Basic check for configuration completeness before attempting send
        if not self.is_configured:
            logger.error("Attempted to send email but notifier is not configured.")
            return

        try:
            # Create the email message object
            msg = MIMEText(body, 'plain', 'utf-8')
            msg['Subject'] = subject
            msg['From'] = self._email_user
            msg['To'] = self._email_recipient

            logger.info(f"Attempting to send email notification via {self._email_host}:{self._email_port}...")

            # Determine the SMTP server type based on the port
            if self._email_port == 465:
                # Use SMTPS for port 465 (implicit SSL)
                server = smtplib.SMTP_SSL(self._email_host, self._email_port)
            elif self._email_port == 587:
                # Use SMTP for port 587 and start TLS explicitly
                server = smtplib.SMTP(self._email_host, self._email_port)
                server.starttls() # Upgrade the connection to TLS
            else:
                # Log an error for unsupported ports
                logger.error(f"Unsupported SMTP port {self._email_port}. Use 465 (SSL) or 587 (TLS).")
                return # Exit the sending process

            # Use a 'with' statement to ensure the SMTP server connection is closed
            with server:
                # Log in to the SMTP server
                server.login(self._email_user, self._email_password)
                # Send the email
                server.sendmail(self._email_user, self._email_recipient, msg.as_bytes())

            logger.info(f"Email notification sent successfully.")

        # Catch specific SMTP exceptions for better error reporting
        except smtplib.SMTPAuthenticationError:
            logger.error(f"SMTP Authentication failed. Check email user/password in .env. If using Gmail with 2FA, consider using an App Password.")
        except (smtplib.SMTPConnectError, ConnectionRefusedError) as e:
             logger.error(f"SMTP Connection failed to {self._email_host}:{self._email_port}. Check server/port, firewall, or network issues: {e}")
        except smtplib.SMTPException as e:
            logger.error(f"An SMTP error occurred during sending: {e}")
        except Exception as e:
            # Catch any other unexpected errors during the synchronous sending process
            logger.error(f"An unexpected error occurred while sending email: {e}")


    async def send_notification(self, alerts: List[Dict[str, Any]]):
        """
        Prepares email content and submits the synchronous sending task to an executor.

        This method is the asynchronous interface required by the Notifier ABC.

        Args:
            alerts: A list of dictionaries representing price alerts.
        """
        # Check configuration and if there are alerts to send
        if not self.is_configured:
            logger.warning("Skipping email notification: Configuration not loaded or invalid.")
            return
        if not alerts:
             logger.info("No email alerts to send.")
             return

        # Prepare the email subject and body content
        subject = f"Price Tracker Alert: {len(alerts)} item(s) reached target price!"
        body_intro = "Hello,\n\nThe following items have reached your target price or gone below it:\n\n"
        body_items = ""
        # Format details for each alert into the email body
        for alert in alerts:
             item_name = alert.get('item_name', 'Unnamed Item')
             url = alert.get('url', 'No URL')
             current_price = alert.get('current_price', 'N/A')
             target_price = alert.get('target_price', 'N/A')
             body_items += f"- Item: {item_name}\n  Current Price: {current_price}\n  Target Price: {target_price}\n  Link: {url}\n\n"

        body_outro = "It might be a good time to buy!\n\nThis is an automated notification from your price tracker."
        body = body_intro + body_items + body_outro

        # Log the full email body at debug level
        logger.debug(f"Email body content: {body}")

        try:
            # Get the currently running event loop
            loop = asyncio.get_running_loop()
            # Run the synchronous email sending method in the default thread pool executor
            # This prevents blocking the main asyncio event loop
            loop.run_in_executor(default_executor, self._send_email_sync, subject, body)
            logger.info("Email sending task submitted to executor.")

        except Exception as e:
            # Log errors if submitting the task to the executor fails
            logger.error(f"Failed to submit email sending task to executor: {e}")


class TelegramNotifier(Notifier):
    """
    Handles sending Telegram notifications using an aiogram Bot instance.

    Requires a pre-configured aiogram.Bot instance and a TELEGRAM_CHAT_ID
    loaded from environment variables.
    """

    # Modified __init__ to accept a configured AiogramBot instance
    def __init__(self, bot_instance: Optional[AiogramBot]):
        """
        Initializes the TelegramNotifier with a pre-configured Aiogram Bot instance.

        The Aiogram Bot instance should have been created and configured with
        the bot token in the main application entry point (`main.py`).
        The chat ID is loaded from environment variables within this notifier.

        Args:
            bot_instance: An initialized aiogram.Bot instance, or None if
                          Bot initialization failed in the main application.
        """
        self._bot: Optional[AiogramBot] = bot_instance
        # Retrieve chat_id from .env here as it's specific to the notifier's target.
        # Using config_env loaded at module level.
        self._chat_id: Optional[str] = config_env.get("TELEGRAM_CHAT_ID")


        # Determine if the notifier is configured.
        # Requires both the chat ID AND a valid bot instance.
        self._is_configured: bool = self._chat_id is not None and self._bot is not None

        # Log a warning if the notifier is not configured
        if not self._is_configured:
            reason = []
            if self._chat_id is None:
                reason.append("TELEGRAM_CHAT_ID not found in .env")
            if self._bot is None:
                 reason.append("Telegram Bot instance not initialized (check TELEGRAM_BOT_TOKEN)")
            logger.warning(f"Telegram configuration incomplete: {', '.join(reason)}. Telegram notifications will be disabled.")


    @property
    def channel_name(self) -> str:
        """Returns the channel name 'telegram'."""
        return "telegram"

    @property
    def is_configured(self) -> bool:
        """Checks if the chat ID and Bot instance are configured."""
        return self._is_configured # Simply return the pre-calculated status


    async def send_notification(self, alerts: List[Dict[str, Any]]):
        """
        Sends a Telegram notification containing a list of price alerts using aiogram.

        Requires the notifier to be configured (`is_configured` is True).
        Uses the asynchronous `self._bot.send_message` method.

        Args:
            alerts: A list of dictionaries representing price alerts.

        Raises:
            aiogram.exceptions.TelegramNetworkError: If a network error occurs
                                                    while communicating with the Telegram API.
            aiogram.exceptions.TelegramForbiddenError: If the bot cannot send
                                                       messages to the chat (e.g., bot kicked).
            aiogram.exceptions.TelegramBadRequest: If the request is malformed
                                                  (e.g., invalid chat ID, message too long - though length is checked).
            Exception: For any other unexpected errors during the sending process.
        """
        # Check if the notifier is configured (chat_id and bot instance are present)
        if not self.is_configured:
            logger.warning("Skipping Telegram notification: Not configured.")
            return

        # This check is redundant if is_configured is checked, but kept for clarity
        # if self._bot is None:
        #     logger.error("Telegram Bot instance is not initialized. Cannot send notification.")
        #     return
        # if self._chat_id is None:
        #      logger.error("Telegram chat ID is not configured. Cannot send notification.")
        #      return


        if not alerts:
             logger.info("No Telegram alerts to send.")
             return

        # --- Prepare the message content from alerts ---
        message_text_parts = ["📈 Price Tracker Alert! 📉\n"]

        # Format details for each alert into the message body
        for alert in alerts:
             item_name = alert.get('item_name', 'Unnamed Item')
             url = alert.get('url', 'No URL')
             current_price = alert.get('current_price', 'N/A')
             target_price = alert.get('target_price', 'N/A')

             # Add item details to the message parts
             message_text_parts.append(f"• Item: {item_name}\n  Price: {current_price} (Target: {target_price})\n  Link: {url}\n")

        # Add a concluding remark
        message_text_parts.append("\nIt might be a good time to buy!")
        # Join all parts into the final message string
        message_text = "\n".join(message_text_parts)

        # Log the full message content at debug level
        logger.debug(f"Telegram message content: {message_text}")

        # Check message length before sending to avoid Telegram API limits
        MAX_MESSAGE_LENGTH = 4096 # Maximum allowed length for a Telegram message
        if len(message_text) > MAX_MESSAGE_LENGTH:
             logger.warning(f"Telegram message for {len(alerts)} alerts is too long ({len(message_text)} characters > {MAX_MESSAGE_LENGTH}). It will be truncated.")
             # Truncate the message and add an ellipsis
             # Ensure truncation leaves space for the ellipsis and doesn't cut mid-character in rare cases (though basic ascii/utf8 is fine)
             if MAX_MESSAGE_LENGTH > 50: # Ensure there's enough space for meaningful content + ellipsis
                 message_text = message_text[:MAX_MESSAGE_LENGTH - 50].rsplit('\n', 1)[0] + "\n..." # Try to cut at last newline
                 if len(message_text) > MAX_MESSAGE_LENGTH: # Fallback if splitting by newline still exceeds limit
                     message_text = message_text[:MAX_MESSAGE_LENGTH - 3] + "..." # Simple truncation
             else: # For very small limits, just truncate
                 message_text = message_text[:MAX_MESSAGE_LENGTH]


        # --- Use asynchronous aiogram send_message method ---
        try:
            logger.info(f"Attempting to send Telegram message for {len(alerts)} item(s) to chat {self._chat_id} using aiogram...")
            # Call the asynchronous send_message method provided by the aiogram Bot instance
            await self._bot.send_message(chat_id=self._chat_id, text=message_text)

            logger.info(f"Telegram notification sent successfully to chat {self._chat_id} using aiogram.")

        # Catch specific aiogram exceptions for better error handling
        except TelegramNetworkError as e:
            logger.error(f"Telegram network error while sending message to chat {self._chat_id}: {e}")
        except TelegramForbiddenError:
             # This happens if the bot is blocked by the user or kicked from the group
             logger.error(f"Telegram bot is forbidden to send messages to chat {self._chat_id}. User might have blocked the bot or bot was kicked from the group.")
        except TelegramBadRequest as e:
             # This can happen for various reasons, including invalid chat ID or malformed message
             logger.error(f"Telegram bad request error while sending message to chat {self._chat_id}. Check chat ID or message content: {e}")
        except Exception as e:
            # Catch any other unexpected errors during the asynchronous sending process
            logger.error(f"An unexpected error occurred while sending Telegram message to chat {self._chat_id}: {e}")


# You could add other notifiers here (e.g., SmsNotifier) inheriting from Notifier