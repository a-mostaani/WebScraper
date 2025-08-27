from annotated_types.test_cases import cases
from llama_index.core import Document, VectorStoreIndex, SimpleDirectoryReader
from llama_index.core.query_engine import RetrieverQueryEngine
from llama_index.llms.ollama import Ollama
from bs4 import BeautifulSoup
import logging
import os
import logging
from llama_index.core import Document, VectorStoreIndex, Settings
from llama_index.core.node_parser import SentenceSplitter
from llama_index.llms.ollama import Ollama
from llama_index.embeddings.ollama import OllamaEmbedding
from bs4 import BeautifulSoup
from llama_index.llms.gemini import Gemini
from llama_index.embeddings.gemini import GeminiEmbedding
from sympy.strategies.core import switch

from main_package.scrapper.utils import MarkdownReader
from llama_index.core.node_parser import SentenceSplitter
import asyncio
from main_package.scrapper.utils import WorkerLogger
from dotenv import load_dotenv
from bs4 import BeautifulSoup
import requests, time, json, hashlib
from urllib.parse import urljoin
from llama_index.core.node_parser import HTMLNodeParser





# Example usage:
# blob = fetch_page("https://www.luxauto.lu/en/usedcar/...html?id=123456")
# with open(f"/tmp/{hashlib.md5(blob['url'].encode()).hexdigest()}.html","wb") as f:
#     f.write(blob["content_bytes"])  # archive raw
# parsed = parse_all(blob["content_bytes"], base_url=blob["url"], encoding=blob["encoding"])



