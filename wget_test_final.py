#!/usr/bin/env python3
import subprocess
import time
import csv
import os
import re
from lxml.html import fromstring

# Define the CSV file name
FAILED_WEBSITES_CSV = "/home/loris/scripts/failed_websites.csv"
FAILED_CAPTCHAS_CSV = "/home/loris/scripts/failed_captchas.csv"


def has_captcha(html_text: str) -> bool:
    """
    Analyzes an HTML text string to detect signs of a captcha.

    The function looks for common HTML elements, attributes, and text patterns
    associated with captcha challenges, such as reCAPTCHA.
    It now uses lxml for HTML parsing instead of BeautifulSoup.

    Args:
        html_text: A string containing the HTML content to be analyzed.

    Returns:
        True if signs of a captcha are found, False otherwise.
    """
    if not isinstance(html_text, str):
        # Handle cases where the input is not a string
        print("Warning: Input to has_captcha is not a string. Returning False.")
        return False
    if not html_text.strip():
        # Handle empty or whitespace-only strings
        return False

    # Parse the HTML using lxml.html.fromstring
    # This creates an ElementTree-like object that can be queried using XPath.
    try:
        tree = fromstring(html_text)
    except Exception as e:
        print(f"ERROR: Failed to parse HTML with lxml.html.fromstring: {e}")
        return False


    # 1. Look for common text patterns (case-insensitive)
    captcha_keywords = [
        "captcha",
        "recaptcha",
        "i am not a robot",
        "verify you are human",
        "security check",
        "human verification",
        "prove you're not a robot",
        "fill out this challenge",
        "are you a robot?",
    ]
    # Compile regex patterns for efficiency
    keyword_patterns = [re.compile(r'\b' + re.escape(kw) + r'\b', re.IGNORECASE) for kw in captcha_keywords]

    #for pattern in keyword_patterns:
    #    if pattern.search(html_text):
    #        print(f"DEBUG: Found keyword '{pattern.pattern}' in HTML text.")
    #        return True

    # 2. Look for reCAPTCHA specific HTML attributes/classes/IDs using XPath
    # Check for elements with class 'g-recaptcha' (using a robust XPath for whole word class matching)
    g_recaptcha_elements = tree.xpath('//*[contains(concat(" ", normalize-space(@class), " "), " g-recaptcha ")]')
    #if g_recaptcha_elements:
    #    print("DEBUG: Found element with class 'g-recaptcha'.")
    #    return True # General presence detected

    # Check for elements with 'data-sitekey' attribute
    #if tree.xpath('//*[@data-sitekey]'):
    #    print("DEBUG: Found element with 'data-sitekey' attribute.")
    #    return True

    # Check for elements with IDs or classes containing 'captcha' or 'recaptcha'
    #if tree.xpath('//*[contains(@id, "captcha") or contains(@id, "recaptcha") or '
    #               'contains(concat(" ", normalize-space(@class), " "), " captcha ") or '
    #               'contains(concat(" ", normalize-space(@class), " "), " recaptcha ")]'):
    #    print("DEBUG: Found element with 'captcha' or 'recaptcha' in ID or class.")
    #    return True

    # 3. Look for iframes commonly used by captcha services
    #for iframe in tree.xpath('//iframe'):
    #    iframe_src = iframe.get('src', '').lower()
    #    if "google.com/recaptcha" in iframe_src or \
    #       "captcha" in iframe_src: # General check for 'captcha' in iframe source
    #        print(f"DEBUG: Found iframe with captcha-related source: {iframe_src}.")
    #        return True

    # --- New check for "actively prompted" (visible v2 checkbox) ---
    # This is an inference based on static HTML: look for g-recaptcha div NOT explicitly hidden.
    for element in g_recaptcha_elements:
        style_attr = element.get('style', '').lower()
        # If the g-recaptcha element does not have inline styles to hide it
        if "display: none" not in style_attr and "visibility: hidden" not in style_attr:
            print("DEBUG: Found a 'g-recaptcha' element likely visible (not hidden by inline style).")
            # We can't return True directly here as this function is for general captcha presence.
            # However, this specific print statement helps in debugging/understanding the state.
            return True # Keep searching for other captcha signs if this is within main has_captcha

    # If none of the above indicators are found
    return False

