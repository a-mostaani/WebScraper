# Scope
LLM-Based web scraper, which receives an instruction for data extraction together with a list of urls to extract the requested data from the list of indicated urls.

# Tech Summary
This project is a parallelized web scraper with a Streamlit UI. It accepts URLs, scrapes structured content, and displays results with export options.

## Features
- Parallel scraping (multithreading)
- Auto extraction of titles and metadata
- Streamlit-based UI with file input
- Export to CSV and JSON

## Assumptions
- The web page that is scraped is publicly available without a need for login
- There is no need to pass through a captcha
- The page that is scrapped is not paginated or framed, iFramed, or if it is, only the first visible page is scraped
- In every user instruction, there is one main data subject you want to acquire data for but that one data subject can have many data categories associated with it.
For example: you can ask the scraper to find information about all footbal teams and their won championships, their current coach and many other data categories associate with the footbal team.
Yet you cannot ask the scraper to find information about both footbal teams and vollibal teams and their won championships etc. These are two different data subjects altogether. Current scraper is not guranteed to handle this type of task.
- 

## Setup
```bash
pip install -r requirements.txt
streamlit run main.py