class Scrapper_agent:

        #step 0 fetch all the data of a webpage
        def fetch_page(url, session=None, timeout=30):
            s = session or requests.Session()
            # A realistic UA + language helps with EU sites
            headers = {
                "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                              "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "Accept-Language": "en,en-GB;q=0.9,fr;q=0.8,de;q=0.7"
            }
            r = s.get(url, headers=headers, timeout=timeout)
            r.raise_for_status()
            # Keep original bytes and server-declared encoding
            return {
                "url": r.url,
                "status": r.status_code,
                "headers": dict(r.headers),
                "fetched_at": int(time.time()),
                "content_bytes": r.content,          # save this to disk verbatim
                "encoding": r.encoding or "utf-8"
            }

        def parse_all(html_bytes, base_url, encoding="utf-8"):
            soup = BeautifulSoup(html_bytes, "html.parser", from_encoding=encoding)

            # 1) Raw visible text (what your function did)
            visible_text = soup.get_text(separator="\n", strip=True)

            # 2) Metadata & structured data
            meta = {m.get("name") or m.get("property") or m.get("http-equiv"): m.get("content")
                    for m in soup.find_all("meta") if m.get("content")}
            ld_json = [s.get_text() for s in soup.find_all("script", type="application/ld+json")]
            noscript_text = "\n".join(ns.get_text(" ", strip=True) for ns in soup.find_all("noscript"))

            # 3) Links, images, canonical, hreflang
            canonical = (soup.find("link", rel="canonical") or {}).get("href")
            hrefs = [urljoin(base_url, a.get("href")) for a in soup.find_all("a", href=True)]
            images = [{
                "src": urljoin(base_url, img.get("src")),
                "alt": img.get("alt"),
                "width": img.get("width"),
                "height": img.get("height")
            } for img in soup.find_all("img") if img.get("src")]

            # 4) Tables (keep structure)
            tables_html = [str(t) for t in soup.find_all("table")]

            # 5) Useful attributes often holding data
            data_attrs = []
            for tag in soup.find_all(True):
                for k, v in tag.attrs.items():
                    if k.startswith("data-"):
                        data_attrs.append({"tag": tag.name, "attr": k, "value": v})

            # 6) Scripts that might embed JSON (besides ld+json)
            inline_scripts = []
            for s in soup.find_all("script"):
                tp = s.get("type", "")
                if not tp or tp in ("text/javascript", "application/json"):
                    txt = s.get_text().strip()
                    if txt:
                        inline_scripts.append(txt[:200000])  # guard against huge blobs

            return {
                "visible_text": visible_text,
                "meta": meta,
                "ld_json": ld_json,
                "noscript_text": noscript_text,
                "canonical": urljoin(base_url, canonical) if canonical else None,
                "links": hrefs,
                "images": images,
                "tables_html": tables_html,
                "data_attrs": data_attrs,
                "inline_scripts": inline_scripts
            }

        # --- Step 1: Preprocess HTML into plain text ---
        def html_to_text(html: str) -> str:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)

        # --- Step 2: Index content using LlamaIndex ---
        # scraper/agent_llm.py

        @staticmethod
        def create_index_and_query_from_url(html: str, instruction: str, model: str = "llama3:8b-instruct-q5_k_m") -> dict[str, str]:
            # Get the logger instance from the class method
            worker_logger_instance = WorkerLogger()
            worker_logger = worker_logger_instance.setup_worker_logger()
            try:
                # Step 1: Convert HTML to clean plain text
                plain_text = Scrapper_agent.html_to_text(html)
                blob = Scrapper_agent.fetch_page("https://www.luxauto.lu/en/car/porsche/911.html?tri=prix_asc")

                # Step 2: Configure Ollama LLM
                load_dotenv()
                os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
                os.environ["LLAMA_CLOUD_API_KEY"] = os.getenv("GOOGLE_API_KEY")

                if not os.environ["GOOGLE_API_KEY"]:
                    raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it using your previous code: os.environ[\"GOOGLE_API_KEY\"] = ..." )
                else:
                    worker_logger.info(f"Successfully loaded Google's API key.")

                if not os.environ["LLAMA_CLOUD_API_KEY"]:
                    raise ValueError("LLAMA_CLOUD_API_KEY environment variable not set. Please set it using your previous code: os.environ[\"LLAMA_CLOUD_API_KEY\"] = ...")
                else:
                    worker_logger.info("Successfully loaded Llama cloud's API key")

                ollama_base_url = "http://localhost:11434"
                # Settings.llm = Ollama(model=model, base_url=ollama_base_url, request_timeout=120.0  ) #if you want ollama
                Settings.llm = Gemini(model="models/gemini-1.5-flash") # The model name can be changed #if you want gemini


                # Step 3: Configure embedding model (nomic-embed-text via Ollama)
                # Settings.embed_model = OllamaEmbedding(
                #     model_name="nomic-embed-text",
                #     base_url=ollama_base_url
                # ) #if you want ollama
                Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001")



                # Step 4: Set up document chunking
                Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=20)

                # Step 5: Build Document and Index
                doc = Document(text=blob['content_bytes'])
                index = VectorStoreIndex.from_documents([doc])

                # Step 6: Query the index with the user instruction
                query_engine = index.as_query_engine()


                scraping_subject_prompt = (
                    f""" I have received the following user request: {instruction} for a web scraper.
                    Given this request, give me the subject for which we are looking for data.
                    ⚠️ Return ONLY a data subject, which is usually a single world or a phrase, 
                    **Do NOT** inc
                    lude any explanation, markdown, or commentary.
                    
                                        User request:
                    'I want to find information about the price of second-hand cars', 
                    
                    Your answer:
                    second hand cars
                    
                    
                    Example2:                    
                    User request:
                    'I want to find a list of movies together with their number of nominations, awards and best pictures', 
                    
                    Your answer:
                    movies
                    """
                )

                data_subject = query_engine.query(scraping_subject_prompt)

                data_categories_prompt = (
                    f"""I have received the following user request: {instruction} for a web scraper"
                    From this request extract the data categories that should be found associated with this data subject: {data_subject.response}.
                    ⚠️ Return ONLY a list and **Do NOT** include any explanation, markdown, or commentary.
                    Each item/bullet point should represent a specific data category request by the user.
                    
                    Example1:
                    User request:
                    'I want to find information about the price of second-hand cars', 
                    Data subject:
                    second-hand cars
                    
                    Your answer:
                    * Car make, model, version, year
                    * car Features/configurations
                    * car Expert price
                    * car Sold price (if available)
                    
                    
                    Example2:                    
                    User request:
                    'I want to find a list of movies together with their number of nominations, awards and best pictures', 
                    Data subject:
                    movies
                    
                    Your answer:
                    * Movie number of nominations 
                    * Movie number of awards for a movie
                    * Movie number of best pictures for a movie
                    """
                )
                data_categories = query_engine.query(data_categories_prompt)



                relevance_prompt = (
                    f"""
                    find all the relevant data related to {data_subject.response} 
                    on the following categories: {data_categories.response}
                    inside the source of information available.
                    do not skip extracting any relevant data."""  # You can truncate the HTML if needed
                )
                relevant_info = query_engine.query(relevance_prompt)

                table_prompt = (
                    f"""About this data subject:"{data_subject.response}", this data categories are requested: "{data_categories.response}"
                    And here is the relevant content from a web page:{relevant_info}".
                    Generate a structured table (in markdown format) where each column corresponds to a data category requested.
                    Each row of the table corresponds to a unique {data_subject.response}."""
                )
                structured_table = query_engine.query(table_prompt)

            except Exception as e:
                logging.error(f"LLM agent failed: {e}")
                return f"Error: {str(e)}"

            try:
                MarkdownReader.MarkDownToCsv(structured_table.response, data_subject.response)

                return {
                    "Data Subject": {data_subject.response},
                    "relevant data categories request": {data_categories.response},
                    "relevant_info": {relevant_info.response},
                    "structured_data": str(structured_table.response)
                }

            except Exception as e:
                logging.error(f"Fail to turn the Marked-down table into a standard CSV or JSON.")
                return f"Error: {str(e)}"



