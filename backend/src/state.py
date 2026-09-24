"""
Shared state object passed between agents in the LangGraph pipeline.

Using a single TypedDict as shared state (rather than each agent returning an
ad-hoc object) is the standard LangGraph pattern: every node reads what it
needs from the state and returns a partial update that gets merged in.
"""

from typing import TypedDict, List, Dict, Any, Optional


class VerifierState(TypedDict, total=False):
    # ---- input ----
    raw_text: str
    diagnosis_hint: Optional[str]        # optional structured diagnosis override
    ordered_tests: List[str]             # tests the clinician says are already ordered

    # ---- Prescription Parser Agent output ----
    parsed_drugs: List[Dict[str, Any]]   # [{name, dose, route, frequency}]
    parsed_diagnosis: Optional[str]

    # ---- Retriever Agent output ----
    retrieval_query: str
    retrieved_chunks: List[Dict[str, Any]]  # [{text, source, version, specialty, score}]
    retrieval_confidence: float
    retrieval_attempts: int

    # ---- Cross-Check Agent output ----
    drug_drug_flags: List[Dict[str, Any]]
    drug_diagnosis_flags: List[Dict[str, Any]]

    # ---- Missing-Test Detector Agent output ----
    missing_tests: List[Dict[str, Any]]

    # ---- Violation + Explanation Agent output ----
    violations: List[Dict[str, Any]]
    explanation_report: str
