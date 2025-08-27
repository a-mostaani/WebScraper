# Clean up the data rows by stripping whitespace from each cell
import io
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from llama_index.readers.file import MarkdownReader
import csv
import re
import pandas as pd
import logging
import os
from typing import Dict, List
import base64, hashlib
from llama_index.core import Document  # v0.10+ import
import ollama
from typing import List


PRICE_RE = re.compile(r'(\d[\d\.\s]*)(?:\s*€)', re.UNICODE)
AD_HREF_PAT = re.compile(r'/([a-z]{2}/)?usedcar/[^"]+?\.html\?id=\d+', re.I)


class ArrayGenerators:

    def create_dict_with_empty_lists(n_keys: int, keys: List[str] = None) -> dict:
        """
        Creates a Python dictionary with 'n_keys', where each key corresponds to an empty list.

        If a list of key names is provided, it will use those names. Otherwise, it will
        generate default key names.

        Args:
            n_keys (int): The number of keys to create in the dictionary.
            keys (List[str], optional): A list of strings to use as key names.
                                         Must have a length equal to n_keys. Defaults to None.

        Returns:
            dict: A dictionary with 'n_keys' and an empty list as the value for each key.

        Raises:
            ValueError: If a 'keys' list is provided and its length does not match 'n_keys'.
        """
        # Use a dictionary comprehension for a clean and efficient creation process.
        if keys:
            # Check if the number of keys provided matches the requested number of keys.
            if len(keys) != n_keys:
                raise ValueError(f"The number of keys provided ({len(keys)}) must match n_keys ({n_keys}).")

            # Create the dictionary using the provided keys.
            return {key: [] for key in keys}
        else:
            # If no keys are provided, generate default key names like 'key_0', 'key_1', etc.
            return {f"key_{i}": [] for i in range(n_keys)}


class WebPageReader:
    def extract_listing_links(html_bytes: bytes, base_url: str):
        """Robustly pull ad-detail links from a listing page."""
        soup = BeautifulSoup(html_bytes, "lxml")  # lxml is more forgiving than the default parser
        links = set()

        # Primary: any <a> whose href contains /usedcar/ and ends with id=...
        for a in soup.select('a[href]'):
            href = a.get('href', '')
            if AD_HREF_PAT.search(href):
                links.add(urljoin(base_url, href))

        # Fallback: regex over raw HTML in case attributes are weirdly split
        if not links:
            html_txt = html_bytes.decode("utf-8", "ignore")
            for m in AD_HREF_PAT.finditer(html_txt):
                links.add(urljoin(base_url, m.group(0)))

        return sorted(links)

    def extract_price_from_detail(html):
        soup = BeautifulSoup(html, "html.parser")
        txt = soup.get_text(" ", strip=True)
        # Try a narrow search near the "Price" label first (detail pages)
        price_block = ""
        for label in soup.find_all(string=re.compile(r'\bPrice\b', re.I)):
            # look at the parent chunk for a nearby euro amount
            chunk = label.parent.get_text(" ", strip=True)
            m = PRICE_RE.search(chunk)
            if m:
                price_block = m.group(0)
                break
        if not price_block:
            # fallback: global search in the whole page text
            m = PRICE_RE.search(txt)
            if m:
                price_block = m.group(0)
        if not price_block:
            return None, None
        # normalize "33.999 €" -> 33999
        amount_txt = PRICE_RE.search(price_block).group(1)
        amount_num = int(re.sub(r'[^\d]', '', amount_txt))
        return price_block, amount_num


    def debug_anchor_sample(html_bytes: bytes, base_url: str, n=10):
        soup = BeautifulSoup(html_bytes, "lxml")
        anchors = soup.select('a[href]')
        print(f"Total <a> tags: {len(anchors)}")
        # show a few that look like detail links
        sample = []
        for a in anchors:
            href = a.get('href', '')
            if '/usedcar/' in href or 'id=' in href:
                sample.append(urljoin(base_url, href))
            if len(sample) >= n:
                break
        print("Sample candidate hrefs:")
        for h in sample:
            print("  ", h)


class WorkerLogger:
    def __init__(self):
        self.LOG_FILE_PATH = "scrapper_log.txt"
    # This function configures a file logger for each process.
    def setup_worker_logger(self):
        # Use a unique logger name for each process to avoid conflicts
        worker_logger = logging.getLogger(f"Worker_{os.getpid()}")
        if not worker_logger.handlers:
            file_handler = logging.FileHandler(self.LOG_FILE_PATH)
            formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(formatter)
            worker_logger.addHandler(file_handler)
            worker_logger.setLevel(logging.INFO)
        return worker_logger


