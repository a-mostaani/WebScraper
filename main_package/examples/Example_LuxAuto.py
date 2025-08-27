import time
import csv
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from main_package.scrapper.agent_llm import Scrapper_agent
from main_package.scrapper.utils import WebPageReader

# --- from earlier ---
# fetch_page(html) you already have from the previous snippet
# extract_listing_links(html, base_url) and extract_price_from_detail(html) are the two functions you referenced

# If you put those functions in a module (e.g., parsers.py), import them:
# from parsers import fetch_page, extract_listing_links, extract_price_from_detail

# For this inline example, I’ll assume they’re already defined in your file.


def crawl_one_model(start_url: str, max_pages: int = 1, max_ads_per_page: int = 10, delay_sec: float = 0.7):
    """
    Use the two helpers to:
      - collect ad links from listing pages
      - open each ad detail page
      - extract price

    Returns: list of dict rows
    """
    session = requests.Session()
    rows = []

    for page in range(1, max_pages + 1):
        # Add/replace ?page= when needed
        if "page=" in start_url:
            listing_url = start_url
        else:
            sep = "&" if "?" in start_url else "?"
            listing_url = f"{start_url}{sep}page={page}"

        blob = Scrapper_agent.fetch_page(listing_url, session=session)
        html = blob["content_bytes"]
        base_url = blob["url"]

        # Uncomment this once to inspect what the page actually contains:
        WebPageReader.debug_anchor_sample(html, base_url)

        ad_links = WebPageReader.extract_listing_links(html, base_url)
        if not ad_links:
            print(f"[page {page}] no ad links found at {listing_url}")
            continue

        # limit per page if you like
        for ad_url in ad_links[:max_ads_per_page]:
            time.sleep(delay_sec)  # be polite
            ad_blob = Scrapper_agent.fetch_page(ad_url, session=session)
            ad_html = ad_blob["content_bytes"]

            price_text, price_eur = WebPageReader.extract_price_from_detail(ad_html)

            # grab a simple title too
            soup = BeautifulSoup(ad_html, "html.parser")
            title = soup.title.get_text(strip=True) if soup.title else ""

            rows.append({
                "ad_url": ad_blob["url"],
                "title": title,
                "price_text": price_text,  # e.g., "33.999 €"
                "price_eur": price_eur,    # e.g., 33999 (int) or None
                "fetched_at": ad_blob["fetched_at"]
            })

            print(f"OK  {price_text or 'NO PRICE':>12}  {ad_blob['url']}")

    return rows


if __name__ == "__main__":
    # Example: Porsche 911 (English listing). You can change to any model page you like.
    start = "https://www.luxauto.lu/en/car/porsche/911.html?tri=prix_asc"

    rows = crawl_one_model(
        start_url=start,
        max_pages=3,          # bump to 2+ to paginate
        max_ads_per_page=10,   # adjust as needed
        delay_sec=0.8
    )

    # Save to CSV (optional)
    out_csv = "luxauto_sample_prices.csv"
    with open(out_csv, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["ad_url", "title", "price_text", "price_eur", "fetched_at"])
        w.writeheader()
        w.writerows(rows)

    print(f"\nSaved {len(rows)} rows to {out_csv}")
