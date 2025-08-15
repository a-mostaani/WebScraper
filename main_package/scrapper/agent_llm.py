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
from main_package.scrapper.utils import MarkdownReader
from llama_index.core.node_parser import SentenceSplitter
import asyncio



class Scrapper_agent:

        # --- Step 1: Preprocess HTML into plain text ---
        def html_to_text(html: str) -> str:
            soup = BeautifulSoup(html, "html.parser")
            return soup.get_text(separator="\n", strip=True)

        # --- Step 2: Index content using LlamaIndex ---
        # scraper/agent_llm.py

        @staticmethod
        def create_index_and_query(html: str, instruction: str, model: str = "llama3:8b-instruct-q5_k_m") -> dict[str, str]:
            try:
                # Step 1: Convert HTML to clean plain text
                plain_text = Scrapper_agent.html_to_text(html)

                # Step 2: Configure Ollama LLM
                os.environ["GOOGLE_API_KEY"] = "AIzaSyC2HAclDxNQAzKJEBJ8k8dk40JyQuZKCJs"
                os.environ["LLAMA_CLOUD_API_KEY"] = "llx-Nic4YSakCGZoTdKChJm9XGC6bKDXlggyE6liSgfiC8yXclHk"
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
                doc = Document(text=plain_text)
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






        def create_index_and_query_async(html: str, instruction: str, model: str = "llama3:8b-instruct-q5_k_m") -> dict[str, str]:
            try:
                # Step 1: Convert HTML to clean plain text
                plain_text = Scrapper_agent.html_to_text(html)

                # Step 2: Configure Ollama LLM
                os.environ["GOOGLE_API_KEY"] = "AIzaSyC2HAclDxNQAzKJEBJ8k8dk40JyQuZKCJs"
                os.environ["LLAMA_CLOUD_API_KEY"] = "llx-Nic4YSakCGZoTdKChJm9XGC6bKDXlggyE6liSgfiC8yXclHk"
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
                doc = Document(text=plain_text)
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




        # --- Wrapper agent call ---
        def run_llm_agent(html: str, instruction: str) -> str:
            try:
                plain_text = html_to_text(html)
                index = create_index(plain_text)
                result = query_with_instruction(index, instruction)
                return result
            except Exception as e:
                logging.error(f"LLM agent failed: {e}")
                return f"Error: {str(e)}"