class DataCleaner:

    def DirtyStringCleaner(dirty_string):
        # Step 1: Remove leading and trailing whitespace and newline characters
        cleaned_string = dirty_string.strip()

        # Step 2: Remove all non-alphanumeric characters (excluding spaces)
        # This includes the pipe '|' and any other symbols.
        cleaned_string = re.sub(r'[^a-zA-Z0-9 ]', '', cleaned_string)

        # Step 3: Replace multiple spaces with a single space
        # This cleans up any extra spacing that may have been created.
        cleaned_string = re.sub(r' +', ' ', cleaned_string)

        # Step 4: Final strip to remove any leading/trailing space
        cleaned_string = cleaned_string.strip()

        return cleaned_string

class MarkdownReader:

    def MarkDownToCsv(markdown_data, data_subject):

        # The first line is the header, which we will use for the CSV file.
        # The second line is the separator, which we can ignore.
        lines = markdown_data.strip().split('\n')
        headers = [h.strip() for h in lines[0].strip('| ').split('|')]
        data_rows = [line.strip().strip('| ').split('|') for line in lines[2:]]

        cleaned_rows = []
        for row in data_rows:
            cleaned_row = [cell.strip() for cell in row]
            cleaned_rows.append(cleaned_row)

        # Now, write the data to a new CSV file
        file_name = DataCleaner.DirtyStringCleaner(data_subject)
        csv_filename = f"{file_name}.csv"

        with open(csv_filename, 'w', newline='', encoding='utf-8') as csvfile:
            csv_writer = csv.writer(csvfile)

            # Write the header row
            csv_writer.writerow(headers)

            # Write the data rows
            csv_writer.writerows(cleaned_rows)


    def MarkDownToDigitalCsv(scraped_results):

        # Process the raw results to parse markdown tables
        parsed_dfs = []
        for result in scraped_results:
            if result['data'] and not "Error" in result['data']:
                try:
                    # Convert markdown string to a file-like object
                    markdown_data = io.StringIO(list(result['data']['relevant_info'])[0])
                    # Read the markdown table as a CSV
                    df_page = pd.read_csv(markdown_data, sep='|', header=0, skiprows=[1], engine='python')
                    # Clean up the DataFrame
                    df_page = df_page.dropna(axis=1, how='all')
                    # df_page = df_page.iloc[:, 1:-1] # Remove the first and last empty columns from markdown parsing
                    df_page.columns = [col.strip() for col in df_page.columns]
                    df_page = df_page.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
                    df_page['Source URL'] = result['url']
                    parsed_dfs.append(df_page)
                except Exception as e:
                    logging.error(f"Could not parse data from {result['url']}: {e}")

            elif result['error']:
                logging.error(f"Failed to scrape {result['url']}: {result['error']}")

        if parsed_dfs:
            final_df = pd.concat(parsed_dfs, ignore_index=True)


            # 1. Prepare CSV file for download
            csv_data = final_df.to_csv(index=False).encode('utf-8')

            # 2. Prepare JSON data for download
            # Orient='records' is often the most useful format for this type of data
            json_data = final_df.to_json(orient='records', indent=4)

            return csv_data, json_data


        else:
            logging.error(f"No data was successfully scraped and parsed.")

            return None


class DataMapper:
# if you're on old code, use: from llama_index.legacy import Document

    def data_map_to_documents(data_map: Dict[str, dict]) -> List[Document]:
        docs: List[Document] = []
        for url, rec in data_map.items():
            # accept either plaintext html or base64 bytes
            if "html" in rec and isinstance(rec["html"], str):
                html_text = rec["html"]
            elif "html_bytes_b64" in rec:
                enc = rec.get("encoding", "utf-8")
                html_text = base64.b64decode(rec["html_bytes_b64"]).decode(enc, errors="replace")
            else:
                continue

            # stable id: use the url (or hash if you prefer shorter)
            doc_id = url  # or hashlib.md5(url.encode()).hexdigest()

            docs.append(
                Document(
                    id_=doc_id,
                    text=html_text,                 # raw HTML string
                    metadata={
                        "source": "luxauto",
                        "url": url,
                        "encoding": rec.get("encoding", "utf-8"),
                        "fetched_at": rec.get("fetched_at"),
                    },
                    # optional: embed metadata into text for downstream prompts
                    # text_template="URL: {metadata[url]}\n-----\n{content}",
                )
            )
        return docs



class LLMInteractions:

    def get_llama3_response_non_streaming(prompt_text, model_name="llama3"):
        """
        Sends a prompt to Llama 3 (via Ollama) and retrieves the full response.
        """
        try:
            # ollama.chat() is generally preferred for conversational models like Llama 3
            # It takes a list of messages, allowing for conversational context
            response = ollama.chat(
                model=model_name,
                messages=[
                    {'role': 'user', 'content': prompt_text},
                ],
                stream=False # Set to False for non-streaming
            )

            # The response structure for ollama.chat (non-streaming)
            # is a dictionary, where the message content is under ['message']['content']
            if 'message' in response and 'content' in response['message']:
                llama_message = response['message']['content']
                return llama_message
            else:
                print(f"Error: Unexpected response format for non-streaming chat: {response}")
                return None

        except ollama.ResponseError as e:
            print(f"Ollama API Error (Status {e.status_code}): {e.error}")
            return None
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
            return None