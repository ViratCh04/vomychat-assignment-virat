The scraped data is stored in `final/` directory after having gone through formatting by `data_handling.py`. 
The file is named `final_lawyer_data.xlsx` and `final_lawyer_data.csv` and any can be used as proof of work.

The scraper code is stored in `main.py` and it contains all of the necessary code which was used to scrape the lawyer contents off of [Martin Dale lawyer directory](https://www.martindale.com).


Extra code used for prototyping is located in extras. I could have added the unprocessed data as well but famous firms are able to provide their services across multiple cities and as such there was really a huge amount of data to go through since duplicacy was a significant issue once the scraping was done. 4 states in general weren't able to be scraped appropriately, namely, South Dakota, Tennessee, Texas, Utah as the website was giving me some DNS errors which I would not have been able to resolve before the deadline which happens to be today. 


My approach for solving this problem revolves around building a custom scraper of my own as automation workflow tools such as [Make](make.com) require LLM api keys and without SoTA models like GPT-4o, I would not have been able to process the data accurately and fast enough. Additionally, each page opened will have a large amount of html code and even if I were to use my OpenAI credits for the same, the costs will ramp up over time. 

As it was suggested to use a tool I was familiar with, I picked Selenium as my go to choice since I have previous internship experience in building scrapers and workflows(albeit hardcoded) with this. 

My choice of website might appear strange since it was suggested that I visit the state bar websites for lawyers but each website would then have required a different scraper application in Python and you can see how that would get terribly inefficient. Additionally, not all states have a publicly accessible lawyer directory and ratelimiting would have been an issue. 