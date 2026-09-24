"""
Live external data sources, as an alternative/supplement to the hand-written
local protocol corpus.

Two sources, chosen deliberately over a live PubMed-only approach:

  - openFDA Drug Label API (api.fda.gov) -- returns REAL, structured FDA
    prescribing-information text (warnings, drug interactions, dosing,
    indications) for a given drug. This is the right fit for "guideline
    retrieval with a citation", because it's an actual regulatory label,
    not a research abstract.

  - PubMed (NCBI E-utilities) -- returns research article titles/PMIDs
    related to a drug/diagnosis. This is positioned as SUPPORTING
    LITERATURE, not a guideline citation -- an abstract is evidence, not
    a clinical directive, and the pipeline never treats it as one.

Both functions degrade gracefully: on any network error, timeout, rate
limit, or "drug not found", they return an empty list rather than raising,
so a live-data failure never breaks the pipeline -- it just means the
Retriever Agent falls back to (or stays with) the local corpus.

NOTE ON TESTING: this sandbox's network is restricted to package
registries and cannot reach api.fda.gov or eutils.ncbi.nlm.nih.gov, so
these functions are verified in tests/test_live_data.py against MOCKED
HTTP responses shaped like the real APIs' documented schemas (confirmed
via official FDA/NCBI documentation), not against a live call. Run
tests/test_live_data.py --live yourself with real internet access to
confirm the live calls work exactly as expected before relying on them.
"""

import requests

FDA_LABEL_ENDPOINT = "https://api.fda.gov/drug/label.json"
PUBMED_ESEARCH_ENDPOINT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
PUBMED_ESUMMARY_ENDPOINT = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"

REQUEST_TIMEOUT_SECONDS = 6

# Label sections worth surfacing as citable "chunks", in priority order.
FDA_LABEL_SECTIONS = [
    ("boxed_warning", "Boxed Warning"),
    ("indications_and_usage", "Indications and Usage"),
    ("dosage_and_administration", "Dosage and Administration"),
    ("drug_interactions", "Drug Interactions"),
    ("warnings", "Warnings"),
    ("warnings_and_cautions", "Warnings and Cautions"),
]


def _query_fda(drug_name: str, require_prescription_type: bool):
    """One query attempt. Builds the search string with real spaces (not
    literal '+' characters) and lets `requests` handle URL-encoding --
    passing literal '+' through params= double-encodes it as %2B, which
    openFDA's search engine can't parse as the boolean operator it's meant
    to be. This was the bug behind the original 0-results issue."""
    query = f'openfda.generic_name:"{drug_name}"'
    if require_prescription_type:
        query += ' AND openfda.product_type:"HUMAN PRESCRIPTION DRUG"'
    response = requests.get(
        FDA_LABEL_ENDPOINT,
        params={"search": query, "limit": 1},
        timeout=REQUEST_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    return response.json().get("results") or []


def fetch_fda_label_chunks(drug_name: str, max_sections: int = 4) -> list:
    """
    Queries the openFDA drug label API for a generic drug name and returns
    a list of chunks in the SAME shape as the local corpus
    (src/vector_store.py's chunks: text, title, source, version, specialty)
    so they can be merged directly into retrieved_chunks with no frontend
    changes needed.

    Tries a prescription-drug-only match first (to avoid OTC/homeopathic
    noise); if that returns nothing -- some legitimately prescribed
    generics aren't tagged exactly "HUMAN PRESCRIPTION DRUG" in every
    record -- retries without that filter before giving up.

    Returns [] on any failure (drug not found, network error, timeout,
    rate limit) -- callers should treat that as "no live result",
    not an error.
    """
    try:
        results = _query_fda(drug_name, require_prescription_type=True)
        if not results:
            results = _query_fda(drug_name, require_prescription_type=False)
    except (requests.RequestException, ValueError):
        return []

    if not results:
        return []

    label = results[0]
    brand = ", ".join(label.get("openfda", {}).get("brand_name", [])) or drug_name.title()
    effective_time = label.get("effective_time", "unknown")
    version = f"{effective_time[:4]}-{effective_time[4:6]}-{effective_time[6:8]}" if len(effective_time) == 8 else effective_time

    chunks = []
    for field, section_title in FDA_LABEL_SECTIONS:
        if len(chunks) >= max_sections:
            break
        section_text = label.get(field)
        if not section_text:
            continue
        text = " ".join(section_text) if isinstance(section_text, list) else str(section_text)
        chunks.append({
            "text": text.strip(),
            "title": f"{brand} — {section_title} (FDA Label)",
            "source": "FDA Structured Product Label (live, via openFDA)",
            "version": version,
            "specialty": "FDA Regulatory Labeling",
            "score": 1.0,  # a matched live label is treated as a direct hit, not ranked
        })
    return chunks


def search_pubmed_literature(query: str, max_results: int = 3) -> list:
    """
    Searches PubMed for articles matching `query` (e.g. "warfarin ibuprofen
    interaction") and returns a short list of {title, pmid, url} -- SUPPORTING
    LITERATURE references, not guideline citations. Returns [] on any
    failure.
    """
    try:
        search_resp = requests.get(
            PUBMED_ESEARCH_ENDPOINT,
            params={"db": "pubmed", "term": query, "retmax": max_results, "retmode": "json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        search_resp.raise_for_status()
        pmids = search_resp.json().get("esearchresult", {}).get("idlist", [])
        if not pmids:
            return []

        summary_resp = requests.get(
            PUBMED_ESUMMARY_ENDPOINT,
            params={"db": "pubmed", "id": ",".join(pmids), "retmode": "json"},
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        summary_resp.raise_for_status()
        summary_data = summary_resp.json().get("result", {})
    except (requests.RequestException, ValueError):
        return []

    articles = []
    for pmid in pmids:
        record = summary_data.get(pmid)
        if not record:
            continue
        articles.append({
            "title": record.get("title", "Untitled"),
            "pmid": pmid,
            "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
        })
    return articles
