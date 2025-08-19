import streamlit as st
from main_package.scrapper.parallel_handler import scrape_urls_parallel
import pandas as pd
from main_package.scrapper.utils import MarkdownReader

def run_app():
    st.title("Agentic Web Scraper")

    # Text area for user to provide the instructions for scraping
    st.markdown("#### Step 1: Provide Instructions")
    user_instruction = st.text_input(
    "Enter your scraping instruction:",
    "Extract a markdown table of books, their titles, and prices."
    )

    # Input methods for URLs
    st.markdown("#### Step 2: Provide URLs")
    url_input = st.text_area("Enter URLs (one per line without quotations "" or other decorators)",
                             value="""https://www.example.com/page1
                            https://www.example.com/page2
                            https://www.example.com/page3""")
    uploaded_file = st.file_uploader("Or upload a .txt file with URLs - following same rules as in urls input")

    urls = []
    if uploaded_file:
        urls = uploaded_file.read().decode().splitlines()
    elif url_input:
        urls = url_input.strip().splitlines()
        # urls = url_input

    if st.button("Start Scraping") and urls and user_instruction:
        with st.spinner("Scraping in progress..."):
            scraped_results = scrape_urls_parallel(urls, user_instruction)
            # df = pd.DataFrame(data)
            # st.success("Scraping complete!")
            # st.dataframe(df)

            csv, json = MarkdownReader.MarkDownToDigitalCsv(scraped_results)

            # csv = df.to_csv(index=False)
            st.download_button("Download CSV", csv, "results.csv")

            # json = df.to_json(orient="records")
            st.download_button("Download JSON", json, "results.json")
