<img src="logo.png" width="195" height="55">

---

# ✨ Product Price Tracker ✨

A simple yet powerful Python application designed to track product prices from various websites. It leverages asynchronous web fetching, flexible parsing with selectors, saves price history, and notifies you when items reach your target price via channels like Telegram and Email.

## 🌟 Features

* **📈 Asynchronous Web Fetching:** Efficiently fetches data from multiple URLs concurrently using `aiohttp`.
* **🎯 Flexible Parsing:** Extracts price data using both CSS and XPath selectors via `lxml` and `cssselect`.
* **🧹 Robust Price Cleaning:** Parses price strings from various international formats (e.g., `1.234,56`, `50 000 грн`, `$1,234.56`) and handles currency symbols and extra text.
* **💾 Price History:** Stores price data in a local SQLite database (`price_history.db`).
* **🔔 Notifications:** Sends alerts when a tracked item's price meets or falls below the target price.
* **📱📧 Multiple Notification Channels:** Supports sending alerts via Telegram and Email (extensible to other channels).
* **⚙️ Configuration:** Easily configure items to track, selectors, target prices, and notification channels using a JSON/YAML file and environment variables (`.env`).
* **🧪 Unit Tests:** Comprehensive test suite using `pytest` covering core functionalities like price parsing.

## 📋 Table of Contents

