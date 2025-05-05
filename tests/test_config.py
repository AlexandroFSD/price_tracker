# tests/test_config.py

"""Unit tests for the configuration loading and validation module (src.config)."""

import pytest
import json
import os


# Import the function and constants to test from your source code
# This import now relies on pytest.ini correctly setting the pythonpath
from src.config import load_config, CONFIG_FILE

# --- Test Fixtures ---

@pytest.fixture
def temp_config_file(tmp_path):
    """
    Pytest fixture to create a temporary path for the configuration file.

    Args:
        tmp_path: Built-in pytest fixture providing a temporary directory path.

    Returns:
        A pathlib.Path object representing the path to the temporary config file.
    """
    # tmp_path is a built-in pytest fixture providing a temporary directory
    # Create a path object for the config file within the temporary directory
    return tmp_path / CONFIG_FILE

# --- Test Cases for load_config ---

def test_load_config_success(temp_config_file):
    """
    Tests successfully loading a valid configuration file.

    Verifies that load_config returns a dictionary with expected keys
    and properly validates and converts item data types.
    """
    valid_config_content = {
        "global_notification_channels": ["email", "telegram"],
        "items": [
            {
                "name": "Test Item 1",
                "url": "http://example.com/item1",
                "selector": ".price", # Single string selector
                "target_price": 100.0
            },
            {
                "name": "Test Item 2",
                "url": "http://example.com/item2",
                "selector": ["#price", "//span[@class='cost']"], # List of string selectors
                "target_price": 250 # Integer target price
            }
        ],
        "check_interval_hours": 12 # Example of another optional key
    }
    # Write the valid config content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(valid_config_content, f)

    # Load the configuration using the function under test
    config = load_config(str(temp_config_file)) # Pass the string path

    # Assert that the config was loaded correctly and is a dictionary
    assert config is not None
    assert isinstance(config, dict)

    # Assert global notification channels are loaded correctly
    assert "global_notification_channels" in config
    assert isinstance(config["global_notification_channels"], list)
    assert config["global_notification_channels"] == ["email", "telegram"]

    # Assert items list is loaded and validated correctly
    assert "items" in config
    assert isinstance(config["items"], list)
    assert len(config["items"]) == 2

    # Assert details of the first item
    assert config["items"][0]["name"] == "Test Item 1"
    assert config["items"][0]["url"] == "http://example.com/item1"
    assert config["items"][0]["selector"] == [".price"] # Single selector should be converted to list
    assert config["items"][0]["target_price"] == 100.0 # Should be float

    # Assert details of the second item
    assert config["items"][1]["name"] == "Test Item 2"
    assert config["items"][1]["url"] == "http://example.com/item2"
    assert config["items"][1]["selector"] == ["#price", "//span[@class='cost']"] # List should be kept
    assert config["items"][1]["target_price"] == 250.0 # Integer should be converted to float

    # Assert other optional keys are present
    assert "check_interval_hours" in config
    assert config["check_interval_hours"] == 12


def test_load_config_file_not_found():
    """
    Tests loading a configuration file that does not exist.

    Verifies that load_config returns None and potentially logs an error.
    """
    # Use a path that definitely does not exist relative to the current working directory
    non_existent_path = "non_existent_directory/non_existent_config_file.json"
    # Use os.path.join to create a path that won't clash with system paths
    non_existent_absolute_path = os.path.abspath(non_existent_path)

    # Load the config using the function
    config = load_config(non_existent_path)

    # Assert that loading failed and returned None
    assert config is None

    # Optional: Check if an error message was logged (requires mocking logging)
    # from src.config import logger as config_logger # Import the logger from src.config module
    # with patch.object(config_logger, 'error') as mock_log_error:
    #     load_config(non_existent_path)
    #     # Verify that the error logging function was called with the expected message
    #     mock_log_error.assert_called_with(
    #         f"Configuration file '{non_existent_path}' not found at {non_existent_absolute_path}"
    #     )


def test_load_config_invalid_json(temp_config_file):
    """
    Tests loading a config file with invalid JSON syntax.

    Verifies that load_config returns None.
    """
    # Content with invalid JSON syntax
    invalid_json_content = "{ \"name\": \"test\", items: [ }" # Missing closing brace, items value is incomplete

    # Write the invalid content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        f.write(invalid_json_content)

    # Attempt to load the invalid config
    config = load_config(str(temp_config_file))

    # Assert that loading failed
    assert config is None


