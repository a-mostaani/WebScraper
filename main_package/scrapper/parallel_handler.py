import concurrent.futures
import requests
from main_package.scrapper.agent_llm import Scrapper_agent

def scrape_urls_parallel(urls: list, user_instruction: str) -> list:
    results = []

    def fetch_and_extract(url):
        try:
            print(f"Fetching and processing: {url}")
            # Fetch the raw HTML content from the URL
            response = requests.get(url, timeout=30)
            html_content = response.text

            # Use the Scrapper_agent to process the HTML
            structured_data = Scrapper_agent.create_index_and_query(html_content, user_instruction)

            # Return the extracted data along with the URL
            return {"url": url, "data": structured_data}

        except Exception as e:
            # Catch any network or processing errors
            return {"url": url, "error": str(e)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # Use a list of URLs to map to the fetch_and_extract function
        results = list(executor.map(fetch_and_extract, urls))

    return results

