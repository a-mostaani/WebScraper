# luxauto_pipeline.py
# End-to-end: crawl -> archive HTML -> LlamaIndex Documents -> HTMLNodeParser -> LLM-ready chunks (JSONL)

import os, re, time, json, base64, hashlib
from typing import Dict, List, Iterable, Tuple
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

import main_package.scrapper.agent_llm
from main_package.scrapper.agent_llm import Scrapper_agent
from main_package.scrapper.utils import LLMInteractions, ArrayGenerators

# --- LlamaIndex imports (v0.10+) ---
try:
    from llama_index.core import Document
    from llama_index.core.node_parser import HTMLNodeParser
    from llama_index.core.schema import MetadataMode
except Exception:
    # fallback for older versions
    from llama_index.legacy import Document
    from llama_index.legacy.node_parser import HTMLNodeParser
    from llama_index.legacy.schema import MetadataMode


# =========================
# Fetch + link extraction
# =========================

def fetch_page(url, session=None, timeout=30):
    """Return dict with raw HTML bytes and HTTP metadata."""
    s = session or requests.Session()
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                      "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Accept-Language": "en,en-GB;q=0.9,fr;q=0.8,de;q=0.7",
    }
    r = s.get(url, headers=headers, timeout=timeout)
    r.raise_for_status()
    return {
        "url": r.url,
        "status": r.status_code,
        "headers": dict(r.headers),
        "fetched_at": int(time.time()),
        "content_bytes": r.content,
        "encoding": r.encoding or "utf-8",
    }


# Match /usedcar/<slug>.html?id=123456 with optional "/en/" prefix
AD_HREF_PAT = re.compile(r'/([a-z]{2}/)?usedcar/[^"]+?\.html\?id=\d+', re.I)

def extract_listing_links(html_bytes: bytes, base_url: str) -> List[str]:
    """Find ad-detail links on a listing page (robust to nesting/labels)."""
    soup = BeautifulSoup(html_bytes, "lxml")
    links = set()
    for a in soup.select('a[href]'):
        href = a.get('href', '')
        if AD_HREF_PAT.search(href):
            links.add(urljoin(base_url, href))

    if not links:  # fallback regex over raw HTML
        html_txt = html_bytes.decode("utf-8", "ignore")
        for m in AD_HREF_PAT.finditer(html_txt):
            links.add(urljoin(base_url, m.group(0)))

    return sorted(links)


# =========================
# Crawl & collect ad pages
# =========================

