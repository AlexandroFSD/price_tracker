# src/main.py

"""
Main entry point for the Product Price Tracker application.

Handles application setup, configuration loading, component initialization
(fetcher, notifiers, tracker), and running the price checking process.
Manages asynchronous execution and resource cleanup.
"""

import asyncio
import logging.handlers  # Required for RotatingFileHandler
import os
from typing import Optional, List  # Import used types

# Specific imports for Telegram notifications using aiogram
from aiogram import Bot as AiogramBot
from dotenv import load_dotenv  # For loading environment variables from .env

# Import components from the local 'src' package
# Use relative imports as main.py is run as part of the package (python -m src.main)
from .config import load_config, CONFIG_FILE, AppConfig
from .database import DATABASE_FILE  # Import DATABASE_FILE name
from .fetcher import PriceFetcher
# Assuming Notifier is a base class and EmailNotifier/TelegramNotifier are concrete implementations
from .notifiers import EmailNotifier, TelegramNotifier, Notifier
from .tracker import Tracker

# Note: As of aiogram v3, exceptions are typically accessed via aiogram.exceptions


# --- Configure Logging to File and Console ---
LOG_DIR = 'logs' # Directory for log files
LOG_FILE = os.path.join(LOG_DIR, 'price_tracker.log') # Full path to the log file

# Create the log directory if it does not exist
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# Configure the root logger
# Sets the minimum logging level and format for all loggers in the application
# Using basicConfig is a simple way to set up handlers for the root logger.
logging.basicConfig(
    level=logging.DEBUG, # Set initial level to DEBUG to capture all messages
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', # Standard log format
    handlers=[
        # Handler to output logs to the console (stderr by default)
        logging.StreamHandler(),
        # Handler to output logs to a file with rotation (max 5MB per file, keep 5 backups)
        logging.handlers.RotatingFileHandler(
            LOG_FILE,
            maxBytes=1024 * 1024 * 5, # 5 MB
            backupCount=5, # Keep up to 5 backup files
            encoding='utf-8' # Ensure correct encoding for file output
        )
    ]
)

# Get a logger for this specific module (__main__)
logger = logging.getLogger(__name__)


