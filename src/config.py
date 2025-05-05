# src/config.py

"""Configuration loading and validation for the price tracker application."""

import json
import os
import logging
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# Define the default configuration file name
# Changed from "config.json" to "items_config.json" as requested.
CONFIG_FILE = "items_config.json"

# Type alias for the application configuration dictionary
AppConfig = Optional[Dict[str, Any]]


def load_config(config_path: str = CONFIG_FILE) -> AppConfig:
    """
    Loads and validates the application configuration from a JSON file.

    The configuration file is expected to contain a dictionary with keys
    like 'items' (a list of item configurations) and optional
    'global_notification_channels'. Basic validation is performed
    to ensure required keys and types are present for each item.

    Args:
        config_path: The path to the configuration file. Defaults to
                     the value of CONFIG_FILE ("items_config.json").

    Returns:
        A dictionary containing the validated configuration data if loading
        and validation are successful. Returns None if the file is not found,
        invalid JSON, or validation fails.
    """
    # Get the absolute path to the configuration file
    absolute_config_path = os.path.abspath(config_path)
    logger.info(f"Attempting to load configuration from {absolute_config_path}")

    # Check if the configuration file exists
    if not os.path.exists(absolute_config_path):
        logger.error(f"Configuration file '{config_path}' not found at {absolute_config_path}")
        return None

    try:
        # Open and load the configuration file as JSON
        with open(absolute_config_path, 'r', encoding='utf-8') as f:
            config_data = json.load(f)

        logger.info("Configuration file loaded.")

        # Perform basic validation on the loaded data
        if not isinstance(config_data, dict):
            logger.error("Configuration file root is not a dictionary.")
            return None

        # Validate the 'items' key - it must be a list
        items_config = config_data.get("items")
        if not isinstance(items_config, list):
            logger.error("Configuration key 'items' is missing or not a list.")
            return None

        # Validate each item within the 'items' list
        validated_items: List[Dict[str, Any]] = []
        # Define required keys for each item configuration
        required_item_keys = ["name", "url", "selector", "target_price"]

        # Iterate through each item and validate its structure and required keys
        for i, item in enumerate(items_config):
            # Ensure item is a dictionary
            if not isinstance(item, dict):
                logger.warning(f"Invalid item configuration at index {i}: not a dictionary. Skipping.")
                continue

            # Check for missing required keys in the item dictionary
            missing_keys = [key for key in required_item_keys if key not in item]
            if missing_keys:
                logger.warning(f"Invalid item configuration at index {i}: missing required keys {missing_keys}. Skipping item.")
                continue

            # Perform basic type validation for the required fields
            # 'name' must be a non-empty string
            if not isinstance(item["name"], str) or not item["name"].strip():
                 logger.warning(f"Invalid item configuration at index {i} ('name'): Must be a non-empty string. Skipping item.")
                 continue
            # 'url' must be a non-empty string
            if not isinstance(item["url"], str) or not item["url"].strip():
                 logger.warning(f"Invalid item configuration at index {i} ('url'): Must be a non-empty string. Skipping item.")
                 continue

            # 'selector' can be a single string or a list of strings
            selector = item["selector"]
            # Validate selector type and content
            if not isinstance(selector, (str, list)) or (isinstance(selector, list) and not all(isinstance(s, str) and s.strip() for s in selector)):
                 logger.warning(f"Invalid item configuration at index {i} ('selector'): Must be a string or a list of non-empty strings. Skipping item.")
                 continue
            # Convert a single selector string to a list for consistent processing later in PriceFetcher
            if isinstance(selector, str):
                item["selector"] = [selector]
            # Filter out any empty strings from the selector list after stripping
            item["selector"] = [s.strip() for s in item["selector"] if s and s.strip()]
            # Check if the selector list is empty after processing
            if not item["selector"]:
                 logger.warning(f"Invalid item configuration at index {i} ('selector'): Resulting selector list is empty after processing. Skipping item.")
                 continue


            # 'target_price' must be an int or float
            target_price = item["target_price"]
            if not isinstance(target_price, (int, float)):
                logger.warning(f"Invalid item configuration at index {i} ('target_price'): Must be a number (int or float). Skipping item.")
                continue
            # Convert target_price to float to ensure consistent type throughout the application
            item["target_price"] = float(target_price)

            # If all validations pass for the item, add it to the list of validated items
            validated_items.append(item)

        # After checking all items, ensure at least one valid item was found
        if not validated_items:
             logger.error("No valid items found in the configuration.")
             return None

        # --- Optional Configuration Keys Validation ---

        # Validate the 'global_notification_channels' key (optional)
        global_channels = config_data.get("global_notification_channels")
        if global_channels is not None: # Allow this key to be missing
             # If the key is present, ensure it's a list
             if not isinstance(global_channels, list):
                 logger.warning("Configuration key 'global_notification_channels' is not a list. Ignoring and defaulting to empty list.")
                 # Default to an empty list if the provided value is not a list
                 config_data["global_notification_channels"] = []
             else:
                 # Filter out any non-string or empty string values from the list
                 valid_channels = [channel for channel in global_channels if isinstance(channel, str) and channel.strip()]
                 if len(valid_channels) != len(global_channels):
                      logger.warning(f"Invalid values found in 'global_notification_channels'. Keeping only valid non-empty strings.")
                 # Update the list in config_data with only the validated string channels
                 config_data["global_notification_channels"] = [channel.strip() for channel in valid_channels]
        # If 'global_notification_channels' is not present, the .get() method will return None, which is handled.


        # Replace the original 'items' list in config_data with the list of validated items
        config_data["items"] = validated_items

        # Return the fully loaded and validated configuration dictionary
        return config_data

    except json.JSONDecodeError:
        # Handle errors if the file content is not valid JSON
        logger.error(f"Failed to parse configuration file '{config_path}': Invalid JSON format.")
        return None
    except Exception as e:
        # Catch any other unexpected errors during file reading or initial parsing process
        logger.error(f"An unexpected error occurred while reading config file '{config_path}': {e}")
        return None