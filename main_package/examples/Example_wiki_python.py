from llama_index.readers.file import MarkdownReader

from main_package.scrapper.agent_llm import Scrapper_agent
import requests
import io
import pandas as pd
import logging
from main_package.scrapper.parallel_handler import scrape_urls_parallel
from main_package.scrapper.utils import MarkdownReader

# url = "https://en.wikipedia.org/wiki/Python_(programming_language)"
# user_request = " Extract the Python language’s release date, the name of its designer, and the typing discipline (e.g., dynamic, strong, duck typing) from the page. "
#
#
# # url = "https://www.scrapethissite.com/pages/simple/"
# # user_request = "extract the list of all countries in the world along their capitals and their population."
#
#
#
# html_txt = requests.get(url).text
# result = Scrapper_agent.create_index_and_query(html_txt, user_request, "llama3")


# Example usage
urls_to_scrape = [
    "http://books.toscrape.com/",  # A good example page for scraping
    "http://quotes.toscrape.com/",
    "http://quotes.toscrape.com/scroll",
]

# http://books.toscrape.com/
# http://quotes.toscrape.com/
# http://quotes.toscrape.com/scroll

# The single instruction that will be used for all URLs
instruction = "I want a list of all the books, their titles, and prices on the page."

scraped_results = scrape_urls_parallel(urls_to_scrape, instruction)

#--------------------------------------------------------------- can be removed -->

# # Process the raw results to parse markdown tables
# parsed_dfs = []
# for result in scraped_results:
#     if result['data'] and not "Error" in result['data']:
#         try:
#             # Convert markdown string to a file-like object
#             markdown_data = io.StringIO(list(result['data']['relevant_info'])[0])
#             # Read the markdown table as a CSV
#             df_page = pd.read_csv(markdown_data, sep='|', header=0, skiprows=[1], engine='python')
#             # Clean up the DataFrame
#             df_page = df_page.dropna(axis=1, how='all')
#             df_page = df_page.iloc[:, 1:-1] # Remove the first and last empty columns from markdown parsing
#             df_page.columns = [col.strip() for col in df_page.columns]
#             df_page = df_page.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
#             df_page['Source URL'] = result['url']
#             parsed_dfs.append(df_page)
#         except Exception as e:
#             logging.error(f"Could not parse data from {result['url']}: {e}")
#
#     elif result['error']:
#         logging.error(f"Failed to scrape {result['url']}: {result['error']}")
#
# if parsed_dfs:
#     final_df = pd.concat(parsed_dfs, ignore_index=True)
#
#
#     # Prepare files for download
#     csv_data = final_df.to_csv(index=False).encode('utf-8')
#
#
# else:
#     print("No data was successfully scraped and parsed.")

#--------------------------------------------------------------- can be removed <--

final_df, downloads = MarkdownReader.MarkDownToDigitalCsv(scraped_results)

for result in scraped_results:
    print("\n--- Processing Result ---")
    print(f"URL: {result.get('url')}")
    if result.get('error'):
        print(f"Error: {result['error']}")
    else:
        print(f"Extracted Data:\n{result['data']}")