#----------------------------------------------------------------------------------------------------------------------------------------------


#----------------------------------------------------------------------------------------------------------------------------------------------



        @staticmethod
        def create_index_and_query_from_detail_dict(ad_html: list, instruction: str, model: str = "llama3:8b-instruct-q5_k_m") -> dict[str, str]:
            # Get the logger instance from the class method
            worker_logger_instance = WorkerLogger()
            worker_logger = worker_logger_instance.setup_worker_logger()
            try:
                load_dotenv()
                # Skip step 1: Convert HTML to clean plain text: the ad details are already extracted externally and available
                # plain_text = Scrapper_agent.html_to_text(ad_html)
                # blob = Scrapper_agent.fetch_page("https://www.luxauto.lu/en/car/porsche/911.html?tri=prix_asc")

                # Step 2: Configure the LLM
                if "llama" in model.lower():
                    os.environ["LLAMA_CLOUD_API_KEY"] = os.getenv("LLAMA_CLOUD_API_KEY")
                    if not os.environ["LLAMA_CLOUD_API_KEY"]:
                        raise ValueError("LLAMA_CLOUD_API_KEY environment variable not set. Please set it using your previous code: os.environ[\"LLAMA_CLOUD_API_KEY\"] = ...")
                    else:
                        worker_logger.info("Successfully loaded Llama cloud's API key")

                    ollama_base_url = "http://localhost:11434"
                    Settings.llm = Ollama(model=model, base_url=ollama_base_url, request_timeout=120.0  ) #if you want ollama
                    Settings.embed_model = OllamaEmbedding(
                        model_name="nomic-embed-text",
                        base_url=ollama_base_url)

                if "google" in model.lower():
                        os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
                        if not os.environ["GOOGLE_API_KEY"]:
                            raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it using your previous code: os.environ[\"GOOGLE_API_KEY\"] = ..." )
                        else:
                            worker_logger.info(f"Successfully loaded Google's API key.")

                        Settings.llm = Gemini(model="models/gemini-1.5-flash") # The model name can be changed #if you want gemini
                        # Step 3: Configure embedding model (nomic-embed-text via Ollama)
                        Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001")










            # Step 4: Set up document chunking
                Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=20)

                # Step 5: Build Document and Index
                # doc = Document(ad_html)
                index = VectorStoreIndex.from_documents(ad_html)

                # Step 6: Query the index with the user instruction
                query_engine = index.as_query_engine()


                scraping_subject_prompt = (
                    f""" I have received the following user request: {instruction} for a web scraper.
                    Given this request, give me the subject for which we are looking for data.
                    ⚠️ Return ONLY a data subject, which is usually a single world or a phrase, 
                    **Do NOT** inc
                    lude any explanation, markdown, or commentary.
                    
                                        User request:
                    'I want to find information about the price of second-hand cars', 
                    
                    Your answer:
                    second hand cars
                    
                    
                    Example2:                    
                    User request:
                    'I want to find a list of movies together with their number of nominations, awards and best pictures', 
                    
                    Your answer:
                    movies
                    """
                )

                data_subject = query_engine.query(scraping_subject_prompt)

                data_categories_prompt = (
                    f"""I have received the following user request: {instruction} for a web scraper"
                    From this request extract the data categories that should be found associated with this data subject: {data_subject.response}.
                    ⚠️ Return ONLY a list and **Do NOT** include any explanation, markdown, or commentary.
                    Each item/bullet point should represent a specific data category request by the user.
                    
                    Example1:
                    User request:
                    'I want to find information about the price of second-hand cars', 
                    Data subject:
                    second-hand cars
                    
                    Your answer:
                    * Car make, model, version, year
                    * car Features/configurations
                    * car Expert price
                    * car Sold price (if available)
                    
                    
                    Example2:                    
                    User request:
                    'I want to find a list of movies together with their number of nominations, awards and best pictures', 
                    Data subject:
                    movies
                    
                    Your answer:
                    * Movie number of nominations 
                    * Movie number of awards for a movie
                    * Movie number of best pictures for a movie
                    """
                )
                data_categories = query_engine.query(data_categories_prompt)



                relevance_prompt = (
                    f"""
                    find all the relevant data related to {data_subject.response} 
                    on the following categories: {data_categories.response}
                    inside the source of information available.
                    do not skip extracting any relevant data."""  # You can truncate the HTML if needed
                )
                relevant_info = query_engine.query(relevance_prompt)

                table_prompt = (
                    f"""About this data subject:"{data_subject.response}", this data categories are requested: "{data_categories.response}"
                    And here is the relevant content from a web page:{relevant_info}".
                    Generate a structured table (in markdown format) where each column corresponds to a data category requested.
                    Each row of the table corresponds to a unique {data_subject.response}."""
                )
                structured_table = query_engine.query(table_prompt)

            except Exception as e:
                logging.error(f"LLM agent failed: {e}")
                return f"Error: {str(e)}"

            try:
                MarkdownReader.MarkDownToCsv(structured_table.response, data_subject.response)

                return {
                    "Data Subject": {data_subject.response},
                    "relevant data categories request": {data_categories.response},
                    "relevant_info": {relevant_info.response},
                    "structured_data": str(structured_table.response)
                }

            except Exception as e:
                logging.error(f"Fail to turn the Marked-down table into a standard CSV or JSON.")
                return f"Error: {str(e)}"





