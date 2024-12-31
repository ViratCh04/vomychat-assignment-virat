import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)
from concurrent.futures import ThreadPoolExecutor
import time
import csv
import logging
import json
from datetime import datetime
from urllib.parse import urlparse
import hashlib

os.makedirs("logs", exist_ok=True)
os.makedirs("logs/cities", exist_ok=True)

logging.basicConfig(level=logging.INFO)

options = webdriver.FirefoxOptions()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
# options.add_argument("--window-size=1920,1080")
# driver = webdriver.Firefox(options=options)

BASE_URL = "https://www.martindale.com/by-location/"
OUTPUT_FILE_PREFIX = "lawyer_data_part"
PART_SIZE = 5000  # Number of records per part

PROCESSED_LINKS_FILE = "processed_links.json"

max_retries = 2


class LinkTracker:
    def __init__(self, filename=PROCESSED_LINKS_FILE):
        self.filename = filename
        self.processed_links = self._load_processed_links()

    def _load_processed_links(self):
        try:
            with open(self.filename, "r") as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()

    def _save_processed_links(self):
        with open(self.filename, "w") as f:
            json.dump(list(self.processed_links), f)

    def is_processed(self, link):
        return link in self.processed_links

    def mark_processed(self, link):
        self.processed_links.add(link)
        self._save_processed_links()


def get_output_file(part_number):
    return f"data/{OUTPUT_FILE_PREFIX}_{part_number}.csv"