# --- Main Asynchronous Function ---
async def main():
    """
    Main asynchronous function to set up and run the price tracking process.

    This function orchestrates the application flow:
    1. Loads environment variables from .env.
    2. Loads and validates application configuration from the config file.
    3. Initializes core components: PriceFetcher, Notifiers (Email, Telegram), and Tracker.
    4. Runs the main price checking logic within the Tracker.
    5. Handles potential unhandled errors during the process.
    6. Ensures asynchronous resources (like the Aiogram Bot session) are closed gracefully.

    It relies on the configuration defined in items_config.json (or equivalent)
    and sensitive details from the .env file.
    """
    logger.info("Application started.")

    # Load environment variables from the .env file in the project root.
    # This should be done early before attempting to access env vars for config or secrets.
    load_dotenv()
    logger.info(".env file loaded.")


    # Load application configuration from the defined config file (e.g., items_config.json).
    # The load_config function handles file path resolution and basic validation.
    app_config: Optional[AppConfig] = load_config(CONFIG_FILE)

    # Exit the application if configuration loading or validation failed.
    if app_config is None:
        logger.critical("Failed to load application configuration. Exiting.")
        return # Exit the main function

    # Extract items to track and global notification channels from the loaded configuration.
    # Use .get() with default values to safely access optional keys without errors if they are missing.
    items_to_track = app_config.get("items", [])
    global_notification_channels = app_config.get("global_notification_channels", [])
    # Retrieve optional database path from config, defaulting to DATABASE_FILE constant
    database_path = app_config.get("database_path", DATABASE_FILE)


    # Check if there are any valid items configured to track after loading and validation.
    if not items_to_track:
        logger.info(f"No valid items to track found in '{CONFIG_FILE}'. Exiting.")
        return # Exit if no items are configured, as there is nothing to track.


    # --- Initialize Core Components ---

    # Initialize the PriceFetcher which is responsible for fetching web content and parsing prices.
    price_fetcher = PriceFetcher()
    logger.info("PriceFetcher initialized.")


    # --- Initialize Notifiers ---
    # Notifier instances need to be initialized here in main() to configure them
    # and pass the list of available notifiers to the Tracker.
    # The Aiogram Bot instance, being an async resource, is also best managed here.

    # Retrieve Telegram Bot Token from environment variables loaded by load_dotenv().
    telegram_bot_token: Optional[str] = os.getenv("TELEGRAM_BOT_TOKEN")
    telegram_bot_instance: Optional[AiogramBot] = None # Initialize bot instance variable to None

    # Create Aiogram Bot instance only if a Telegram bot token was successfully found in environment variables.
    if telegram_bot_token:
         try:
             # Initialize the Aiogram Bot with the retrieved token.
             # Bot instantiation itself is synchronous, but it manages an async session internally.
             telegram_bot_instance = AiogramBot(token=telegram_bot_token)
             logger.info("Aiogram Bot instance created.")

             # Optional early validation: You could call `await telegram_bot_instance.get_me()` here
             # to verify the token and connection early. If you do this, main() would need to
             # handle potential aiogram exceptions (like TelegramNetworkError, TelegramUnauthorizedError).
             # For simplicity, we rely on the Notifier's send method to handle connection errors.

         except Exception as e:
             # Log any errors that occur during Aiogram Bot instantiation (e.g., invalid token format, basic connection issues).
             logger.error(f"Failed to initialize Aiogram Bot instance with provided token. Check TELEGRAM_BOT_TOKEN in .env: {e}")
             telegram_bot_instance = None # Ensure instance is explicitly None if initialization failed.


    # Create a list containing instances of all available notification channel notifiers.
    # EmailNotifier is included directly. TelegramNotifier is included only if the Bot instance was successfully created.
    all_notifiers: List[Notifier] = [
        EmailNotifier(), # Add EmailNotifier instance (assuming its config loading is internal)
        # Add TelegramNotifier instance only if telegram_bot_instance is valid.
        # The TelegramNotifier __init__ checks for CHAT_ID internally using dotenv_values.
        TelegramNotifier(bot_instance=telegram_bot_instance) if telegram_bot_instance is not None else None # Explicitly add None if bot failed
        # Add other notifier types here if they are implemented (e.g., SlackNotifier(api_key=os.getenv("SLACK_API_KEY")), ...)
    ]
    # Filter out any None values if optional notifiers (like TelegramNotifier) failed initialization
    all_notifiers = [notifier for notifier in all_notifiers if notifier is not None]

    logger.info(f"Initialized {len(all_notifiers)} notifiers.")


    # Initialize the main Tracker component which coordinates the price checking loop.
    # Pass the initialized fetcher, the list of all potential notifiers, the global
    # notification channels configuration, and the database path.
    tracker = Tracker(
        price_fetcher=price_fetcher,
        notifiers=all_notifiers, # Pass the list of all initialized notifiers
        global_notification_channels=global_notification_channels, # Pass the list of channels enabled globally
        database_path=database_path # Pass the database file path
    )
    logger.info("Tracker initialized.")


    # --- Run the Tracker's Price Check and ensure resources are closed ---
    # Use a try...finally block to ensure cleanup happens even if errors occur during the run.
    try:
        logger.info("Running price check...")
        # Await the asynchronous method that performs the main tracking logic
        # This method includes fetching, parsing, saving, and triggering notifications.
        await tracker.run_check(items_to_track)
        logger.info("Price check completed.")

    except Exception as e:
        # Catch and log any unhandled exceptions that occur during the tracker's main execution.
        # Log as critical with exc_info=True to include traceback for debugging.
        logger.critical(f"An unhandled error occurred during tracker run: {e}", exc_info=True)

    finally:
        # --- Cleanup Phase ---
        # This block is guaranteed to execute. Ensure asynchronous resources are closed.

        # Ensure the Aiogram Bot session is closed gracefully if a bot instance was successfully created.
        # Closing the session releases underlying network connections.
        if telegram_bot_instance: # Check if a bot instance variable holds a valid object
             # Check if the bot instance has an active session attribute to close
             if hasattr(telegram_bot_instance, 'session') and telegram_bot_instance.session:
                 try:
                    logger.info("Closing Aiogram Bot session...")
                    # Await the asynchronous session close operation.
                    await telegram_bot_instance.session.close()
                    logger.info("Aiogram Bot session closed.")
                 except Exception as e:
                    # Log any errors encountered while attempting to close the session.
                    logger.error(f"Error closing Aiogram Bot session: {e}")
             # Note: Database connections opened within save_price_data are closed immediately after use.
             # If Tracker held a persistent connection, it would need closing here.


    logger.info("Application finished.")


# --- Entry Point ---
# This block is executed when the script is run directly (e.g., using `python -m src.main`).
if __name__ == "__main__":
    # Use asyncio.run() to execute the main asynchronous function `main()`.
    # asyncio.run() handles creating and managing the event loop, running the
    # async function until completion, and properly shutting down the loop.
    try:
        asyncio.run(main())
    except Exception as e:
        # Catch any unhandled fatal exceptions that escape the `main()` function's
        # error handling and occur during the asyncio event loop management.
        # Log as critical with exc_info=True to include traceback.
        logger.critical(f"An unhandled fatal error occurred during application execution: {e}", exc_info=True)