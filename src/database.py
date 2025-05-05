# src/database.py

"""Handles SQLite database initialization and price data saving."""

import logging
import os
import sqlite3
from datetime import datetime

# Define the default name for the SQLite database file
DATABASE_FILE = 'price_history.db'

# Configure logger for this module
logger = logging.getLogger(__name__)


def initialize_database(db_path: str = DATABASE_FILE):
    """
    Initializes the SQLite database and creates the price_history table if it doesn't exist.

    Ensures the directory for the database file exists. Creates a table
    `price_history` to store price records with a unique constraint
    on `timestamp`, `url`, and `price` to prevent duplicate entries
    for the exact same data point.

    Args:
        db_path: The path where the SQLite database file should be created.
                 Defaults to the value of DATABASE_FILE ('price_history.db').

    Raises:
        sqlite3.Error: If a database connection or execution error occurs
                       during initialization. This is considered a critical
                       error that should halt the application setup.
    """
    # Extract the directory path from the full database path
    db_dir = os.path.dirname(db_path)
    # If a directory path is specified and it doesn't exist, create it
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir)
        logger.info(f"Created directory for database: {db_dir}")

    conn = None  # Initialize connection to None
    try:
        # Connect to the SQLite database. Creates the file if it doesn't exist.
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # SQL statement to create the price_history table if it doesn't exist
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT, -- Unique ID for each record
                timestamp TEXT NOT NULL,            -- Timestamp of when the price was recorded (YYYY-MM-DD HH:MM:SS format)
                item_name TEXT NOT NULL,            -- Name of the tracked item
                url TEXT NOT NULL,                  -- URL of the tracked item
                price REAL NOT NULL,                -- The price of the item (stored as a real number)
                -- Ensure that the exact same timestamp, url, and price combination is only stored once.
                -- If a duplicate is attempted, ignore the insert.
                UNIQUE(timestamp, url, price) ON CONFLICT IGNORE
            )
        """)

        # Commit the changes to the database
        conn.commit()
        logger.info(f"SQLite database initialized at {os.path.abspath(db_path)}")

    except sqlite3.Error as e:
        # Log any SQLite errors during initialization as critical and re-raise
        logger.critical(f"Error initializing database at {db_path}: {e}")
        raise # Re-raise the exception to signal a fatal error

    finally:
        # Ensure the database connection is closed even if errors occur
        if conn:
            conn.close()


def save_price_data(item_name: str, url: str, price: float, db_path: str = DATABASE_FILE):
    """
    Saves a single price data record for an item to the SQLite database.

    If a record with the exact same timestamp, URL, and price already exists,
    the insert operation is ignored due to the table's unique constraint.

    Args:
        item_name: The name of the item.
        url: The URL of the item.
        price: The price of the item as a float.
        db_path: The path to the SQLite database file. Defaults to DATABASE_FILE.
    """
    conn = None # Initialize connection to None
    try:
        # Connect to the database
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # Get the current timestamp in the required format
        current_timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

        # SQL statement to insert price data. ON CONFLICT IGNORE handles duplicates.
        cursor.execute("""
            INSERT INTO price_history (timestamp, item_name, url, price)
            VALUES (?, ?, ?, ?)
        """, (current_timestamp, item_name, url, price)) # Use parameter substitution to prevent SQL injection

        # Commit the transaction
        conn.commit()
        # Logging for individual save is handled in the calling function (e.g., tracker)

    except sqlite3.IntegrityError:
         # This exception is expected if ON CONFLICT IGNORE is triggered.
         # We catch it and pass, as no action is needed - the duplicate was ignored.
         pass
    except sqlite3.Error as e:
        # Log other SQLite errors during saving
        logger.error(f"Error saving data for '{item_name}' to database: {e}")
    except Exception as e:
        # Catch any other unexpected errors during the saving process
        logger.error(f"An unexpected error occurred while saving data for '{item_name}' to database: {e}")
        # The current logic logs the error and continues without re-raising,
        # which is typically desired for saving individual items.
    finally:
        # Ensure the database connection is closed
        if conn:
            conn.close()