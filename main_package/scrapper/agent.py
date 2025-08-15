from bs4 import BeautifulSoup

def extract_data(html: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    return {
        "title": soup.title.string if soup.title else "N/A",
        "meta_description": soup.find("meta", attrs={"name": "description"})["content"]
        if soup.find("meta", attrs={"name": "description"}) else "N/A",
        # Add more logic for price, author, etc.
    }