def crawl_one_model_collect(
        start_url: str,
        max_pages: int = 1,
        max_ads_per_page: int = 30,
        delay_sec: float = 0.8,
        return_bytes_b64: bool = False,
        jsonl_path: str | None = None,
        archive_dir: str | None = None,
) -> Dict[str, dict]:
    """
    Crawl listing pagination, fetch ad detail pages, and return:
      { ad_url: { html | html_bytes_b64, encoding, headers, fetched_at } }

    Also (optional) append each ad as a JSON line and/or archive raw HTML to disk.
    """
    session = requests.Session()
    data_map: Dict[str, dict] = {}

    if archive_dir:
        os.makedirs(archive_dir, exist_ok=True)

    def write_jsonl(rec: dict):
        if jsonl_path:
            with open(jsonl_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")

    for page in range(1, max_pages + 1):
        # ensure page param
        if "page=" in start_url:
            listing_url = start_url
        else:
            sep = "&" if "?" in start_url else "?"
            listing_url = f"{start_url}{sep}page={page}"

        listing_blob = fetch_page(listing_url, session=session)
        ad_links = extract_listing_links(listing_blob["content_bytes"], listing_blob["url"])
        if not ad_links:
            print(f"[page {page}] no ad links found at {listing_url}")
            continue

        for ad_url in ad_links[:max_ads_per_page]:
            time.sleep(delay_sec)
            ad_blob = fetch_page(ad_url, session=session)

            if archive_dir:
                # Persist raw HTML for reproducibility
                fname = hashlib.md5(ad_blob["url"].encode()).hexdigest() + ".html"
                with open(os.path.join(archive_dir, fname), "wb") as f:
                    f.write(ad_blob["content_bytes"])

            if return_bytes_b64:
                rec = {
                    "ad_url": ad_blob["url"],
                    "html_bytes_b64": base64.b64encode(ad_blob["content_bytes"]).decode("ascii"),
                    "encoding": ad_blob["encoding"],
                    "headers": ad_blob["headers"],
                    "fetched_at": ad_blob["fetched_at"],
                }
            else:
                html_text = ad_blob["content_bytes"].decode(ad_blob["encoding"], errors="replace")
                rec = {
                    "ad_url": ad_blob["url"],
                    "html": html_text,
                    "encoding": ad_blob["encoding"],
                    "headers": ad_blob["headers"],
                    "fetched_at": ad_blob["fetched_at"],
                }

            data_map[rec["ad_url"]] = rec
            write_jsonl(rec)
            print(f"collected: {rec['ad_url']}")

    return data_map


# =========================
# LlamaIndex ingestion
# =========================

def data_map_to_documents(data_map: Dict[str, dict]) -> List[Document]:
    """Turn the collected dict into LlamaIndex Documents with page-level metadata."""
    docs: List[Document] = []
    for url, rec in data_map.items():
        if "html" in rec:
            html_text = rec["html"]
        elif "html_bytes_b64" in rec:
            enc = rec.get("encoding", "utf-8")
            html_text = base64.b64decode(rec["html_bytes_b64"]).decode(enc, errors="replace")
        else:
            continue

        docs.append(
            Document(
                id_=url,                      # stable id per ad
                text=html_text,               # raw HTML for HTMLNodeParser
                metadata={
                    "source": "luxauto",
                    "url": url,
                    "encoding": rec.get("encoding", "utf-8"),
                    "fetched_at": rec.get("fetched_at"),
                },
            )
        )
    return docs


def build_nodes_from_documents(docs: List[Document]):
    """
    Parse HTML into semantically split Nodes. The tag set keeps headings, paragraphs,
    list items, and table cells (useful for classifieds).
    """
    parser = HTMLNodeParser(tags=["h1", "h2", "h3", "p", "li", "td", "th", "section", "article", "dl", "dt", "dd"])
    nodes = parser.get_nodes_from_documents(docs)
    return nodes


def group_nodes_by_url(nodes) -> Dict[str, list]:
    """Group parsed nodes by their source URL for per-ad processing."""
    by_url: Dict[str, list] = {}
    for n in nodes:
        url = None
        # metadata is usually copied onto nodes; if not, grab from ref doc
        if n.metadata and "url" in n.metadata:
            url = n.metadata["url"]
        elif getattr(n, "ref_doc", None) and n.ref_doc.metadata and "url" in n.ref_doc.metadata:
            url = n.ref_doc.metadata["url"]
        if not url:
            # skip nodes that somehow lost their URL
            continue
        by_url.setdefault(url, []).append(n)
    return by_url


# =========================
# Chunking for your LLM
# =========================

def chunk_text(s: str, max_chars: int) -> List[str]:
    """Simple, safe character-based chunking with boundary on whitespace when possible."""
    if len(s) <= max_chars:
        return [s]
    chunks, i, n = [], 0, len(s)
    while i < n:
        j = min(i + max_chars, n)
        # try to break on whitespace for nicer chunks
        if j < n:
            k = s.rfind(" ", i, j)
            if k != -1 and k > i + max_chars * 0.6:  # don't cut too early
                j = k
        chunks.append(s[i:j].strip())
        i = j
    return [c for c in chunks if c]


def make_agent_jobs(
        by_url: Dict[str, list],
        max_chars_per_chunk: int = 12000,
        include_page_metadata: bool = True,
) -> List[dict]:
    """
    Build LLM-ready work items:
      [{ "url", "chunk_index", "text", "metadata" }]
    """
    jobs: List[dict] = []
    for url, nlist in by_url.items():
        # Join node text (no node-level metadata in content)
        page_text = "\n\n".join(n.get_content(metadata_mode=MetadataMode.NONE) for n in nlist).strip()
        # Keep page metadata (from first node)
        page_meta = nlist[0].metadata if (include_page_metadata and nlist) else {}

        for idx, chunk in enumerate(chunk_text(page_text, max_chars_per_chunk)):
            jobs.append({
                "url": url,
                "chunk_index": idx,
                "text": chunk,
                "metadata": page_meta,
            })
    return jobs


def write_jsonl(items: Iterable[dict], path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        for it in items:
            f.write(json.dumps(it, ensure_ascii=False) + "\n")


# =========================
# Putting it all together
# =========================

if __name__ == "__main__":
    # 1) pick any brand/model listing URL (English here)
    START_URL = "https://www.luxauto.lu/en/car/porsche/911.html?tri=prix_asc"

    # 2) crawl & collect ad pages (HTML only; no parsing)
    data_map = crawl_one_model_collect(
        start_url=START_URL,
        max_pages=1,                 # increase to walk pagination
        max_ads_per_page=2,         # cap per page
        delay_sec=0.9,               # be polite
        return_bytes_b64=False,      # text is fine for LlamaIndex
        jsonl_path="out/raw_ads.jsonl",     # optional: stream sink of raw pages
        archive_dir="out/html_archive"      # optional: store raw HTML files
    )
    print(f"\nCollected {len(data_map)} ad pages.")

    # 3) convert to LlamaIndex Documents
    docs = data_map_to_documents(data_map)

    # 4) parse HTML -> Nodes
    nodes = build_nodes_from_documents(docs)
    print(f"Parsed into {len(nodes)} nodes.")

    # 5) group nodes per ad URL
    by_url = group_nodes_by_url(nodes)
    print(f"Grouped into {len(by_url)} ads.")

    # 6) build LLM-ready jobs (chunked text + metadata)
    jobs = make_agent_jobs(
        by_url,
        max_chars_per_chunk=12000,   # tune to your local model context + RAM
        include_page_metadata=True
    )
    print(f"Prepared {len(jobs)} LLM jobs (chunks).")

    # 7) write jobs to JSONL — feed this to your scraper agent
    write_jsonl(jobs, "out/llm_jobs.jsonl")
    print("Wrote LLM jobs to out/llm_jobs.jsonl")


    relevant_data = ArrayGenerators.create_dict_with_empty_lists(len(by_url.keys()), list(by_url.keys()))

    instruction = ("I want a list of all the cars, their models, and prices on the following page. Only give answer "
                   "if you found some relevant information. Return no answer if there were no relevant information there."
                   "Do NOT include any explanation, markdown, or commentary.")

    # structured_data = Scrapper_agent.create_index_and_query_from_detail_dict(docs, instruction, model='llama3')
    for job in jobs:
        relevant_data[job['url']].append(LLMInteractions.get_llama3_response_non_streaming(instruction + job['text'], model_name="llama3"))
        print(f"Processed {len(relevant_data[job['url']])} llm job related to the url: {job['url']}.")

    print(relevant_data)