* [🌟 Features](#-features)
* [📋 Table of Contents](#-table-of-contents)
* [🚀 Getting Started](#-getting-started)
    * [Prerequisites](#prerequisites)
    * [Cloning the Repository](#cloning-the-repository)
    * [Setting up the Virtual Environment](#setting-up-the-virtual-environment)
    * [Installing Dependencies](#installing-dependencies)
* [🛠️ Configuration](#-configuration)
    * [Public Configuration (`items_config.json`)](#public-configuration-items_configjson)
    * [Sensitive Configuration (`.env`)](#sensitive-configuration-env)
* [▶️ Usage](#-usage)
* [✅ Running Tests](#-running-tests)
* [📁 Project Structure](#-project-structure)
* [📄 License](#-license)
* [🤝 Contributing](#-contributing)
* [📬 Contact](#-contact)
* [🙌 Acknowledgements](#-acknowledgements)

## 🚀 Getting Started

Follow these instructions to get a copy of the project up and running on your local machine.

### Prerequisites

* Python 3.8 or higher installed.
* Git installed.

### Cloning the Repository

```bash
git clone https://github.com/AlexandroFSD/price_tracker
cd price-tracker
```

### Setting up the Virtual Environment

It's highly recommended to use a virtual environment to manage project dependencies.

```bash

# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# On Windows:
.\.venv\Scripts\activate
# On macOS/Linux:
source .venv/bin/activate
```

### Installing Dependencies

Install the required libraries. It's recommended to use the dependencies specified in `pyproject.toml`.
```Bash
# Install runtime and development dependencies using pip and pyproject.toml
pip install .[dev]
```

Alternatively, if you prefer using `requirements.txt`:
```Bash
# Ensure you have a requirements.txt file
pip install -r requirements.txt
```
Running with `pyproject.toml` dependencies
If you installed dependencies using `pip install .[dev]`, the `requirements.txt` file is not strictly needed for running or installing. You can include it for clarity or compatibility with other tools, but the primary source of truth for dependencies becomes `pyproject.toml`.

## 🛠️ Configuration
The application requires configuration to know which items to track and how to send notifications. Configuration is split into public settings (`items_config.json`) and sensitive secrets (`.env`).

### Public Configuration (`items_config.json`)

Create a file named items_config.json (or items_config.yaml if using YAML) in the root directory of the project. This file contains the list of items to track, their details, and global notification channel preferences.

Example `items_config.json`:
```JSON
{
  "global_notification_channels": ["telegram", "email"],
  "items": [
    {
      "name": "Example Product 1",
      "url": "[https://example.com/product/1](https://example.com/product/1)",
      "selector": ".product-price span.value",
      "target_price": 100.0
    },
    {
      "name": "Example Product 2",
      "url": "[https://another-site.com/item/2](https://another-site.com/item/2)",
      "selector": ["#price", "//span[@class='cost']"],
      "target_price": 500.0
    }
  ],
  "check_interval_hours": 24, # Optional: how often checks should ideally run (for future scheduling)
  "database_path": "price_history.db" # Optional: specify database path if different from default
}
```
`global_notification_channels`: A list of channel names (strings) where alerts should be sent globally. Only channels with a corresponding configured notifier and name matching this list will send alerts.
`items`: A list of dictionaries, each representing an item to track.
    `name`: A descriptive name for the item.
    `url`: The URL of the product page.
    `selector`: A CSS selector string or a list of CSS/XPath selector strings. The tracker will try these selectors in order until a price is found.
    `target_price`: The price (number) that triggers an alert if the current price is less than or equal to it.

`check_interval_hours`: (Optional) An integer specifying the desired interval between checks. Useful for future scheduling features.
`database_path`: (Optional) A string specifying the path to the SQLite database file. Defaults to `price_history.db` in the project root.

### Sensitive Configuration (`.env`)
Create a file named `.env` in the root directory of the project. This file stores your sensitive information like API keys and chat IDs. This file is ignored by Git (`.gitignore`) and must NOT be committed to the repository.

Use the provided `.env.example` file as a template. Copy it to `.env` and fill in your actual secrets.
Example `.env`:
```
# Example environment variables file (.env)
# This file should NOT be committed to Git.

# --- Telegram Notification Settings ---
# Your Telegram Bot Token obtained from BotFather
TELEGRAM_BOT_TOKEN=1234567890:ABCDEFGHIJKLMNOPQRSTUVWXYZ-abcdefghij

# Your Telegram Chat ID where the bot should send messages.
# Can be a user ID, group chat ID, or channel ID. Make sure the bot has permissions.
TELEGRAM_CHAT_ID=-1001234567890 # Example for a channel/group (starts with -100) or user id (like 123456789)

# --- Email Notification Settings ---
# Uncomment and fill in if you want to use email notifications.
# EMAIL_HOST=your.smtp.host.com
# EMAIL_PORT=587
# EMAIL_USER=your_email@example.com
# EMAIL_PASSWORD=your_email_password # Use App Password for Gmail with 2FA if needed
# EMAIL_RECIPIENT=recipient_email@example.com
```
Make sure to get your actual `TELEGRAM_BOT_TOKEN` from `BotFather` on Telegram.
Find your `TELEGRAM_CHAT_ID`. For a user, it's their `user ID`. For a group/channel, you might need a bot (like `@userinfobot`) to tell you the ID after you add the bot to the chat. Remember that group/channel IDs are usually negative.
If using Gmail with 2-Factor Authentication, you'll need to generate an App Password instead of using your regular password.

## ▶️ Usage

To run the price tracker check:

   * Activate your virtual environment.

   * Ensure your `items_config.json` and `.env` files are correctly set up.

   * Run the main script as a module:
```Bash
python -m src.main
```
The script will fetch prices, save data, check targets, and send notifications based on your configuration.

## ✅ Running Tests

To run the unit tests and verify the core logic:

   * Activate your virtual environment.

   * Run pytest from the project root:
```Bash
pytest -v -s
```
`-v` provides verbose output (shows each test name).
`-s` shows print statements and logger output (useful for debugging parsing).
Tests using XPath will be skipped if `lxml` library is not installed. 

## 📁 Project Structure

```
price_tracker/
├── .gitignore               # Specifies intentionally untracked files (.env, logs, db, venv etc.)
├── .env                     # Sensitive environment variables (IGNORED by Git)
├── .env.example             # Template for sensitive environment variables (TRACKED by Git)
├── items_config.json        # Public configuration file (items, selectors, targets, channels)
├── pyproject.toml           # Project build configuration and dependencies (incl. pytest config)
├── requirements.txt         # Project dependencies list (optional if using pyproject.toml)
├── price_history.db         # SQLite database (IGNORED by Git)
├── src/                     # Source code directory (Python package)
    ├── __init__.py          # Makes src a Python package
    ├── config.py            # Configuration loading and validation
    ├── database.py          # SQLite database interaction
    ├── fetcher.py           # Web fetching and price parsing
    ├── main.py              # Main application entry point
    ├── notifiers.py         # Notification channel implementations
    └── tracker.py           # Core tracking logic
└── tests/                   # Unit tests directory (Python package)
    ├── __init__.py          # Makes tests a Python package
    ├── test_config.py       # Tests for configuration loading
    └── test_fetcher_parsing.py # Tests for price fetching and parsing
```

## 📄 License

This project is licensed under the [![License](https://img.shields.io/badge/License-MIT-informational?style=plastic&logo=law&color=088484)](https://choosealicense.com/licenses/mit/). See the [LICENSE](LICENSE) file for details. 

## 🤝 Contributing
Pull requests are welcome. For major changes, please open an issue first to discuss what you would like to change.

If you like my job and you want to support me, you can do it by buying me coffee on 
[![By Me a coffe](https://img.shields.io/badge/By%20me%20a%20coffe-informational?style=plastic&logo=buymeacoffee&color=088484)](https://buymeacoffee.com/webproalex)

## 📬 Contact

If you have any questions or suggestions, feel free to open an issue on this repository or contact [AlexandroFSD](https://github.com/AlexandroFSD) at [oleksandr.nechyporenko81@gmail.com](mailto:oleksandr.nechyporenko81@gmail.com).

---

## 🙌 Acknowledgements

Icons by [Icons8](https://icons8.com)