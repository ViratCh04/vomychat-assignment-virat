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

options = webdriver.FirefoxOptions()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
#options.add_argument("--window-size=1920,1080")
driver = webdriver.Firefox(options=options)

BASE_URL = "https://www.martindale.com/by-location/"


def get_links(state_link, city_links):
    def extract_state_name(url):
        """Extract the state name from the given URL string."""
        # Use regular expression to find the state name in the URL
        match = re.search(r'by-location/([a-z-]+)-lawyers', url)
        if match:
            state_name = match.group(1).replace('-', ' ')
            return state_name
        return None

    #state_link = state_link.translate({ord(ch):' ' for ch in './:-'})
    state_name = extract_state_name(state_link)
    with open(f'links/{state_name}.txt', 'w') as f:
        for link in city_links:
            f.write(f"{link}\n")


def process_state_links():
    """
    Visit each state and extract city links
    """
    state_count = 0
    driver.get(BASE_URL)
    time.sleep(2)
    state_links = [
        state.get_attribute("href")
        for state in driver.find_elements(By.CSS_SELECTOR, "div.medium-collapse:nth-child(2) ul:nth-child(2) li a")
    ]
    #print(len(state_links))
    
    for i, state_link in enumerate(state_links):
        driver.get(state_link)
        time.sleep(2)  # Allow state page to load

        city_links = [
            city.get_attribute("href")
            for city in driver.find_elements(By.CSS_SELECTOR, "#cityPanelAll div ul li a")
        ]
        get_links(state_links, city_links)
        
        #print(len(city_links))
        #process_city_links(city_links)
        
        state_count += 1
        print(f"We are at state #{state_count}")


process_state_links()