def write_to_csv(data, part_number):
    """Write scraped data to a CSV file."""
    output_file = get_output_file(part_number)
    with open(output_file, mode="a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(data)


def write_header(part_number):
    output_file = get_output_file(part_number)
    with open(output_file, mode="w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(
            [
                "Name",
                "Company Name",
                "Company Position",
                "Address",
                "Phone Number",
                "Website",
            ]
        )


class CityLogger:
    def __init__(self, city_url):
        parsed_url = urlparse(city_url)
        city_path = parsed_url.path
        url_hash = hashlib.md5(city_url.encode()).hexdigest()[:8]

        city_name = (
            city_path.split("/")[-2]
            if city_path.endswith("/")
            else city_path.split("/")[-1]
        )
        city_name = city_name.replace("-lawyers", "").replace("-law-firms", "")

        self.logger = logging.getLogger(f"city_{url_hash}")
        if not self.logger.handlers:
            self.logger.setLevel(logging.INFO)

            # File handler (logs to file)
            log_file = f"logs/cities/{city_name}_{url_hash}.log"
            self.file_handler = logging.FileHandler(log_file, encoding="utf-8")
            self.file_handler.setLevel(logging.INFO)

            # Stream handler (logs to terminal)
            self.stream_handler = logging.StreamHandler()
            self.stream_handler.setLevel(logging.INFO)

            # Create formatter and add it to the handlers
            formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")
            self.file_handler.setFormatter(formatter)
            self.stream_handler.setFormatter(formatter)

            # Add both handlers to the logger
            self.logger.addHandler(self.file_handler)
            self.logger.addHandler(self.stream_handler)

            # Keep propagate=False since we're handling console output ourselves
            self.logger.propagate = False

    def __enter__(self):
        return self.logger

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.file_handler.close()
        self.logger.removeHandler(self.file_handler)
        self.logger.removeHandler(self.stream_handler)


class CityProcessor:
    def __init__(self, city_url, part_number, record_count):
        self.city_url = city_url
        self.part_number = part_number
        self.record_count = record_count
        self.total_lawyers_processed = 0
        self.start_time = None
        self.end_time = None
        self.city_logger = CityLogger(city_url)

    def log_start(self):
        self.start_time = datetime.now()
        self.logger.info(f"Started processing city: {self.city_url}")

    def log_completion(self):
        self.end_time = datetime.now()
        duration = self.end_time - self.start_time
        self.logger.info(f"Completed processing city: {self.city_url}")
        self.logger.info(f"Total lawyers processed: {self.total_lawyers_processed}")
        self.logger.info(f"Processing duration: {duration}")

    def log_error(self, error_msg):
        self.logger.error(f"Error processing city {self.city_url}: {error_msg}")

    def fetch_lawyer_details(self, driver):
        """Extract details of lawyers from the current city page."""
        with self.city_logger as logger:
            lawyers = driver.find_elements(
                By.CSS_SELECTOR, "div.medium-12.columns.card.card--attorney"
            )
            count = 0

            for lawyer in lawyers:
                try:
                    name = lawyer.find_element(
                        By.CSS_SELECTOR, "li.detail_title > a > h3"
                    ).text
                    try:
                        company_info = lawyer.find_element(
                            By.CSS_SELECTOR, "li.detail_position"
                        ).text
                    except NoSuchElementException:
                        logger.warning(f"No company info found for lawyer: {name}")
                        continue

                    if " at " in company_info:
                        position, company_name = company_info.split(" at ", 1)
                    else:
                        position = ""
                        company_name = company_info

                    try:
                        address = lawyer.find_element(
                            By.CSS_SELECTOR, "li.detail_location"
                        ).text
                    except NoSuchElementException:
                        address = ""
                        logger.debug(f"No address found for lawyer: {name}")

                    try:
                        phone_element = lawyer.find_element(
                            By.CSS_SELECTOR, "a.webstats-phone-click"
                        )
                        phone = (
                            phone_element.get_attribute("href").replace("tel:", "")
                            if phone_element.get_attribute("href")
                            else ""
                        )
                    except NoSuchElementException:
                        phone = ""
                        logger.debug(f"No phone found for lawyer: {name}")

                    try:
                        website_element = lawyer.find_element(
                            By.CSS_SELECTOR, "a.webstats-website-click"
                        )
                        website = (
                            website_element.get_attribute("href")
                            if website_element.get_attribute("href")
                            else ""
                        )
                    except NoSuchElementException:
                        website = ""
                        logger.debug(f"No website found for lawyer: {name}")

                    logger.info(f"Processing lawyer: {name}")
                    write_to_csv(
                        [name, company_name, position, address, phone, website],
                        self.part_number,
                    )
                    self.record_count += 1
                    count += 1
                    self.total_lawyers_processed += 1

                    if self.record_count >= PART_SIZE:
                        self.part_number += 1
                        self.record_count = 0
                        write_header(self.part_number)

                except Exception as e:
                    logger.error(f"Error processing lawyer element: {e}", exc_info=True)

            return count, self.part_number, self.record_count

    def navigate_pagination(self, driver):
        """Handle pagination and fetch lawyer details from all pages."""
        with self.city_logger as logger:
            page_number = 1
            while True:
                logger.info(f"Processing page {page_number}")
                try:
                    new_count, self.part_number, self.record_count = (
                        self.fetch_lawyer_details(driver)
                    )
                    logger.info(f"Processed {new_count} lawyers on page {page_number}")

                    try:
                        wait = WebDriverWait(driver, 2)
                        next_button = wait.until(
                            EC.element_to_be_clickable(
                                (
                                    By.CSS_SELECTOR,
                                    "ul.inline-list.right.pagination a[rel='next']",
                                )
                            )
                        )

                        if "unavailable" in next_button.get_attribute("class"):
                            logger.info("Reached last page")
                            break

                        next_button.click()
                        logger.info(f"Navigating to page {page_number + 1}")
                        time.sleep(2)
                        page_number += 1

                    except (NoSuchElementException, TimeoutException) as e:
                        logger.error(f"Error with pagination: {e}")
                        break

                except Exception as e:
                    logger.error(
                        f"Error processing page {page_number}: {e}", exc_info=True
                    )
                    break

            return self.part_number, self.record_count

    def process_city(self, driver):
        with self.city_logger as logger:
            self.start_time = datetime.now()
            logger.info(f"Started processing city: {self.city_url}")

            try:
                driver.get(self.city_url)
                time.sleep(2)

                self.part_number, self.record_count = self.navigate_pagination(driver)

                self.end_time = datetime.now()
                duration = self.end_time - self.start_time
                logger.info(f"Completed processing city: {self.city_url}")
                logger.info(f"Total lawyers processed: {self.total_lawyers_processed}")
                logger.info(f"Processing duration: {duration}")

            except WebDriverException as e:
                logger.error(f"WebDriver error: {e}")
            except Exception as e:
                logger.error(f"Unexpected error: {e}")

            return self.part_number, self.record_count


def process_city_links(driver, city_links, link_tracker):
    """Iterate over all city links and fetch lawyer data."""
    part_number = 8
    record_count = 0

    for city_link in city_links:
        if link_tracker.is_processed(city_link):
            continue

        processor = CityProcessor(city_link, part_number, record_count)
        part_number, record_count = processor.process_city(driver)
        link_tracker.mark_processed(city_link)


def read_city_links(file_path):
    with open(file_path, "r") as file:
        return [line.strip() for line in file.readlines()]


def process_state_links(directory):
    """Process all city links from text files in the given directory."""
    link_tracker = LinkTracker()

    for filename in os.listdir(directory):
        if filename.endswith(".txt"):
            file_path = os.path.join(directory, filename)
            city_links = read_city_links(file_path)
            logging.info(f"Processing file: {filename}")

            # Filter out already processed links
            remaining_links = [
                link for link in city_links if not link_tracker.is_processed(link)
            ]
            if not remaining_links:
                logging.info(f"All links in {filename} have been processed. Skipping.")
                continue

            with ThreadPoolExecutor(max_workers=5) as executor:
                drivers = [webdriver.Firefox(options=options) for _ in range(5)]
                futures = [
                    executor.submit(
                        process_city_links, driver, remaining_links[i::5], link_tracker
                    )
                    for i, driver in enumerate(drivers)
                ]
                for future in futures:
                    future.result()
                for driver in drivers:
                    driver.quit()


try:
    write_header(8)
    process_state_links("links/")
except Exception as e:
    print(f"Error occurred: {e}")
