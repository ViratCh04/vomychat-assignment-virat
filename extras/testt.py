from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import logging
import time
import csv
#from selenium.webdriver.firefox.service import Service
# Start geckodriver on the custom port
#service = Service(port=6090, executable_path="./geckodriver.exe")

logging.basicConfig(level=logging.INFO)

options = webdriver.FirefoxOptions()
options.add_argument("--headless")
#options.log.level = "trace"
#options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
#driver = webdriver.Firefox(options=options, service=service)
driver = webdriver.Firefox(options=options)
#driver.maximize_window()

def get_states():
    try:
        driver.get("https://www.martindale.com/find-attorneys/")
        time.sleep(5)
        states = []
        parent_element = driver.find_element(By.CSS_SELECTOR, "div.medium-collapse:nth-child(2) > div:nth-child(1) > ul:nth-child(2)")

        li_elements = parent_element.find_elements(By.TAG_NAME, "li")

        for li in li_elements:
            # extract text content of the <a> tag inside each <li> element
            a_tag = li.find_element(By.TAG_NAME, "a")
            states.append(a_tag.text)

        return states, len(states)
    except:
        driver.quit()

def get_cities():
    try:
        driver.get("https://www.martindale.com/by-location/nevada-lawyers/")
        time.sleep(5)
        cities = []
        parent_div = driver.find_element(By.CSS_SELECTOR, "#cityPanelAll")

        child_divs = parent_div.find_elements(By.CSS_SELECTOR, "div[class*='show-for-medium-up'], div[class*='content-list-abc']")
        #child_divs = parent_div.find_elements(By.CSS_SELECTOR, "div.show-for-medium-up:nth-child(1)")
        #child_divs = parent_div.find_elements(By.CSS_SELECTOR, "div.content-list-abc:nth-child(2)")
        #child_divs = parent_div.find_elements(By.CSS_SELECTOR, "div.content-list-abc:nth-child(22)")

        for div in child_divs:
            # Find the ul within each child div
            ul_element = div.find_element(By.TAG_NAME, "ul")
            # Find all li elements within the ul
            li_elements = ul_element.find_elements(By.TAG_NAME, "li")

            for li in li_elements:
                # Extract the text content of the <a> tag inside each <li> element
                a_tag = li.find_element(By.TAG_NAME, "a")
                cities.append(a_tag.text)

        return cities, len(cities)
    except:
        driver.quit()

def get_lawyer_details():
    # if location icon with this css selector(5th comment) shows up, 
    # user is registered and I need to open their details in a new tab to access their address, 
    # which means a call to another subroutine which handles the detailed webpage 
    # maybe we can extract more information from this webpage for brownie points :) 
    
    # Get name, company name, company position, address, phone, website for now
    
    # Visit more pages if there are any(implement pagination)
    
    # Just extract name, company name(if any), position(if any), address for unregistered users- don't prioritize them
    
    # use "at" keyword to split strings into [company position] and [company name] keywords
    
    # Store in csv zzz
    #time.sleep(2)
    #lawyers = driver.find_elements(By.CSS_SELECTOR, "div[class*='medium-12']")
    #lawyers = driver.find_elements(By.CSS_SELECTOR, "div.medium-12:nth-child > div:nth-child")
    lawyers = driver.find_elements(By.CSS_SELECTOR, "div.medium-12.columns.card.card--attorney")

    count = 0
    
    for lawyer in lawyers:
        name = lawyer.find_element(By.CSS_SELECTOR, "li.detail_title > a > h3").text
        company_info = lawyer.find_element(By.CSS_SELECTOR, "li.detail_position").text
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
            #phone = lawyer.find_element(By.CSS_SELECTOR, "a.webstats-phone-click").get_attribute("href").replace("tel:", "")
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
        count += 1
    
    return count


def navigate_pagination():
    """Handle pagination and fetch lawyer details from all pages."""
    count = 0
    #driver.get("https://www.martindale.com/all-lawyers/amargosa-valley/nevada/")
    driver.get("https://www.martindale.com/all-lawyers/bellmore/new-york/")
    #driver.get("https://www.martindale.com/all-lawyers/boston/kentucky/")
    while True:
        count += get_lawyer_details()
        try:
            #next_button = driver.find_element(By.CSS_SELECTOR, "ul.inline-list.right.pagination > li > a.arrow[rel='next']")
            #next_button = driver.find_element(By.CSS_SELECTOR, "ul.inline-list.right.pagination a[rel='next']")
            #next_button = driver.find_element(By.CSS_SELECTOR, "/html/body/div[3]/div/div[16]/div[5]/div[2]/div/div/ul/li[4]/a")
            
            # Was using this earlier
            wait = WebDriverWait(driver, 1)
            next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "ul.inline-list.right.pagination a[rel='next']")))
            
            #next_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "ul.inline-list:nth-child(3) > li:nth-child(4)")))
            #next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "/html/body/div[3]/div/div[16]/div[5]/div[2]/div/div/ul/li[4]/a")))
            
            # Check if the "Next" button has the 'unavailable' class. No more pages to traverse if True.
            if "unavailable" in next_button.get_attribute("class"):
                logging.info("Next button is unavailable. End of pagination.")
                break
            # Click the "Next" button
            #ActionChains(driver).move_to_element(next_button).click(next_button).perform()
            next_button.click()
            logging.info("Navigated to the next page.")
            time.sleep(2)  # Wait for the next page to load
        except NoSuchElementException:
            break  # No more pages
    logging.info(count)
    
    return 

#print(get_states())
#print(get_cities())
navigate_pagination()