#-----------------------------------------------------------------------------------------------------------------------------------------------


#------------------------------------------------------------------------------------------------------------------------------------------------



        # def create_index_and_query_async(html: str, instruction: str, model: str = "llama3:8b-instruct-q5_k_m") -> dict[str, str]:
        #     # Get the logger instance from the class method
        #     worker_logger_instance = WorkerLogger()
        #     worker_logger = worker_logger_instance.setup_worker_logger()
        #
        #     try:
        #         # Step 1: Convert HTML to clean plain text
        #         plain_text = Scrapper_agent.html_to_text(html)
        #
        #         # Step 2: Configure Ollama LLM
        #         os.environ["GOOGLE_API_KEY"] = os.getenv("GOOGLE_API_KEY")
        #         os.environ["LLAMA_CLOUD_API_KEY"] = os.getenv("GOOGLE_API_KEY")
        #
        #         if not os.environ["GOOGLE_API_KEY"]:
        #             raise ValueError("GOOGLE_API_KEY environment variable not set. Please set it using your previous code: os.environ[\"GOOGLE_API_KEY\"] = ..." )
        #         else:
        #             worker_logger.info(f"Successfully loaded Google's API key.")
        #
        #         if not os.environ["LLAMA_CLOUD_API_KEY"]:
        #             raise ValueError("LLAMA_CLOUD_API_KEY environment variable not set. Please set it using your previous code: os.environ[\"LLAMA_CLOUD_API_KEY\"] = ...")
        #         else:
        #             worker_logger.info("Successfully loaded Llama cloud's API key")
        #
        #         ollama_base_url = "http://localhost:11434"
        #         # Settings.llm = Ollama(model=model, base_url=ollama_base_url, request_timeout=120.0  ) #if you want ollama
        #         Settings.llm = Gemini(model="models/gemini-1.5-flash") # The model name can be changed #if you want gemini
        #
        #
        #         # Step 3: Configure embedding model (nomic-embed-text via Ollama)
        #         # Settings.embed_model = OllamaEmbedding(
        #         #     model_name="nomic-embed-text",
        #         #     base_url=ollama_base_url
        #         # ) #if you want ollama
        #         Settings.embed_model = GeminiEmbedding(model_name="models/embedding-001")
        #
        #
        #
        #         # Step 4: Set up document chunking
        #         Settings.node_parser = SentenceSplitter(chunk_size=1024, chunk_overlap=20)
        #
        #         # Step 5: Build Document and Index
        #         doc = Document(text=plain_text)
        #         index = VectorStoreIndex.from_documents([doc])
        #
        #         # Step 6: Query the index with the user instruction
        #         query_engine = index.as_query_engine()
        #
        #
        #         scraping_subject_prompt = (
        #             f""" I have received the following user request: {instruction} for a web scraper.
        #             Given this request, give me the subject for which we are looking for data.
        #             ⚠️ Return ONLY a data subject, which is usually a single world or a phrase,
        #             **Do NOT** inc
        #             lude any explanation, markdown, or commentary.
        #
        #                                 User request:
        #             'I want to find information about the price of second-hand cars',
        #
        #             Your answer:
        #             second hand cars
        #
        #
        #             Example2:
        #             User request:
        #             'I want to find a list of movies together with their number of nominations, awards and best pictures',
        #
        #             Your answer:
        #             movies
        #             """
        #         )
        #
        #         data_subject = query_engine.query(scraping_subject_prompt)
        #
        #         data_categories_prompt = (
        #             f"""I have received the following user request: {instruction} for a web scraper"
        #             From this request extract the data categories that should be found associated with this data subject: {data_subject.response}.
        #             ⚠️ Return ONLY a list and **Do NOT** include any explanation, markdown, or commentary.
        #             Each item/bullet point should represent a specific data category request by the user.
        #
        #             Example1:
        #             User request:
        #             'I want to find information about the price of second-hand cars',
        #             Data subject:
        #             second-hand cars
        #
        #             Your answer:
        #             * Car make, model, version, year
        #             * car Features/configurations
        #             * car Expert price
        #             * car Sold price (if available)
        #
        #
        #             Example2:
        #             User request:
        #             'I want to find a list of movies together with their number of nominations, awards and best pictures',
        #             Data subject:
        #             movies
        #
        #             Your answer:
        #             * Movie number of nominations
        #             * Movie number of awards for a movie
        #             * Movie number of best pictures for a movie
        #             """
        #         )
        #         data_categories = query_engine.query(data_categories_prompt)
        #
        #
        #
        #         relevance_prompt = (
        #             f"""
        #             find all the relevant data related to {data_subject.response}
        #             on the following categories: {data_categories.response}
        #             inside the source of information available.
        #             do not skip extracting any relevant data."""  # You can truncate the HTML if needed
        #         )
        #         relevant_info = query_engine.query(relevance_prompt)
        #
        #         table_prompt = (
        #             f"""About this data subject:"{data_subject.response}", this data categories are requested: "{data_categories.response}"
        #             And here is the relevant content from a web page:{relevant_info}".
        #             Generate a structured table (in markdown format) where each column corresponds to a data category requested.
        #             Each row of the table corresponds to a unique {data_subject.response}."""
        #         )
        #         structured_table = query_engine.query(table_prompt)
        #
        #     except Exception as e:
        #         logging.error(f"LLM agent failed: {e}")
        #         return f"Error: {str(e)}"
        #
        #     try:
        #         MarkdownReader.MarkDownToCsv(structured_table.response, data_subject.response)
        #
        #         return {
        #             "Data Subject": {data_subject.response},
        #             "relevant data categories request": {data_categories.response},
        #             "relevant_info": {relevant_info.response},
        #             "structured_data": str(structured_table.response)
        #         }
        #
        #     except Exception as e:
        #         logging.error(f"Fail to turn the Marked-down table into a standard CSV or JSON.")
        #         return f"Error: {str(e)}"




        # # --- Wrapper agent call ---
        # def run_llm_agent(html: str, instruction: str) -> str:
        #     try:
        #         plain_text = html_to_text(html)
        #         index = create_index(plain_text)
        #         result = query_with_instruction(index, instruction)
        #         return result
        #     except Exception as e:
        #         logging.error(f"LLM agent failed: {e}")
        #         return f"Error: {str(e)}"