def update_failed_captchas(website: str):
    """
    Updates a CSV file to record failed website fetches.
    Increments a counter for existing failed websites or adds a new entry.

    Args:
        website (str): The URL of the website that failed to fetch.
        csv_file_path (str): The absolute path to the CSV file (e.g., "failed_websites.csv").
    """
    data = {}
    # Read existing data
    if os.path.exists(FAILED_CAPTCHAS_CSV):
        try:
            with open(FAILED_CAPTCHAS_CSV, mode='r', newline='') as infile:
                reader = csv.reader(infile)
                for row in reader:
                    if len(row) == 2:
                        try:
                            # Ensure the counter is an integer
                            data[row[0]] = int(row[1])
                        except ValueError:
                            print(f"Warning: Non-integer counter found for {row[0]}. Resetting to 1.")
                            data[row[0]] = 1
                    else:
                        print(f"Warning: Skipping malformed row in CSV: {row}")
        except Exception as e:
            print(f"Error reading: {e}. Starting fresh.")
            data = {} # If read fails, start with empty data

    # Update or add the website counter
    if website in data:
        data[website] += 1
    else:
        data[website] = 1

    # Write all data back to the CSV
    try:
        with open(FAILED_CAPTCHAS_CSV, mode='w', newline='') as outfile:
            writer = csv.writer(outfile)
            for site, counter in data.items():
                writer.writerow([site, counter])
        print(f"Updated failure count for {website} in file: {data[website]}")
    except Exception as e:
        print(f"Error writing: {e}")


def update_failed_websites_csv(website: str):
    """
    Updates a CSV file to record failed website fetches.
    Increments a counter for existing failed websites or adds a new entry.

    Args:
        website (str): The URL of the website that failed to fetch.
        csv_file_path (str): The absolute path to the CSV file (e.g., "failed_websites.csv").
    """
    data = {}
    # Read existing data
    if os.path.exists(FAILED_WEBSITES_CSV):
        try:
            with open(FAILED_WEBSITES_CSV, mode='r', newline='') as infile:
                reader = csv.reader(infile)
                for row in reader:
                    if len(row) == 2:
                        try:
                            # Ensure the counter is an integer
                            data[row[0]] = int(row[1])
                        except ValueError:
                            print(f"Warning: Non-integer counter found for {row[0]}. Resetting to 1.")
                            data[row[0]] = 1
                    else:
                        print(f"Warning: Skipping malformed row in CSV: {row}")
        except Exception as e:
            print(f"Error reading: {e}. Starting fresh.")
            data = {} # If read fails, start with empty data

    # Update or add the website counter
    if website in data:
        data[website] += 1
    else:
        data[website] = 1

    # Write all data back to the CSV
    try:
        with open(FAILED_WEBSITES_CSV, mode='w', newline='') as outfile:
            writer = csv.writer(outfile)
            for site, counter in data.items():
                writer.writerow([site, counter])
        print(f"Updated failure count for {website} in file: {data[website]}")
    except Exception as e:
        print(f"Error writing: {e}")


def fetch_html_with_wget(url: str, user_agent: str = "Mozilla/5.0 (compatible; Wget/1.21.3; +https://example.com/bot)") -> str | None:
    """
    Executes a wget request to a given URL and returns its HTML content.

    Args:
        url (str): The URL of the website to fetch.
        user_agent (str): The User-Agent string to use for the wget request.
                          It's good practice to set a custom, identifiable User-Agent.

    Returns:
        str | None: The HTML content of the website as a string, or None if an error occurred.
    """
    print(f"Attempting to fetch HTML from: {url}")
    try:
        command = [
            "wget",
            "-qO-",
            "--wait=1",  # Wait 1 second between requests (adjust as needed)
            f"-U={user_agent}",
            "--tries=1",  # Do not retry on transient errors
            url
        ]
        result = subprocess.run(command, capture_output=True, text=True, check=True)
        print(f"Successfully fetched HTML from: {url}")
        if has_captcha(result.stdout):
            update_failed_captchas(url)
        return result.stdout
    except subprocess.CalledProcessError as e:
        print(f"Error fetching {url}: Wget failed with exit code {e.returncode}")
        print(f"Stderr: {e.stderr}")
        update_failed_websites_csv(url)  # Call the CSV update function on failure
        return None
    except FileNotFoundError:
        print("Error: 'wget' command not found. Please ensure wget is installed and in your system's PATH.")
        update_failed_websites_csv(url)  # Call the CSV update function on failure
        return None
    except Exception as e:
        print(f"An unexpected error occurred while fetching {url}: {e}")
        update_failed_websites_csv(url)  # Call the CSV update function on failure
        return None


