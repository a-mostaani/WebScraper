# Clean up the data rows by stripping whitespace from each cell
import io

from llama_index.readers.file import MarkdownReader
import csv
import re
import pandas as pd
import logging
import streamlit as st


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

    @staticmethod
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

    @staticmethod
    def MarkDownToDigitalCsv(scraped_results):
        # Initialize parsed_dfs list to store dataframes from each URL
        parsed_dfs = []

        # Loop through each scraped result to process it
        for result in scraped_results:
            # Check if there is data and no 'Error' string in it
            if result.get('data') and "Error" not in result['data']:
                try:
                    # Access the markdown content from the 'relevant_info' key
                    markdown_data_string = list(result['data']['relevant_info'])[0]
                    # Convert the string to a file-like object for pandas
                    markdown_data_io = io.StringIO(markdown_data_string)

                    # Read the markdown table as a CSV, skipping header formatting line
                    df_page = pd.read_csv(markdown_data_io, sep='|', header=0, skiprows=[1], engine='python')

                    # Clean up the DataFrame
                    df_page = df_page.dropna(axis=1, how='all')
                    df_page.columns = [col.strip() for col in df_page.columns]
                    # Apply string stripping to all object columns
                    df_page = df_page.apply(lambda x: x.str.strip() if x.dtype == "object" else x)
                    df_page['Source URL'] = result['url']
                    parsed_dfs.append(df_page)

                except Exception as e:
                    # Log parsing errors but don't stop the process
                    logging.error(f"Could not parse data from {result['url']}: {e}")

            # Handle scraping errors
            elif result.get('error'):
                logging.error(f"Failed to scrape {result['url']}: {result['error']}")

        # Now, handle the final aggregation and return
        if parsed_dfs:
            final_df = pd.concat(parsed_dfs, ignore_index=True)

            # Prepare CSV and JSON data from the final DataFrame
            csv_data = final_df.to_csv(index=False).encode('utf-8')
            json_data = final_df.to_json(orient='records', indent=4).encode('utf-8')

            # Return the DataFrame and the tuple of download data
            return final_df, (csv_data, json_data)
        else:
            # If no data was scraped, return None for the DataFrame and for the downloads
            logging.warning("No data was successfully scraped and parsed.")
            return None, (None, None)



    @staticmethod
    def process_scraped_data(scraped_results):
        """
        Parses markdown from scraped results, creates a DataFrame, and prepares
        CSV and JSON data for download.
        Returns the DataFrame and a tuple of (csv_data, json_data).
        """
        parsed_dfs = []
        for result in scraped_results:
            if result.get('data') and "Error" not in result['data']:
                try:
                    markdown_text = list(result['data']['relevant_info'])[0]
                    markdown_data = io.StringIO(markdown_text)

                    df_page = pd.read_csv(markdown_data, sep='|', header=0, skiprows=[1], engine='python')
                    df_page = df_page.dropna(axis=1, how='all')
                    df_page.columns = [col.strip() for col in df_page.columns]
                    for col in df_page.select_dtypes(include=['object']).columns:
                        df_page[col] = df_page[col].str.strip()
                    df_page['Source URL'] = result['url']
                    parsed_dfs.append(df_page)
                except Exception as e:
                    st.error(f"Could not parse data from {result['url']}: {e}")
            elif result.get('error'):
                st.error(f"Failed to scrape {result['url']}: {result['error']}")
        if parsed_dfs:
            final_df = pd.concat(parsed_dfs, ignore_index=True)
            csv_data = final_df.to_csv(index=False).encode('utf-8')
            json_data = final_df.to_json(orient='records', indent=4).encode('utf-8')
            return final_df, (csv_data, json_data)
        else:
            st.warning("No data was successfully scraped.")
            return None, (None, None)

