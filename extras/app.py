import re
import os
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
import time
import csv
import json
import logging

logging.basicConfig(level=logging.INFO)

options = webdriver.FirefoxOptions()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
#options.add_argument("--window-size=1920,1080")
#driver = webdriver.Firefox(options=options)

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
            with open(self.filename, 'r') as f:
                return set(json.load(f))
        except (FileNotFoundError, json.JSONDecodeError):
            return set()
            
    def _save_processed_links(self):
        with open(self.filename, 'w') as f:
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
        writer.writerow(["Name", "Company Name", "Company Position", "Address", "Phone Number", "Website"])

def fetch_lawyer_details(part_number, record_count, driver):
    """Extract details of lawyers from the current city page."""
    lawyers = driver.find_elements(By.CSS_SELECTOR, "div.medium-12.columns.card.card--attorney")
    count = 0
    
    for lawyer in lawyers:
        name = lawyer.find_element(By.CSS_SELECTOR, "li.detail_title > a > h3").text
        try:
            company_info = lawyer.find_element(By.CSS_SELECTOR, "li.detail_position").text
        except NoSuchElementException:
            continue
        if " at " in company_info:
            position, company_name = company_info.split(" at ", 1)
        else:
            position = ""
            company_name = company_info
        try:
            address = lawyer.find_element(By.CSS_SELECTOR, "li.detail_location").text
        except NoSuchElementException:
            address = ""
        try:
            phone_element = lawyer.find_element(By.CSS_SELECTOR, "a.webstats-phone-click")
            phone = phone_element.get_attribute("href").replace("tel:", "") if phone_element.get_attribute("href") else ""
        except NoSuchElementException:
            phone = ""
        try:
            website_element = lawyer.find_element(By.CSS_SELECTOR, "a.webstats-website-click")
            website = website_element.get_attribute("href") if website_element.get_attribute("href") else ""
        except NoSuchElementException:
            website = ""
        
        logging.info(f"{name}; {company_name}; {position}; {address}; {phone}; {website}")
        write_to_csv([name, company_name, position, address, phone, website], part_number)
        record_count += 1
        count += 1

        if record_count >= PART_SIZE:
            part_number += 1
            record_count = 0
            write_header(part_number)
    
    return count, part_number, record_count


def navigate_pagination(part_number, record_count, driver):
    """Handle pagination and fetch lawyer details from all pages."""
    count = 0
    while True:
        new_count, part_number, record_count = fetch_lawyer_details(part_number, record_count, driver)
        count += new_count
        try:
            retry_count = 0
            # Was using this earlier
            wait = WebDriverWait(driver, 2)
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "ul.inline-list.right.pagination a[rel='next']")))
            
            # Check if the "Next" button has 'unavailable' class. No more pages to traverse if True.
            if "unavailable" in next_button.get_attribute("class"):
                logging.info("Next button is unavailable. End of pagination.")
                break
            
            next_button.click()
            logging.info("Navigated to the next page.")
            time.sleep(2)  # Wait for next page
        except (NoSuchElementException, TimeoutException, WebDriverException) as e:
            logging.error(f"Error navigating to the next page: {e}")
            retry_count += 1
            if retry_count >= max_retries:
                logging.error("Max retries reached. Exiting loop.")
                break
            continue
    
    logging.info(count)
    return part_number, record_count


def process_city_links(driver, city_links, link_tracker):
    """Iterate over all city links and fetch lawyer data."""
    part_number = 4
    record_count = 0
    
    for i, city_link in enumerate(city_links):
        if link_tracker.is_processed(city_link):
            logging.info(f"Skipping already processed link: {city_link}")
            continue
            
        try:
            driver.get(city_link)
            time.sleep(2)
            part_number, record_count = navigate_pagination(part_number, record_count, driver)
            link_tracker.mark_processed(city_link)
            logging.info(f"Processed city #{i}: {city_link}")
        except WebDriverException as e:
            logging.error(f"Error processing city link {city_link}: {e}")

def read_city_links(file_path):
    with open(file_path, 'r') as file:
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
            remaining_links = [link for link in city_links if not link_tracker.is_processed(link)]
            if not remaining_links:
                logging.info(f"All links in {filename} have been processed. Skipping.")
                continue
                
            with ThreadPoolExecutor(max_workers=5) as executor:
                drivers = [webdriver.Firefox(options=options) for _ in range(5)]
                futures = [
                    executor.submit(
                        process_city_links, 
                        driver, 
                        remaining_links[i::5],
                        link_tracker
                    ) for i, driver in enumerate(drivers)
                ]
                for future in futures:
                    future.result()
                for driver in drivers:
                    driver.quit()
                

# TODO: Rewrite lawyer_data_part_1.csv to contain information from first 100 links in trash.txt
# TODO: Scrape south dakota, tenneessee, texas, utah separately
# TODO: Some part of vermont too, in trash.txt
try:
    write_header(5)
    process_state_links('links/')
except Exception as e:
    print(f"Error occurred: {e}")
#finally:
#    driver.quit()


