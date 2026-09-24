"""
LangGraph orchestration for the Hospital Treatment Protocol Verifier.

Pipeline order: parse -> retrieve -> cross_check -> missing_test -> explain

(Note: the parser runs before the retriever so the retrieval query can be
built from the parsed drug names + diagnosis, which gives much better
retrieval than querying on the raw prescription text. The self-correction
re-query loop lives inside the Retriever Agent itself -- see
src/agents/retriever_agent.py -- rather than as a separate graph edge, to
keep the graph structure simple to read.)
"""

from langgraph.graph import StateGraph, END

from src.state import VerifierState
from src.agents.llm_parser_agent import get_parser
from src.agents.retriever_agent import retrieve_protocol
from src.agents.cross_check_agent import cross_check
from src.agents.missing_test_agent import detect_missing_tests
from src.agents.explanation_agent import explain_violations


def build_graph():
    graph = StateGraph(VerifierState)

    graph.add_node("parse", get_parser())
    graph.add_node("retrieve", retrieve_protocol)
    graph.add_node("cross_check", cross_check)
    graph.add_node("missing_test", detect_missing_tests)
    graph.add_node("explain", explain_violations)

    graph.set_entry_point("parse")
    graph.add_edge("parse", "retrieve")
    graph.add_edge("retrieve", "cross_check")
    graph.add_edge("cross_check", "missing_test")
    graph.add_edge("missing_test", "explain")
    graph.add_edge("explain", END)

    return graph.compile()


_compiled_graph = None


def get_graph():
    global _compiled_graph
    if _compiled_graph is None:
        _compiled_graph = build_graph()
    return _compiled_graph


def run_pipeline(raw_text: str, diagnosis_hint: str = "", ordered_tests=None) -> dict:
    """Convenience entry point used by the Streamlit app and tests."""
    graph = get_graph()
    initial_state: VerifierState = {
        "raw_text": raw_text,
        "diagnosis_hint": diagnosis_hint or None,
        "ordered_tests": ordered_tests or [],
    }
    return graph.invoke(initial_state)
