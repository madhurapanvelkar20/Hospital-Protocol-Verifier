"""
Violation + Explanation Agent.

Synthesizes the Cross-Check Agent's and Missing-Test Detector Agent's
findings against the retrieved guideline chunks, and produces a
clinician-readable report. Every flagged issue carries a
(excerpt, source, version, confidence) citation tuple rather than a bare
verdict, per the project's traceability-first design goal.

Two modes:
  - Template mode (default): assembles the report deterministically, no
    API key required. This is what runs in the demo.
  - LLM mode (optional): if an ANTHROPIC_API_KEY is set, uses it to turn the
    same structured findings into a more natural-language narrative. The
    structured findings -- not the LLM -- remain the source of truth for
    what counts as a violation, so a bad LLM call can only change the
    wording, not the underlying flags.
"""

import os
from typing import Dict, Any, List

from src.state import VerifierState


def _build_violations(state: VerifierState) -> List[Dict[str, Any]]:
    violations = []

    for flag in state.get("drug_drug_flags", []):
        violations.append({
            "type": "drug-drug interaction",
            "severity": flag["severity"],
            "description": f"{flag['drugs'][0].title()} + {flag['drugs'][1].title()}: {flag['effect']}",
            "recommendation": flag["recommendation"],
            "source": flag["guideline_source"],
        })

    for flag in state.get("drug_diagnosis_flags", []):
        violations.append({
            "type": "drug-diagnosis contraindication",
            "severity": flag["severity"],
            "description": f"{flag['drug'].title()} in patient with {flag['diagnosis']}: {flag['effect']}",
            "recommendation": flag["recommendation"],
            "source": flag["guideline_source"],
        })

    for missing in state.get("missing_tests", []):
        violations.append({
            "type": "missing monitoring test",
            "severity": "medium",
            "description": (
                f"{missing['drug'].title()} requires {missing['test']} "
                f"({missing['frequency']}), which has not been ordered."
            ),
            "recommendation": missing["rationale"],
            "source": missing["guideline_source"],
        })

    return violations


def _citation_block(state: VerifierState) -> str:
    chunks = state.get("retrieved_chunks", [])
    if not chunks:
        return "No matching protocol passage was retrieved with sufficient confidence."
    lines = []
    for chunk in chunks:
        lines.append(
            f"- \u201c{chunk['text'][:220].strip()}...\u201d\n"
            f"  (Source: {chunk['source']}, v{chunk['version']}, confidence: {chunk['score']:.2f})"
        )
    return "\n".join(lines)


def _template_report(state: VerifierState, violations: List[Dict[str, Any]]) -> str:
    lines = []
    confidence = state.get("retrieval_confidence", 0.0)
    attempts = state.get("retrieval_attempts", 1)

    lines.append("## Retrieved Protocol Reference")
    if attempts > 1:
        lines.append("(Query was reformulated once by the Retriever Agent's self-correction loop.)")
    lines.append(_citation_block(state))
    lines.append("")

    if not violations:
        lines.append("## Result: No violations detected")
        lines.append("The prescription appears consistent with the retrieved protocol, "
                      "no flagged drug interactions, and no missing required monitoring tests.")
        return "\n".join(lines)

    lines.append(f"## Result: {len(violations)} issue(s) flagged")
    for i, v in enumerate(violations, 1):
        lines.append(
            f"\n**{i}. [{v['severity'].upper()}] {v['type'].title()}**\n"
            f"- Finding: {v['description']}\n"
            f"- Recommendation: {v['recommendation']}\n"
            f"- Guideline source: {v['source']}"
        )
    return "\n".join(lines)


def _llm_report(state: VerifierState, violations: List[Dict[str, Any]]) -> str:
    """Optional: rephrase the same structured findings via Claude, if an API
    key is configured. Falls back to the template report on any error."""
    try:
        import anthropic

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env
        findings_text = "\n".join(
            f"- [{v['severity']}] {v['type']}: {v['description']} "
            f"(recommendation: {v['recommendation']}, source: {v['source']})"
            for v in violations
        ) or "No issues were flagged."

        prompt = (
            "You are a clinical decision support assistant. Rewrite the following "
            "structured findings as a short, clear report for a physician. Do not "
            "invent any findings beyond what is listed -- only rephrase them for "
            "clarity, and keep every guideline source citation.\n\n"
            f"Findings:\n{findings_text}"
        )
        response = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=600,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception:
        return _template_report(state, violations)


def explain_violations(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: produces the final violations list and report text."""
    violations = _build_violations(state)

    if os.environ.get("ANTHROPIC_API_KEY"):
        report = _llm_report(state, violations)
    else:
        report = _template_report(state, violations)

    return {
        "violations": violations,
        "explanation_report": report,
    }
