"""
Tests for src/live_data.py.

By default these run against MOCKED HTTP responses, shaped like the real
openFDA / PubMed E-utilities response schemas (confirmed against official
FDA/NCBI documentation) -- this sandbox's network can't reach
api.fda.gov or eutils.ncbi.nlm.nih.gov to test against the live APIs.

To actually verify against the live APIs yourself (recommended before
relying on this in a demo), run:
    python tests/test_live_data.py --live
This skips the mocks and hits the real endpoints for a couple of known
drugs, printing what comes back so you can eyeball it.
"""

import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.live_data import fetch_fda_label_chunks, search_pubmed_literature

# A response shaped exactly like a real openFDA /drug/label.json result
# (field names and nesting confirmed against open.fda.gov's official docs).
FAKE_FDA_RESPONSE = {
    "meta": {"results": {"skip": 0, "limit": 1, "total": 1}},
    "results": [
        {
            "effective_time": "20230415",
            "openfda": {
                "brand_name": ["Glucophage"],
                "generic_name": ["METFORMIN HYDROCHLORIDE"],
                "product_type": ["HUMAN PRESCRIPTION DRUG"],
            },
            "indications_and_usage": ["Metformin is indicated as an adjunct to diet and exercise..."],
            "dosage_and_administration": ["Initial dose is 500 mg orally twice a day..."],
            "warnings": ["Lactic acidosis is a rare but serious metabolic complication..."],
            "drug_interactions": ["Concomitant use with carbonic anhydrase inhibitors..."],
        }
    ],
}

FAKE_FDA_EMPTY_RESPONSE = {"meta": {"results": {"skip": 0, "limit": 1, "total": 0}}, "results": []}

FAKE_PUBMED_ESEARCH_RESPONSE = {"esearchresult": {"idlist": ["12345678", "87654321"]}}

FAKE_PUBMED_ESUMMARY_RESPONSE = {
    "result": {
        "12345678": {"title": "Warfarin and NSAID co-prescription: a bleeding risk review"},
        "87654321": {"title": "Case series of INR destabilization with concurrent ibuprofen use"},
    }
}


def _mock_response(json_data, status_ok=True):
    mock = MagicMock()
    mock.json.return_value = json_data
    mock.raise_for_status = MagicMock() if status_ok else MagicMock(side_effect=Exception("HTTP error"))
    return mock


def test_fda_label_chunks_parsed_correctly():
    with patch("src.live_data.requests.get", return_value=_mock_response(FAKE_FDA_RESPONSE)):
        chunks = fetch_fda_label_chunks("metformin")

    assert len(chunks) > 0, "Expected at least one chunk from a matched FDA label"
    assert all(c["source"] == "FDA Structured Product Label (live, via openFDA)" for c in chunks)
    assert any("Glucophage" in c["title"] for c in chunks)
    assert any("Lactic acidosis" in c["text"] for c in chunks)
    print("PASS: openFDA label response is correctly parsed into citable chunks")


def test_fda_label_falls_back_when_prescription_only_query_is_empty():
    # First call (with product_type filter) returns nothing; second call
    # (without the filter) finds a match -- confirms the fallback fires.
    responses = [_mock_response(FAKE_FDA_EMPTY_RESPONSE), _mock_response(FAKE_FDA_RESPONSE)]
    with patch("src.live_data.requests.get", side_effect=responses):
        chunks = fetch_fda_label_chunks("metformin")
    assert len(chunks) > 0, "Expected the unfiltered fallback query to find a match"
    print("PASS: falls back to an unfiltered query when the prescription-only query finds nothing")


def test_fda_label_no_match_returns_empty():
    with patch("src.live_data.requests.get", return_value=_mock_response(FAKE_FDA_EMPTY_RESPONSE)):
        chunks = fetch_fda_label_chunks("not_a_real_drug_xyz")
    assert chunks == [], "Expected no chunks when openFDA has no matching label (both attempts empty)"
    print("PASS: no matching FDA label in either attempt returns an empty list, not an error")


def test_fda_label_network_failure_returns_empty():
    import requests

    with patch("src.live_data.requests.get", side_effect=requests.RequestException("network down")):
        chunks = fetch_fda_label_chunks("metformin")
    assert chunks == [], "Expected graceful empty list on network failure"
    print("PASS: network failure returns an empty list instead of raising")


def test_pubmed_search_parsed_correctly():
    responses = [_mock_response(FAKE_PUBMED_ESEARCH_RESPONSE), _mock_response(FAKE_PUBMED_ESUMMARY_RESPONSE)]
    with patch("src.live_data.requests.get", side_effect=responses):
        articles = search_pubmed_literature("warfarin ibuprofen interaction")

    assert len(articles) == 2
    assert articles[0]["pmid"] == "12345678"
    assert articles[0]["url"] == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
    assert "bleeding risk" in articles[0]["title"]
    print("PASS: PubMed esearch + esummary responses are correctly combined into article references")


def test_pubmed_no_results_returns_empty():
    with patch("src.live_data.requests.get", return_value=_mock_response({"esearchresult": {"idlist": []}})):
        articles = search_pubmed_literature("a query with no matches")
    assert articles == []
    print("PASS: no PubMed results returns an empty list, not an error")


def run_live_smoke_test():
    """Optional: hits the REAL APIs. Run with --live and real internet access."""
    print("Running LIVE smoke test against real APIs (requires internet)...\n")

    chunks = fetch_fda_label_chunks("metformin")
    print(f"openFDA metformin -> {len(chunks)} chunk(s)")
    for c in chunks:
        print(f"  - {c['title']} (v{c['version']})")
        print(f"    {c['text'][:150]}...")

    print()
    articles = search_pubmed_literature("warfarin ibuprofen bleeding risk")
    print(f"PubMed search -> {len(articles)} article(s)")
    for a in articles:
        print(f"  - {a['title']} ({a['url']})")


if __name__ == "__main__":
    if "--live" in sys.argv:
        run_live_smoke_test()
    else:
        test_fda_label_chunks_parsed_correctly()
        test_fda_label_falls_back_when_prescription_only_query_is_empty()
        test_fda_label_no_match_returns_empty()
        test_fda_label_network_failure_returns_empty()
        test_pubmed_search_parsed_correctly()
        test_pubmed_no_results_returns_empty()
        print("\nAll live_data tests passed (against mocked responses).")
