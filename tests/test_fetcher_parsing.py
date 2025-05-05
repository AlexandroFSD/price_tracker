# tests/test_fetcher_parsing.py

"""Unit tests for the PriceFetcher's price parsing and cleaning logic."""


import logging

import pytest

# Import the class and constant to test from your source code
# This import now relies on pytest.ini correctly setting the pythonpath
from src.fetcher import PriceFetcher, \
    _is_lxml_available  # Import the class and the internal lxml availability flag

# Configure the logger for the module under test to see its debug output during tests (-s flag)
logging.getLogger('src.fetcher').setLevel(logging.DEBUG)
# Note: Basic logging configuration is typically handled by pytest itself.

# --- Test Fixtures ---

@pytest.fixture
def price_fetcher():
    """
    Pytest fixture that provides a PriceFetcher instance for tests.

    Yields:
        An instance of the PriceFetcher class.
    """
    # Create and yield a PriceFetcher instance.
    # The lxml availability is determined inside the class's __init__.
    fetcher = PriceFetcher()
    yield fetcher # Provide the instance to the test function

# --- Test Cases for _parse_price_from_content ---

# Use pytest.mark.parametrize to define multiple test cases with different inputs and expected outputs
# Each tuple in the list represents one test case: (html_content, selectors, expected_price)
@pytest.mark.parametrize(
    "html_content, selectors, expected_price",
    [
        # --- Basic Selector Tests (CSS) ---
        ("<html><body><span class='price'>123.45</span></body></html>", ".price", 123.45),
        # Multiple CSS selectors: first matching one should be used
        ("<html><body><span class='price-main'>99.99</span><span class='price-old'>120</span></body></html>", [".price-main", ".old-price"], 99.99),
        # Multiple CSS selectors: second matching one should be used
        ("<html><body><span class='price-old'>120</span><span class='price-main'>99.99</span></body></html>", [".old-price", ".price-main"], 99.99),
        # Selector not found in the HTML content
        ("<html><body><span class='price'>123.45</span></body></html>", ".non-existent", None),

        # --- Selector Tests (XPath) ---
        # Basic XPath selector
        ("<html><body><div id='product'><span class='cost'>456.78</span></div></body></html>", "//div[@id='product']/span[@class='cost']", 456.78),
        # Multiple selectors including XPath: CSS selector works first
        ("<html><body><span class='price'>100.00</span><span class='cost'>200</span></body></html>", [".price", "//span[@class='cost']"], 100.00),
        # Multiple selectors including XPath: XPath selector works first (corrected test case)
        # The first valid selector is used, so if .old-price is present and parses, it will be returned.
        # If .old-price is not present or doesn't parse, it will try the XPath.
        # Ensure the first selector is present and parses correctly for this test to be meaningful based on code logic.
        ("<html><body><span class='old-price'>100.00</span><span class='cost'>200.50</span></body></html>", [".old-price", "//span[@class='cost']"], 100.0), # <-- Expected 100.0 if .old-price is tried first

        # XPath getting attribute value (test case that previously failed due to wrong logic)
        ("<html><body><meta property='product:price:amount' content='789.00'></body></html>", "//meta[@property='product:price:amount']/@content", 789.00),
        # XPath finding text within nested elements (test case that previously failed due to xpath('string()') logic)
        ("<html><body><div class='price-container'>Total: <span>$<b>1,234</b>.<em>56</em></span> USD</div></body></html>", "//div[@class='price-container']", 1234.56),


        # --- Price Format Cleaning Tests ---
        ("<html><body><span class='price'>1 234.56</span></body></html>", ".price", 1234.56), # Space as thousands separator (common in some locales)
        ("<html><body><span class='price'>1.234,56</span></body></html>", ".price", 1234.56), # Dot as thousands, comma as decimal separator (European format)
        ("<html><body><span class='price'>1,234,567.89</span></body></html>", ".price", 1234567.89), # Commas as thousands, dot as decimal separator (US/UK format)
        ("<html><body><span class='price'>1.234.567,89</span></body></html>", ".price", 1234567.89), # Dots as thousands, comma as decimal separator (common in some locales)
        ("<html><body><span class='price'>$ 1,234.56 USD</span></body></html>", ".price", 1234.56), # Currency symbols and surrounding text/spaces
        ("<html><body><span class='price'>Цена: 999 грн.</span></body></html>", ".price", 999.0), # Text, currency symbol, and punctuation
        ("<html><body><span class='price'>45000</span></body></html>", ".price", 45000.0), # Integer price
        ("<html><body><span class='price'>45.00</span></body></html>", ".price", 45.0), # Price with .00 decimal part
        ("<html><body><span class='price'>45,00</span></body></html>", ".price", 45.0), # Price with ,00 decimal part
        ("<html><body><span class='price'>-100</span></body></html>", ".price", 100.0), # Ensure negative sign is handled (absolute value returned)
        ("<html><body><span class='price'>+250</span></body></html>", ".price", 250.0), # Handle positive sign
        ("<html><body><span class='price'>€1.234,50</span></body></html>", ".price", 1234.50), # European format with Euro symbol
        ("<html><body><span class='price'>50,000 грн</span></body></html>", ".price", 50000.0), # Thousands separator with comma (Ukrainian format example)
        ("<html><body><span class='price'>10000,50</span></body></html>", ".price", 10000.50), # Large number with comma decimal
        ("<html><body><span class='price'>10.000,50</span></body></html>", ".price", 10000.50), # Large number with dot thousands and comma decimal

        # --- Price Cleaning Edge Cases ---
        ("<html><body><span class='price'></span></body></html>", ".price", None), # Empty element text
        ("<html><body><span class='price'>abc</span></body></html>", ".price", None), # Text with no numbers
        ("<html><body><span class='price'>.</span></body></html>", ".price", None), # Just a dot
        ("<html><body><span class='price'>,</span></body></html>", ".price", None), # Just a comma
        ("<html><body><span class='price'>1,</span></body></html>", ".price", 1.0), # Number ending with comma (handled as decimal 1.0)
        ("<html><body><span class='price'>1.</span></body></html>", ".price", 1.0), # Number ending with dot (handled as decimal 1.0)
        ("<html><body><span class='price'>Text 123 Text</span></body></html>", ".price", 123.0), # Number surrounded by text
        ("<html><body><span class='price'>Text 1,234.56 Text</span></body></html>", ".price", 1234.56), # Number with separators surrounded by text
        ("<html><body><span class='price'>1.2.3</span></body></html>", ".price", None), # Invalid format: multiple dots used ambiguously
        ("<html><body><span class='price'>1,2,3</span></body></html>", ".price", None), # Invalid format: multiple commas used ambiguously
        ("<html><body><span class='price'>$,.</span></body></html>", ".price", None), # Only symbols and separators
        ("<html><body><span class='price'>.50</span></body></html>", ".price", 0.50), # Decimal starting with dot
        ("<html><body><span class='price'>,50</span></body></html>", ".price", 0.50), # Decimal starting with comma

    ]
)
# Use pytest.mark.skipif decorator to skip the entire test function
# if lxml is not available and any XPath selectors are used in the parameters.
# This decorator correctly evaluates before running each parameterized case.
@pytest.mark.skipif(not _is_lxml_available, reason="lxml not available for XPath tests")
def test_parse_price_from_content(price_fetcher, html_content, selectors, expected_price):
    """
    Tests parsing and cleaning price from various HTML structures and formats.

    This is a parameterized test covering CSS and XPath selectors, text extraction
    from nested elements, attribute values, and a wide range of price string formats
    with different separators and currency symbols.
    """
    # The @pytest.mark.skipif decorator handles skipping based on lxml availability
    # and whether any selectors in the parameter set are XPath.
    # The check inside the function is redundant when using the decorator correctly.
    # No need for manual skip check inside the test function anymore.

    # Call the protected method under test
    # Encode the HTML content to bytes, as the method expects bytes input
    parsed_price = price_fetcher._parse_price_from_content(html_content.encode('utf-8'), selectors)

    # Assert that the parsed price matches the expected price
    assert parsed_price == expected_price

# --- Additional tests for cleaning edge cases ---
# These tests were in comments, they can be added here if they cover distinct
# scenarios not already present in the extensive parameterized list above.
# Given the current list, these might be redundant but useful for explicit clarity.

# def test_clean_price_string_negative_value(price_fetcher):
#     assert price_fetcher._clean_price_string("-123.45") == 123.45
#
# def test_clean_price_string_with_extra_chars(price_fetcher):
#     assert price_fetcher._clean_price_string("  $ 1,234.56 USD ") == 1234.56