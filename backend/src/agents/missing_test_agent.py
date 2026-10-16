"""
Missing-Test Detector Agent.

Checks each prescribed drug against a monitoring-requirement table
(data/monitoring_requirements.json) and flags any required baseline or
periodic test that the clinician has not indicated as already ordered.
"""

import json
import re
from typing import Dict, Any, List

from src.config import MONITORING_FILE
from src.state import VerifierState

with open(MONITORING_FILE, encoding="utf-8") as f:
    _MONITORING = json.load(f)


def _normalize_test_name(name: str) -> str:
    return " ".join(re.findall(r"[a-z0-9]+", name.lower()))


_PANEL_SEPARATOR = re.compile(r",|&|\+|/|;|\band\b|\n", re.IGNORECASE)
_PARENTHETICAL = re.compile(r"\(([^)]*)\)")
_SPECIMEN_PREFIXES = {"blood", "plasma", "serum"}


def _normalized_test_terms(name: str) -> set[str]:
    normalized = _normalize_test_name(name)
    words = normalized.split()
    terms = {normalized} if normalized else set()
    if words and words[0] in _SPECIMEN_PREFIXES:
        terms.add(" ".join(words[1:]))
    return terms


def _ordered_test_terms(ordered_tests: List[str]) -> set[str]:
    """Normalize individual test names, including explicit panel members."""
    terms = set()
    for test in ordered_tests:
        name = str(test)
        parenthetical_terms = _PARENTHETICAL.findall(name)
        terms.update(
            normalized_term
            for group in parenthetical_terms
            for term in _PANEL_SEPARATOR.split(group)
            for normalized_term in _normalized_test_terms(term)
        )
        name_without_parentheticals = _PARENTHETICAL.sub(" ", name)
        terms.update(
            normalized_term
            for term in _PANEL_SEPARATOR.split(name_without_parentheticals)
            for normalized_term in _normalized_test_terms(term)
        )
    return terms


def _ordered_component_ids(
    component_groups: List[List[str]],
    ordered_tests: List[str],
) -> set[str]:
    """Map observed exact aliases to canonical required-component IDs."""
    observed_terms = _ordered_test_terms(ordered_tests)
    return {
        _normalize_test_name(aliases[0])
        for aliases in component_groups
        if any(
            any(
                alias_term in observed_terms
                for alias_term in _normalized_test_terms(alias)
            )
            for alias in aliases
        )
    }


def detect_missing_tests(state: VerifierState) -> Dict[str, Any]:
    """LangGraph node: flags required tests not present in ordered_tests."""
    drug_names = [d["name"] for d in state.get("parsed_drugs", [])]
    ordered_tests = state.get("ordered_tests", [])

    missing = []
    for drug in drug_names:
        for requirement in _MONITORING.get(drug, []):
            required_components = requirement.get("required_components")
            if not required_components:
                required_components = [[requirement["test"]]]
            required_component_ids = {
                _normalize_test_name(aliases[0])
                for aliases in required_components
            }
            ordered_component_ids = _ordered_component_ids(
                required_components,
                ordered_tests,
            )
            missing_component_ids = required_component_ids - ordered_component_ids
            missing_components = [
                aliases[0].title()
                for aliases in required_components
                if _normalize_test_name(aliases[0]) in missing_component_ids
            ]
            if missing_components:
                finding = {"drug": drug, **requirement}
                if len(required_components) > 1:
                    finding["missing_components"] = missing_components
                missing.append(finding)

    return {"missing_tests": missing}
