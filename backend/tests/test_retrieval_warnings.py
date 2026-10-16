from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.agents import retriever_agent


class _Retriever:
    def query(self, _query, top_k=None):
        return [{"text": "local result", "source": "local", "version": "1", "score": 0.5}]


def _run_with_live_status(monkeypatch, status):
    monkeypatch.setattr(retriever_agent, "LIVE_FDA_RETRIEVAL_ENABLED", True)
    monkeypatch.setattr(retriever_agent, "get_retriever", lambda: _Retriever())
    monkeypatch.setattr(
        retriever_agent,
        "fetch_fda_label_chunks_with_status",
        lambda _drug: ([], status),
    )
    return retriever_agent.retrieve_protocol({
        "parsed_drugs": [{"name": "apixaban"}],
        "parsed_diagnoses": [],
    })


def test_temporary_external_data_failure_is_not_an_unsupported_drug_result(monkeypatch):
    result = _run_with_live_status(monkeypatch, "unavailable")

    assert result["retrieval_warnings"][0]["type"] == "external_data_unavailable"
    assert result["retrieval_warnings"][0]["drug"] == "apixaban"
    assert "temporary external-data failure" in result["retrieval_warnings"][0]["message"]


def test_successful_external_lookup_without_a_match_has_a_distinct_warning(monkeypatch):
    result = _run_with_live_status(monkeypatch, "no_match")

    assert result["retrieval_warnings"][0]["type"] == "external_data_no_match"
    assert "does not establish" in result["retrieval_warnings"][0]["message"]


def test_unprescribed_drug_specific_guideline_is_filtered_from_results(monkeypatch):
    monkeypatch.setattr(retriever_agent, "LIVE_FDA_RETRIEVAL_ENABLED", False)

    class RankedRetriever:
        def query(self, _query, top_k=None):
            return [
                {
                    "title": "Amlodipine (Calcium Channel Blocker) Therapy Guideline",
                    "source": "Amlodipine protocol",
                    "score": 0.99,
                },
                {
                    "title": "Hypertension Management Guideline",
                    "source": "Hypertension protocol",
                    "score": 0.91,
                },
                {
                    "title": "Atorvastatin Therapy for Lipid Management Guideline",
                    "source": "Atorvastatin protocol",
                    "score": 0.82,
                },
                {
                    "title": "Statin Therapy for Lipid Management Guideline",
                    "source": "Statin protocol",
                    "score": 0.74,
                },
            ]

    monkeypatch.setattr(retriever_agent, "get_retriever", lambda: RankedRetriever())
    result = retriever_agent.retrieve_protocol({
        "parsed_drugs": [
            {"name": "apixaban", "recognition_status": "unsupported"},
            {"name": "lisinopril", "recognition_status": "recognized"},
            {"name": "atorvastatin", "recognition_status": "recognized"},
            {"name": "pantoprazole", "recognition_status": "unsupported"},
        ],
        "parsed_diagnoses": ["hypertension"],
    })

    assert "apixaban" not in result["retrieval_query"]
    assert "pantoprazole" not in result["retrieval_query"]
    titles = [chunk["title"] for chunk in result["retrieved_chunks"]]
    assert titles == [
        "Hypertension Management Guideline",
        "Atorvastatin Therapy for Lipid Management Guideline",
        "Statin Therapy for Lipid Management Guideline",
    ]
    assert result["retrieval_confidence"] == 0.91
