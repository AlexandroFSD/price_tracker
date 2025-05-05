# src/fetcher.py

"""Handles fetching web page content and parsing price data."""

import asyncio
import logging
import re
from typing import List, Dict, Any, Optional, Union

import aiohttp
from aiohttp import ClientSession

# import locale # Not used in the current parsing logic

logger = logging.getLogger(__name__)

# Check if lxml is available for XPath/CSS selectors
try:
    from lxml import html

    _is_lxml_available = True
    logger.info("lxml found. XPath and CSS selectors are enabled.")
except ImportError:
    _is_lxml_available = False
    logger.warning(
        "lxml not found. XPath and CSS selectors will not work. Please install lxml (`pip install lxml`) for full functionality.")


class PriceFetcher:
    """
    Fetches web page content and extracts price information based on selectors.

    Provides methods for asynchronous fetching and robust price parsing
    from various string formats.
    """

    def __init__(self):
        """Initializes the PriceFetcher."""
        self._is_lxml_available = _is_lxml_available

    async def _get_page_content_async(
            self,
            session: ClientSession,
            url: str,
            retries: int = 3,
            delay: int = 2
    ) -> Optional[bytes]:
        """
        Fetches page content from a URL asynchronously with retries.

        Args:
            session: An aiohttp ClientSession instance.
            url: The URL to fetch.
            retries: The maximum number of retries in case of failure.
            delay: The delay in seconds between retries.

        Returns:
            The page content as bytes if successful, None otherwise.
        """
        # Standard user agent to mimic a browser
        user_agent = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        headers = {'User-Agent': user_agent}

        # Loop for retries
        for attempt in range(retries):
            try:
                logger.info(f"Attempt {attempt + 1}/{retries}: Fetching {url}")
                # Use a shorter timeout for the connection phase, longer for total request
                async with session.get(url, headers=headers,
                                       allow_redirects=True,
                                       timeout=aiohttp.ClientTimeout(connect=5,
                                                                     total=15)) as response:
                    response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
                    logger.info(
                        f"Successfully fetched {url} (Status: {response.status})")
                    return await response.read()  # Read content as bytes

            except aiohttp.ClientError as e:
                # Log client errors (HTTP errors, connection issues)
                logger.warning(
                    f"Attempt {attempt + 1} failed to fetch {url}: {e}")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    return None
                else:
                    logger.error(
                        f"Failed to fetch {url} after {retries} attempts.")
                    return None
            except asyncio.TimeoutError:
                # Log timeout errors
                logger.warning(f"Attempt {attempt + 1} timed out for {url}.")
                if attempt < retries - 1:
                    logger.info(f"Retrying in {delay} seconds...")
                    await asyncio.sleep(delay)
                    return None
                else:
                    logger.error(
                        f"Failed to fetch {url} after {retries} attempts due to timeout.")
                    return None
        return None

    def _parse_price_from_content(
            self,
            html_content: bytes,
            selectors: Union[str, List[str]]
    ) -> Optional[float]:
        """
        Parses the price from HTML content using CSS or XPath selectors.

        Tries selectors in the provided order until a valid price is found.
        Handles both element text content and attribute values. Requires lxml
        for XPath and CSS selectors.

        Args:
            html_content: The HTML content as bytes.
            selectors: A single CSS/XPath selector string or a list of selector strings.

        Returns:
            The parsed price as a float, or None if no price is found or parsing fails
            after trying all selectors.
        """
        if not html_content:
            logger.debug("No HTML content to parse.")
            return None

        # Ensure selectors is a list for consistent processing
        selector_list = [selectors] if isinstance(selectors,
                                                  str) else selectors
        if not selector_list:
            logger.debug("No selectors provided for parsing.")
            return None

        # Filter out XPath selectors if lxml is not available
        if not self._is_lxml_available:
            xpath_selectors = [s for s in selector_list if
                               s.strip().startswith(
                                   '/') or s.strip().startswith('./')]
            if xpath_selectors:
                logger.warning(
                    f"lxml not installed. Skipping XPath selectors: {xpath_selectors}")
                selector_list = [s for s in selector_list if
                                 s not in xpath_selectors]
                # Return None if no selectors are left after filtering
                if not selector_list:
                    logger.debug(
                        "No CSS selectors remaining after filtering out XPath selectors.")
                    return None

        try:
            # Parse HTML content using lxml into an element tree
            tree = html.fromstring(html_content)
        except Exception as e:
            logger.error(f"Failed to parse HTML content using lxml: {e}")
            return None

        # Iterate through each selector provided
        for selector in selector_list:
            logger.debug(
                f"Attempting to find element with selector: {selector}")
            try:
                # Determine if the selector is an XPath or CSS selector
                is_xpath = selector.strip().startswith(
                    '/') or selector.strip().startswith('./')
                # results will hold elements (for CSS/element XPath) OR attribute values (for attribute XPath)
                results = []

                # Execute the selector query using the appropriate method
                if is_xpath:
                    # For XPath, use tree.xpath(). This returns a list of elements or values.
                    # If it's an attribute selector (@...), xpath will return a list of attribute values (strings)
                    # If it's an element selector, xpath will return a list of elements
                    results = tree.xpath(selector)
                    logger.debug(
                        f"XPath query '{selector}' returned {len(results)} results.")
                else:
                    # For CSS selectors, use tree.cssselect(). This returns a list of elements.
                    results = tree.cssselect(selector)
                    logger.debug(
                        f"CSS selector '{selector}' returned {len(results)} results.")

                # --- Process the results of the query ---
                raw_price_text: Optional[
                    str] = None  # Initialize the variable to hold extracted raw text/attribute value

                # 1. Check if the selector was specifically for an attribute (@...)
                # Correct check: if it's an XPath selector AND the last step of the XPath path starts with '@'
                if is_xpath and selector.strip().split('/')[-1].startswith(
                        '@'):
                    # If it's an attribute selector, results is a list of attribute values
                    logger.debug(
                        f"Selector is attribute selector. Looking for attribute value.")
                    if results:  # Check if the list of values is not empty
                        # Take the first attribute value found (usually there's only one)
                        # str() conversion handles different lxml return types for attribute values
                        raw_price_text = str(results[0]).strip()
                        logger.debug(
                            f"Extracted attribute value: '{raw_price_text}' for selector: {selector}")
                    else:
                        logger.debug(
                            f"Attribute value not found for selector: {selector}.")
                        # raw_price_text remains None if attribute value list is empty

                # 2. Selector was not for an attribute, handle element results (for CSS or non-attribute XPath)
                elif results:  # Check if elements were found by the selector
                    # Take the first element found from the results list
                    element = results[0]

                    # Try to extract text content from the element and its descendants
                    if self._is_lxml_available:
                        try:
                            # Attempt to extract all concatenated text from the element and its descendants using xpath('string()')
                            text_from_xpath_string = element.xpath(
                                'string()').strip()
                            if text_from_xpath_string:  # Use the result only if it's not an empty string
                                raw_price_text = text_from_xpath_string
                                logger.debug(
                                    f"Extracted text using xpath('string()'): '{raw_price_text}' for selector: {selector}")
                            # raw_price_text remains None if xpath('string()') returns empty or None

                        except Exception as e:
                            # Log any errors during xpath('string()') extraction
                            logger.debug(
                                f"Failed xpath('string()') extraction for selector '{selector}': {e}. Falling back to manual extraction.")
                            # raw_price_text remains None

                    # Fallback to manual text extraction if xpath('string()') didn't yield a result, or if lxml is not available
                    if raw_price_text is None or not raw_price_text:
                        logger.debug(
                            "xpath('string()') failed or returned empty, attempting manual text extraction from immediate children.")
                        # Manually collect text from the element itself and its immediate children/tails
                        raw_price_text_parts = []
                        if element.text:
                            raw_price_text_parts.append(element.text)
                        # Add text from immediate children only
                        for child in element:
                            if child.text:
                                raw_price_text_parts.append(child.text)
                            # Also consider text after the child element within the parent
                            if child.tail:
                                raw_price_text_parts.append(child.tail)

                        raw_price_text = "".join(
                            raw_price_text_parts).strip()  # Join all collected parts and strip whitespace
                        logger.debug(
                            f"Extracted text using manual method: '{raw_price_text}' for selector: {selector}")

                # If results is empty (selector found nothing), raw_price_text remains None, and we continue to the next selector

                # --- End of refined extraction logic ---

                # Log the raw text or attribute value extracted before cleaning
                logger.debug(
                    f"Value of raw_price_text before cleaning: '{raw_price_text}' for selector: {selector}")

                # If any text or attribute value was successfully extracted (raw_price_text is not None or empty)
                if raw_price_text:
                    # Pass the extracted raw string to the cleaning function to get a float price
                    cleaned_price = self._clean_price_string(raw_price_text)
                    if cleaned_price is not None:
                        # Log successful parsing and return the cleaned price
                        logger.debug(
                            f"Successfully parsed price '{cleaned_price}' from text '{raw_price_text.strip()}' using selector '{selector}'.")
                        return cleaned_price  # Return the first successfully cleaned price found by any selector

                # Log if the element was found but no parsable price could be extracted from its text/attribute
                logger.debug(
                    f"Element found using selector '{selector}', but no parsable price found in text/attribute '{raw_price_text}'.")
                # Continue the loop to try the next selector if the current one didn't yield a valid price

            except Exception as e:
                # Catch any exceptions during parsing with this specific selector and log a warning
                logger.warning(
                    f"Error parsing with selector '{selector}': {e}")
                # Continue to the next selector if an error occurs

        # If the loop finishes without finding and returning a valid price using any of the selectors
        logger.debug("No price found after trying all selectors.")
        return None

    def _clean_price_string(
            self,
            price_string: str
    ) -> Optional[float]:
        """
        Cleans a raw price string and converts it to a float.

        Removes non-numeric characters (except separators and signs) and handles
        various international number formats based on the presence and position
        of comma (,) and dot (.) separators. Returns the absolute value of the
        parsed price.

        Args:
            price_string: The raw string containing the price, extracted from HTML.

        Returns:
            The parsed price as a float (absolute value), or None if cleaning
            or conversion fails due to an unparsable format.
        """
        logger.debug(f"Cleaning price string: '{price_string}')")

        # Return None for empty or non-string inputs
        if not isinstance(price_string, str) or not price_string.strip():
            logger.debug("Price string is empty or not a string for cleaning.")
            return None

        # Handle and store the leading sign (+ or -)
        sign = 1
        cleaned_with_sign = price_string.strip()
        if cleaned_with_sign.startswith('-'):
            sign = -1
            cleaned_with_sign = cleaned_with_sign[1:].strip()
        elif cleaned_with_sign.startswith('+'):
            cleaned_with_sign = cleaned_with_sign[1:].strip()

        # Remove all characters that are NOT digits (0-9), dot (.), or comma (,)
        numeric_chars_only = re.sub(r'[^\d.,]', '', cleaned_with_sign)
        logger.debug(
            f"After initial cleaning and sign handling: '{numeric_chars_only}')")

        # Return None if no numeric characters remain after cleaning
        if not numeric_chars_only:
            logger.debug(
                f"No numeric characters found after cleaning or only sign was present.")
            return None

        # --- Logic for parsing based on separator analysis ---

        num_dots = numeric_chars_only.count('.')
        num_commas = numeric_chars_only.count(',')

        processed_num_str: Optional[
            str] = None  # Variable to hold the string formatted for float conversion

        # Case 1: Both dots and commas are present
        if num_dots > 0 and num_commas > 0:
            last_dot_pos = numeric_chars_only.rfind('.')
            last_comma_pos = numeric_chars_only.rfind(',')

            # Prioritize US/UK format if the dot is the last separator
            if last_dot_pos > last_comma_pos:
                # US/UK: comma is thousands separator, dot is decimal. Remove commas.
                # Validate that the part after the last dot looks like a decimal part (contains only digits)
                if re.fullmatch(r'\d*', numeric_chars_only[last_dot_pos + 1:]):
                    processed_num_str = numeric_chars_only.replace(',', '')
                    logger.debug(
                        f"Both, last is dot. Assuming US/UK decimal. Processed: '{processed_num_str}'")
                else:
                    # If the part after the dot is not just digits, it's an invalid format
                    logger.debug(
                        f"Both, last is dot, but decimal part invalid: '{numeric_chars_only}'.")
                    return None
            # Prioritize EU format if the comma is the last separator
            elif last_comma_pos > last_dot_pos:
                # EU: dot is thousands separator, comma is decimal. Remove dots, replace comma with dot.
                # Validate that the part after the last comma looks like a decimal part (contains only digits)
                if re.fullmatch(r'\d*',
                                numeric_chars_only[last_comma_pos + 1:]):
                    processed_num_str = numeric_chars_only.replace('.',
                                                                   '').replace(
                        ',', '.')
                    logger.debug(
                        f"Both, last is comma. Assuming EU decimal. Processed: '{processed_num_str}'")
                else:
                    # If the part after the comma is not just digits, it's an invalid format
                    logger.debug(
                        f"Both, last is comma, but decimal part invalid: '{numeric_chars_only}'.")
                    return None
            else:
                # Ambiguous case (e.g., separators interleaved incorrectly), return None
                logger.debug(
                    f"Both separators found, but positions ambiguous: '{numeric_chars_only}'.")
                return None


        # Case 2: Only commas are present
        elif num_commas > 0:
            # Prioritize Thousands integer format if it matches the pattern (e.g., 1,234, 50,000)
            # This regex requires at least one group of ,XXX and no decimal part
            if re.fullmatch(r'^\d{1,3}(?:,\d{3})+$', numeric_chars_only):
                processed_num_str = numeric_chars_only.replace(',', '')
                logger.debug(
                    f"Only commas, looks like thousands integer. Processed: '{processed_num_str}'")
            # Then check for Decimal comma format (e.g., 123,45, 1,)
            # If it has digits after the comma OR ends with a comma, AND it's not a thousands format
            # This covers cases like 123,45, 1,23 (EU decimal), or trailing comma like 1,
            # Check if the part after the last comma looks like a decimal (0-many digits)
            elif re.fullmatch(r'\d*', numeric_chars_only[
                                      numeric_chars_only.rfind(',') + 1:]):
                # If it has multiple commas AND doesn't match the thousands integer pattern,
                # check if it matches a thousands + optional decimal comma pattern like 1,234,50
                if num_commas > 1 and not re.fullmatch(
                        r'^\d{1,3}(?:,\d{3})+(?:,\d+)?$', numeric_chars_only):
                    logger.debug(
                        f"Only commas found, multiple and not clear pattern: '{numeric_chars_only}'.")
                    return None  # Invalid format (e.g., 1,2,3)
                else:  # It's a single comma decimal, trailing comma, or thousands + decimal comma
                    processed_num_str = numeric_chars_only.replace(',', '.')
                    logger.debug(
                        f"Only commas, looks like decimal or trailing. Processed: '{processed_num_str}'")
            else:
                # Other cases with only commas are invalid (e.g., comma not followed by digit/end)
                logger.debug(
                    f"Only commas found, but format is ambiguous or invalid: '{numeric_chars_only}'.")
                return None


        # Case 3: Only dots are present
        elif num_dots > 0:
            # Prioritize Thousands integer format if it matches the pattern (e.g., 1.234)
            # This regex requires at least one group of .XXX and no decimal part
            if re.fullmatch(r'^\d{1,3}(?:.\d{3})+$', numeric_chars_only):
                processed_num_str = numeric_chars_only.replace('.', '')
                logger.debug(
                    f"Only dots, looks like thousands integer. Processed: '{processed_num_str}'")
            # Then check for Decimal dot format (e.g., 123.45, 1.)
            # If it has digits after the dot OR ends with a dot, AND it's not a thousands format
            # This covers cases like 123.45 (US decimal), or trailing dot like 1.
            # Check if the part after the last dot looks like a decimal (0-many digits)
            elif re.fullmatch(r'\d*', numeric_chars_only[
                                      numeric_chars_only.rfind('.') + 1:]):
                # If it has multiple dots AND doesn't match the thousands integer pattern,
                # check if it matches thousands + decimal dot pattern like 1.234.50
                if num_dots > 1 and not re.fullmatch(
                        r'^\d{1,3}(?:.\d{3})+(?:.\d+)?$', numeric_chars_only):
                    logger.debug(
                        f"Only dots found, multiple and not clear pattern: '{numeric_chars_only}'.")
                    return None  # Invalid format (e.g., 1.2.3)
                else:  # It's a single dot decimal, trailing dot, or thousands + decimal dot
                    processed_num_str = numeric_chars_only
                    logger.debug(
                        f"Only dots, looks like decimal or trailing. Processed: '{processed_num_str}'")

            else:
                # Other cases with only dots are invalid (e.g., dot not followed by digit/end)
                logger.debug(
                    f"Only dots found, but format is ambiguous or invalid: '{numeric_chars_only}'.")
                return None

        # Case 4: Neither dots nor commas (integer)
        else:
            processed_num_str = numeric_chars_only
            logger.debug(
                f"No separators found. Assuming integer. Processed: '{processed_num_str}'")

        # --- Final Validation and Conversion ---
        # Return None if the processed string is null, empty, or just a dot
        if processed_num_str is None or not processed_num_str or processed_num_str == '.':
            logger.debug(
                f"Processed string is null, empty or just dot: '{processed_num_str}'.")
            return None

        # Check for multiple decimal points after processing (should only be one or zero)
        # This check is a safeguard if the logic above somehow produced multiple dots.
        if processed_num_str.count('.') > 1:
            logger.debug(
                f"Validation failed after processing: Multiple decimal points in '{processed_num_str}'.")
            return None

        # Check for leading/trailing dot after processing (e.g., '.5' is okay, but '5.' or '.' needs careful handling)
        # The logic above should handle trailing dots, but let's double check.
        if processed_num_str.startswith('.') and len(processed_num_str) > 1:
            # Starts with '.', okay to parse
            pass  # proceed
        elif processed_num_str.endswith('.') and len(processed_num_str) > 1:
            # This case should ideally be handled in the branches above to convert '1.' to '1'.
            # If we reach here with a trailing dot, it means the specific trailing dot logic didn't match,
            # which implies the format might be ambiguous (e.g. combined with other issues).
            # However, if we must handle it, remove the dot and parse as integer.
            processed_num_str = processed_num_str[:-1]
            logger.debug(
                f"Processed string ends with dot, removing for conversion: '{processed_num_str}'")
        elif processed_num_str == '.':
            logger.debug(f"Processed string is just a dot.")
            return None

        # Try to convert the final processed string to a float
        try:
            # Apply the original sign and return the absolute value
            return abs(sign * float(processed_num_str))

        except ValueError:
            # Log a warning if float conversion fails for the processed string
            logger.warning(
                f"Could not convert final processed string '{processed_num_str}' to float from original '{price_string}'.")
            return None

    async def fetch_and_parse_all(
            self,
            session: ClientSession,
            items_config: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        Fetches and parses prices for a list of items concurrently.

        For each item configuration in the list, it fetches the URL,
        parses the price using the provided selectors, and includes the
        parsing result along with the original item information.

        Args:
            session: An aiohttp ClientSession instance to use for fetching.
            items_config: A list of item configuration dictionaries.
                          Each dictionary is expected to contain at least
                          'url' (str) and 'selector' (Union[str, List[str]]).
                          'name' (str) is used for logging if available.

        Returns:
            A list of dictionaries. Each dictionary is the original item
            configuration dictionary with added keys:
            'price': The parsed price as float, or None.
            'fetch_status': 'success', 'failed', or 'skipped'.
            'error': An error message string if fetch_status is 'failed' or 'skipped'.
        """
        logger.info(
            f"Starting async fetch and parse for {len(items_config)} items...")

        async def fetch_and_parse_single(
                item: Dict[str, Any],
                session: ClientSession
        ) -> Dict[str, Any]:
            """Fetches and parses a single item configuration."""
            url = item.get('url')
            selectors = item.get('selector')
            item_name = item.get('name', 'Unnamed Item')

            # Skip item if required configuration is missing
            if not url or not selectors:
                logger.warning(
                    f"Skipping item '{item_name}': Missing URL or selectors in config.")
                return {**item, 'price': None, 'fetch_status': 'skipped',
                        'error': 'Missing URL or selectors'}

            # Fetch the HTML content
            html_content = await self._get_page_content_async(session, url)

            # Parse the price if content was fetched successfully
            if html_content is not None:
                parsed_price = self._parse_price_from_content(html_content,
                                                              selectors)
                return {**item, 'price': parsed_price,
                        'fetch_status': 'success'}
            else:
                # Return failure status if content could not be fetched
                return {**item, 'price': None, 'fetch_status': 'failed',
                        'error': 'Failed to fetch content'}

        # Create a list of asyncio tasks, one for each item configuration
        tasks = [fetch_and_parse_single(item, session) for item in
                 items_config]

        # Run all tasks concurrently and wait for them to complete
        results = await asyncio.gather(*tasks)

        logger.info("Finished async fetch and parse.")
        return results
