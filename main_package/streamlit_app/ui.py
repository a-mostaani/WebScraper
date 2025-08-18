import streamlit as st
from main_package.scrapper.parallel_handler import scrape_urls_parallel
import pandas as pd
from main_package.scrapper.utils import MarkdownReader
import inspect, sys, importlib
import io

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
    url_input = st.text_area("Enter URLs (one per line)")
    uploaded_file = st.file_uploader("Or upload a file with URLs")

    urls = []
    if uploaded_file:
        urls = uploaded_file.read().decode().splitlines()
    elif url_input:
        urls = url_input.strip().splitlines()

    # Use session state to manage scraped data and current page
    if 'final_df' not in st.session_state:
        st.session_state.final_df = None
    if 'current_page' not in st.session_state:
        st.session_state.current_page = 0
    if 'downloads' not in st.session_state:
        st.session_state.downloads = (None, None)

    if st.button("Start Scraping") and urls and user_instruction:
        # Clear previous state
        st.session_state.final_df = None
        st.session_state.current_page = 0
        st.session_state.downloads = (None, None)

        with st.spinner("Scraping in progress..."):
            scraped_results = scrape_urls_parallel(urls, user_instruction)

            # --- START OF CHANGE ---
            # Call your external function and correctly unpack the return values
            # The returned final_df is a local variable here.
            local_final_df, downloads = MarkdownReader.MarkDownToDigitalCsv(scraped_results)

            # Check the type of the returned dataFrame variable and convert if necessary
            if isinstance(local_final_df, pd.DataFrame):
                st.session_state.final_df = local_final_df
            elif isinstance(local_final_df, bytes):
                try:
                    # Assume the bytes object is CSV data and convert it to a DataFrame
                    df_from_bytes = pd.read_csv(io.StringIO(local_final_df.decode('utf-8')))
                    st.session_state.final_df = df_from_bytes
                    st.warning("The data received was not a DataFrame and has been converted.")
                except Exception as e:
                    st.error(f"Could not convert data to DataFrame: {e}")
                    st.session_state.final_df = None
            else:
                st.error("Unexpected data format received.")
                st.session_state.final_df = None

            st.session_state.downloads = downloads
            # --- END OF CHANGE ---

    # Check if a DataFrame is available to display by checking the session state directly
    if st.session_state.final_df is not None:
        st.success("Scraping complete!")

        # We now access the DataFrame directly from the session state for all calculations.
        total_rows = len(st.session_state.final_df)
        rows_per_page = 10
        total_pages = (total_rows - 1) // rows_per_page + 1

        start_index = st.session_state.current_page * rows_per_page
        end_index = start_index + rows_per_page

        # The paginated DataFrame is created from the session state DataFrame.
        paginated_df = st.session_state.final_df.iloc[start_index:end_index]

        st.markdown(f"**Showing results {start_index + 1} to {min(end_index, total_rows)} of {total_rows}**")
        st.dataframe(paginated_df, use_container_width=True)

        # Pagination buttons
        col1, col2, _ = st.columns([1, 1, 6])
        if col1.button("Previous Page", disabled=(st.session_state.current_page == 0)):
            st.session_state.current_page -= 1
            st.rerun()

        if col2.button("Next Page", disabled=(st.session_state.current_page >= total_pages - 1)):
            st.session_state.current_page += 1
            st.rerun()

        # Download buttons
        csv_data, json_data = st.session_state.downloads
        if csv_data is not None:
            st.download_button(
                "Download CSV",
                csv_data,
                "results.csv",
                "text/csv"
            )
        if json_data is not None:
            st.download_button(
                "Download JSON",
                json_data,
                "results.json",
                "application/json"
            )