def process_websites(website_list: list[str]) -> dict[str, str | None]:
    """
    Iterates through a list of website URLs, fetches their HTML content using wget,
    and returns a dictionary of URLs to their HTML content.

    Args:
        website_list (list[str]): A list of website URLs to process.

    Returns:
        dict[str, str | None]: A dictionary where keys are the URLs and values are
                               the fetched HTML content (or None if fetching failed).
    """
    results = {}
    for url in website_list:
        html_content = fetch_html_with_wget(url)
        results[url] = html_content
        # You might want to add a small delay here if processing many websites
        # to be even more polite and avoid triggering aggressive rate limits.
        # time.sleep(0.5)
    return results


if __name__ == "__main__":
    # --- Example Usage ---

    # 1. Example of fetching a single website's HTML
    print("\n--- Fetching a single website ---")
    single_website_url = "https://www.example.com"
    html_example = fetch_html_with_wget(single_website_url)

    if html_example:
        # Print first 500 characters of the HTML
        print(f"\n--- HTML Content (first 500 chars) for {single_website_url} ---")
        print(html_example[:500])
        print("...")
    else:
        print(f"Failed to retrieve HTML for {single_website_url}.")

    # 2. Example of fetching HTML from a list of websites
    print("\n--- Fetching HTML from a list of websites ---")
    #websites_to_process = [
    #    "https://www.google.com",
    #    "https://www.bing.com",
    #    "https://nonexistent-website-12345.com",  # This will likely fail
    #    "https://www.python.org",
    #    "http://definitely-not-a-real-site.org", # Another site to test failure tracking
    #]
    

    websites_to_process = [
    # 10 E-commerce Websites Based on WordPress (often with WooCommerce)
    "https://www.nalgene.com/",
    "https://www.airstream.com/",
    "https://jococups.com/",
    "https://www.robertocoin.com/",
    "https://friendlyfires.ca/", # This is likely the e-commerce site for Friendly Fires (Canada)
    "https://disruptedyouth.com/",
    "https://rootscience.com/",
    "https://thehouseofwhisky.com/",
    "https://www.colagourmet.com/",
    "https://bookriot.com/", # While Book Riot sells merchandise, their primary e-commerce might be through a sub-domain or integrated section. This is the main site.

    # 10 E-commerce Websites Based on Shopify
    "https://www.allbirds.com/",
    "https://eu.gymshark.com/", # Using the EU domain as an example
    "https://kyliecosmetics.com/",
    "https://www.fashionnova.com/",
    "https://bombas.com/",
    "https://hiutdenim.co.uk/",
    "https://pelacase.com/",
    "https://www.tentree.com/",
    "https://www.adoredvintage.com/",
    "https://www.stevemadden.com/",

    # 10 E-commerce Websites Based on WooCommerce
    "https://www.eatstroopwafels.com/",
    "https://porterandyork.com/",
    "https://www.magnatiles.com/",
    "https://godinguitars.com/",
    "https://www.printingnewyork.com/",
    "https://offermanwoodshop.com/",
    "https://www.kawaiibox.com/",
    "https://sodashi.com.au/",
    "https://jackrudycocktailco.com/", 
    "https://2captcha.com/demo/cloudflare-turnstile",
    "https://www.google.com/recaptcha/api2/demo",
    "https://www.aprilsoderstrom.com/"]

    all_html_results = process_websites(websites_to_process)

    print("\n--- Summary of results from list processing ---")
    for url, html_content in all_html_results.items():
        if html_content:
            print(f"[{url}]: Successfully fetched (length: {len(html_content)} characters)")
        else:
            print(f"[{url}]: Failed to fetch HTML")

    print("\nScript execution finished.")
