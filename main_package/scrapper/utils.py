# Clean up the data rows by stripping whitespace from each cell
import io

from llama_index.readers.file import MarkdownReader
import csv
import re
import pandas as pd
import logging


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