def test_load_config_invalid_structure(temp_config_file):
    """
    Tests loading a config file where the root is not a dictionary.

    Verifies that load_config returns None.
    """
    # Content where the root is a list instead of a dictionary
    invalid_structure_content = [ {"item": 1} ]

    # Write the invalid content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(invalid_structure_content, f)

    # Attempt to load the invalid config
    config = load_config(str(temp_config_file))

    # Assert that loading failed
    assert config is None

def test_load_config_missing_items_key(temp_config_file):
    """
    Tests loading a config file missing the mandatory 'items' key.

    Verifies that load_config returns None.
    """
    # Config content missing the 'items' key
    missing_items_content = {
        "global_notification_channels": ["email"]
        # 'items' key is intentionally omitted
    }
    # Write the content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(missing_items_content, f)

    # Attempt to load the config
    config = load_config(str(temp_config_file))

    # Assert that loading failed because 'items' is required
    assert config is None


def test_load_config_items_not_list(temp_config_file):
    """
    Tests loading a config file where the 'items' key's value is not a list.

    Verifies that load_config returns None.
    """
    # Config content where 'items' is a string instead of a list
    items_not_list_content = {
        "global_notification_channels": ["email"],
        "items": "this is not a list"
    }
    # Write the content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(items_not_list_content, f)

    # Attempt to load the config
    config = load_config(str(temp_config_file))

    # Assert that loading failed
    assert config is None


def test_load_config_invalid_item_missing_keys(temp_config_file):
    """
    Tests config with an invalid item (missing required keys).

    Verifies that the invalid item is skipped and a config with only
    valid items (and other valid top-level keys) is returned.
    """
    config_with_invalid_item = {
        "global_notification_channels": ["email"],
        "items": [
            {
                "name": "Valid Item",
                "url": "http://example.com",
                "selector": ".price",
                "target_price": 100.0
            },
            {
                "name": "Invalid Item",
                "url": "http://bad.com"
                # selector and target_price are missing - should be skipped
            }
        ],
        "other_setting": "value" # Include another setting to ensure it's kept
    }
    # Write the content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_with_invalid_item, f)

    # Attempt to load the config
    config = load_config(str(temp_config_file))

    # Assert that config loading did NOT return None, but the items list is filtered
    assert config is not None
    assert isinstance(config, dict)
    assert "items" in config
    assert isinstance(config["items"], list)
    assert len(config["items"]) == 1 # Only the valid item should be loaded

    # Assert details of the single valid item
    assert config["items"][0]["name"] == "Valid Item"
    assert config["items"][0]["url"] == "http://example.com"
    assert config["items"][0]["selector"] == [".price"]
    assert config["items"][0]["target_price"] == 100.0

    # Verify that other valid top-level keys are preserved
    assert "global_notification_channels" in config
    assert config["global_notification_channels"] == ["email"]
    assert "other_setting" in config
    assert config["other_setting"] == "value"


def test_load_config_invalid_item_wrong_type(temp_config_file):
    """
    Tests config with an invalid item (wrong type for a required key like target_price).

    Verifies that the invalid item is skipped.
    """
    config_with_invalid_item = {
        "global_notification_channels": ["email"],
        "items": [
            {
                "name": "Valid Item",
                "url": "http://example.com",
                "selector": ".price",
                "target_price": 100.0
            },
            {
                "name": "Invalid Item Type",
                "url": "http://bad.com",
                "selector": ".cost",
                "target_price": "not a number" # Wrong type for target_price - should be skipped
            }
        ]
    }
    # Write the content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_with_invalid_item, f)

    # Attempt to load the config
    config = load_config(str(temp_config_file))

    # Assert that config loading did NOT return None, but the items list is filtered
    assert config is not None
    assert isinstance(config["items"], list)
    assert len(config["items"]) == 1 # Only the valid item should be loaded
    assert config["items"][0]["name"] == "Valid Item"


def test_load_config_invalid_global_channels_type(temp_config_file):
    """
    Tests config where 'global_notification_channels' has an invalid type (not a list).

    Verifies that the key is ignored or defaulted to an empty list,
    while valid items are still loaded.
    """
    config_with_invalid_channels = {
        "global_notification_channels": "this is not a list", # Wrong type - should be ignored/defaulted
        "items": [
            {
                "name": "Valid Item",
                "url": "http://example.com",
                "selector": ".price",
                "target_price": 100.0
            }
        ]
    }
    # Write the content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_with_invalid_channels, f)

    # Attempt to load the config
    config = load_config(str(temp_config_file))

    # Assert that config is loaded (not None) and items are valid
    assert config is not None
    assert len(config["items"]) == 1

    # Assert that 'global_notification_channels' is handled correctly (empty list or missing)
    # The load_config function returns the modified dict, so it should be an empty list
    assert isinstance(config.get("global_notification_channels"), list)
    assert config.get("global_notification_channels", []) == [] # Should be an empty list


