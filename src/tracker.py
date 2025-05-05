# src/tracker.py

"""
Orchestrates the price tracking process.

Manages fetching, parsing, saving data to the database, checking target prices,
and triggering notifications via configured channels.
"""

import logging
from typing import List, Dict, Any

import aiohttp
from aiohttp import TCPConnector  # Explicitly import used classes

from .database import save_price_data, initialize_database, \
    DATABASE_FILE  # Import database functions and constants
# Import necessary components from the local package
from .fetcher import PriceFetcher
from .notifiers import Notifier  # Import the base Notifier class

# Configure logger for this module
logger = logging.getLogger(__name__)


class Tracker:
    """
    Manages the end-to-end price tracking process.

    Handles fetching prices for multiple items, saving historical data,
    checking against target prices, and coordinating notifications
    through configured channels.
    """

    def __init__(
        self,
        price_fetcher: PriceFetcher,
        notifiers: List[Notifier],
        global_notification_channels: List[str],
        database_path: str = DATABASE_FILE # Accept db path, though initialize_database uses the default
    ):
        """
        Initializes the Tracker with necessary components and configuration.

        Initializes the database when the Tracker instance is created.

        Args:
            price_fetcher: An initialized instance of PriceFetcher for fetching and parsing.
            notifiers: A list of all initialized Notifier instances (both configured and not).
            global_notification_channels: A list of strings representing the names
                                          of notification channels enabled globally
                                          in the application configuration (e.g., ['telegram', 'email']).
            database_path: The path to the SQLite database file. Defaults to DATABASE_FILE.

        Raises:
            Exception: If an error occurs during database initialization.
                       This error is re-raised as it indicates a critical
                       setup failure.
        """
        self._price_fetcher = price_fetcher
        self._database_path = database_path # Store the database path

        # Store all notifier instances
        self._all_notifiers = notifiers
        # Create a dictionary mapping channel names to only the *configured* notifier instances
        self._configured_notifiers: Dict[str, Notifier] = {
            n.channel_name: n for n in notifiers if n.is_configured
        }
        # Log a warning if no notifiers are successfully configured
        if not self._configured_notifiers:
             logger.warning("No configured notifiers available. Price alerts will be logged but not sent via email/telegram.")

        # Store the list of globally enabled notification channel names
        self._global_notification_channels = global_notification_channels

        # Initialize the database when the Tracker is initialized.
        # Note: This ensures the database is ready before the first price check.
        # initialize_database handles creating the file/table if they don't exist.
        try:
            initialize_database(self._database_path)
            # No explicit success log needed here as initialize_database logs success
        except Exception as e: # initialize_database logs the specific error, we re-raise
            # Re-raise the exception to signal a fatal error during initialization,
            # which should be caught and handled at the application entry point (main.py).
            raise e # Re-raise the caught exception


    async def run_check(self, items_config: List[Dict[str, Any]]):
        """
        Runs the price check process for the configured items asynchronously.

        Fetches prices for all items concurrently, saves valid prices to the
        database, checks if current prices meet or beat target prices, and
        triggers notifications for triggered alerts via globally configured
        and available notification channels.

        Args:
            items_config: A list of item configuration dictionaries loaded
                          from the application configuration. Each dictionary
                          is expected to contain at least 'name', 'url',
                          'selector', and 'target_price'.
        """
        # Check if there are any items to process
        if not items_config:
            logger.info("No items provided to run check for.")
            return

        logger.info(f"Starting price check for {len(items_config)} items...")

        # Use a TCPConnector with a connection limit per host for better performance
        # and to avoid overwhelming servers.
        conn = TCPConnector(limit_per_host=10)
        # Use an async context manager for ClientSession to ensure it's closed properly
        async with aiohttp.ClientSession(connector=conn) as session:
            # Fetch and parse prices for all items concurrently using the PriceFetcher
            fetched_items_results = await self._price_fetcher.fetch_and_parse_all(session, items_config)

        # --- Process Results ---
        # Initialize a list to store price alerts that meet the target price criteria
        price_alerts: List[Dict[str, Any]] = []

        # Iterate through the results obtained from the fetcher
        for item_result in fetched_items_results:
            # Extract necessary information from the item result dictionary
            item_name = item_result.get('name', 'Unnamed Item') # Default name if missing
            item_url = item_result.get('url')
            item_target_price = item_result.get('target_price')
            current_price = item_result.get('price') # The parsed price (float or None)

            # Process the item only if a price was successfully retrieved
            if current_price is not None:
                logger.info(f"Processing '{item_name}': Current price is {current_price}")

                try:
                    # Save the current price data to the database
                    # save_price_data handles its own connection and closing
                    save_price_data(item_name, item_url, current_price, self._database_path)
                    # Log successful save (save_price_data logs errors internally)
                    logger.info(f"  Saved price data for '{item_name}' ({current_price}) to database.")
                except Exception:
                    # Catch any exception from save_price_data (it logs internally)
                    # We just pass here as we don't want a save error to stop processing alerts/other items
                    pass


                # Check if the current price meets or is below the target price
                # Ensure item_target_price is available before comparison
                if item_target_price is not None and current_price <= item_target_price:
                    logger.info(f"  Target price met for '{item_name}'! Adding to alerts.")

                    # Add the item's details to the price_alerts list
                    price_alerts.append({
                        'item_name': item_name,
                        'url': item_url,
                        'current_price': current_price,
                        'target_price': item_target_price,
                    })

                else:
                     # Log if the current price does not meet the target (if target exists)
                     if item_target_price is not None:
                          logger.info(f"  Current price ({current_price}) is above target price ({item_target_price}).")
                     else:
                          # Log if target price was missing or None for the item
                          logger.info(f"  Target price not specified for '{item_name}'. No alert triggered.")

            else:
                # Log if the price could not be retrieved for the item
                fetch_error = item_result.get('error', 'Unknown error')
                logger.warning(f"Processing '{item_name}': Failed to retrieve price. Status: {item_result.get('fetch_status', 'unknown')}, Error: {fetch_error}")

        logger.info("Price check finished. Processing alerts...")

        # --- Send Grouped Notifications ---
        # Check if any alerts were triggered
        if not price_alerts:
            logger.info("No price alerts triggered.")
            return

        # Determine which of the globally configured notification channels are actually available (configured notifiers)
        active_alert_channels = [
             channel_name for channel_name in self._global_notification_channels
             if channel_name in self._configured_notifiers
        ]

        # Log a warning if alerts were triggered but no active channels are configured globally
        if not active_alert_channels:
             logger.warning(f"Price alerts triggered for {len(price_alerts)} item(s), but none of the configured global channels ({', '.join(self._global_notification_channels)}) have an active notifier instance.")
             return # Exit notification process if no active channels

        # Log the number of alerts and the channels they will be sent through
        logger.info(f"Sending {len(price_alerts)} price alerts via {len(active_alert_channels)} globally active channels...")
        # Log the content of the alerts list at debug level for inspection
        logger.debug(f"Alerts list content: {price_alerts}")

        # Send the collected alerts via each active global notification channel
        for channel_name in active_alert_channels:
            # Retrieve the configured notifier instance for this channel
            notifier = self._configured_notifiers[channel_name]
            logger.info(f"Sending {len(price_alerts)} alert(s) via globally configured '{channel_name}' channel...")
            # Call the asynchronous send_notification method and AWAIT its completion
            await notifier.send_notification(price_alerts)