def test_load_config_valid_global_channels_content(temp_config_file):
    """
    Tests config with a list for 'global_notification_channels' but with invalid content types.

    Verifies that only valid string channel names are kept.
    """
    config_with_invalid_channels_content = {
        "global_notification_channels": ["email", 123, "telegram", None, "   slack   ", ""], # Invalid content types
        "items": [
            {
                "name": "Valid Item",
                "url": "http://example.com",
                "selector": ".price",
                "target_price": 100.0
            }
        ]
    }
    # Write the content to the temporary file
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_with_invalid_channels_content, f)

    # Attempt to load the config
    config = load_config(str(temp_config_file))

    # Assert that config is loaded and items are valid
    assert config is not None
    assert len(config["items"]) == 1

    # Assert that only valid non-empty strings are kept in global_notification_channels
    assert isinstance(config.get("global_notification_channels"), list)
    # Check content and length after filtering (ignoring order for comparison)
    assert sorted(config["global_notification_channels"]) == sorted(["email", "telegram", "slack"])
    assert len(config["global_notification_channels"]) == 3

# Add test for empty items list after filtering
def test_load_config_no_valid_items_after_filtering(temp_config_file):
    """
    Tests config with items list containing only invalid items.

    Verifies that load_config returns None because no valid items remain.
    """
    config_with_only_invalid_items = {
        "global_notification_channels": ["email"],
        "items": [
            {
                "name": "Invalid Item 1",
                "url": "http://bad.com"
                # Missing keys
            },
            {
                "name": "Invalid Item 2",
                "url": "http://other.com",
                "selector": ".cost",
                "target_price": "not a number" # Wrong type
            }
        ]
    }
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_with_only_invalid_items, f)

    config = load_config(str(temp_config_file))

    # Should return None because no valid items were successfully loaded
    assert config is None

# Add test for selector validation edge cases
@pytest.mark.parametrize("invalid_selector_input", [
    123,         # Not a string or list
    ["", "   "], # List with only empty strings
    [123, "valid"], # List with non-string item
    [],          # Empty list (should be skipped by config validation, but test robustness) - NOTE: config validation filters empty lists
    ["valid", ""], # List with one valid and one empty string
])
def test_load_config_invalid_selector_formats(temp_config_file, invalid_selector_input):
    """
    Tests config with invalid formats or content for the 'selector' key.

    Verifies that items with invalid selectors are skipped.
    """
    config_with_invalid_selector = {
        "items": [
            {
                "name": "Valid Item",
                "url": "http://example.com",
                "selector": ".price",
                "target_price": 100.0
            },
            {
                "name": "Invalid Selector Item",
                "url": "http://bad.com",
                "selector": invalid_selector_input, # The invalid input from the parametrize fixture
                "target_price": 200.0
            }
        ]
    }
    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_with_invalid_selector, f)

    config = load_config(str(temp_config_file))

    # Assert that config is loaded (not None) and items list is filtered
    assert config is not None
    assert isinstance(config["items"], list)
    assert len(config["items"]) == 1 # Only the valid item should be loaded
    assert config["items"][0]["name"] == "Valid Item"


# Add test for name/url validation edge cases (empty strings after strip)
@pytest.mark.parametrize("invalid_field, invalid_value", [
    ("name", ""),
    ("name", "   "),
    ("url", ""),
    ("url", "   "),
])
def test_load_config_invalid_name_url(temp_config_file, invalid_field, invalid_value):
    """
    Tests config with invalid (empty after strip) name or url.

    Verifies that items with invalid name or url are skipped.
    """
    config_with_invalid_item = {
        "items": [
            {
                "name": "Valid Item",
                "url": "http://example.com",
                "selector": ".price",
                "target_price": 100.0
            },
            {
                "name": "Invalid Field Item",
                "url": "http://other.com",
                "selector": ".cost",
                "target_price": 200.0
            }
        ]
    }
    # Inject the invalid value into the specific field
    config_with_invalid_item["items"][1][invalid_field] = invalid_value

    with open(temp_config_file, 'w', encoding='utf-8') as f:
        json.dump(config_with_invalid_item, f)

    config = load_config(str(temp_config_file))

    # Assert that config is loaded (not None) and items list is filtered
    assert config is not None
    assert isinstance(config["items"], list)
    assert len(config["items"]) == 1 # Only the valid item should be loaded
    assert config["items"][0]["name"] == "Valid Item"