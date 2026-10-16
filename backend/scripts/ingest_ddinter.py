"""
Ingests real drug-drug interaction data from DDInter 2.0, a free,
open-access, pharmacist-curated interaction database covering 2,310 drugs
and 302,516 interaction records with severity, mechanism, and management
annotations -- this is the actual answer to "15 hand-written interaction
rules doesn't scale": stop hand-authoring, ingest a real curated dataset.

Source: DDInter 2.0 (Tian et al., 2025, Nucleic Acids Research)
  https://ddinter2.scbdd.com/  (browse online)
  https://ddinter.scbdd.com/download/  (bulk CSV download)
License: CC BY-NC-SA 4.0 (non-commercial use, share-alike, attribution
required) -- fine for an academic/exhibition project; a commercial
deployment would need a different licensed source (e.g. a DrugBank or
First Databank commercial license) instead.

---- Why this script can't just be run for you ----
This project's build environment has no internet access to
ddinter2.scbdd.com (or any non-package-registry domain), so the actual
CSV could not be downloaded and ingested here. What IS verified:
  - The ingestion/mapping logic below, tested against a synthetic CSV
    shaped like DDInter's documented columns (drug pair, severity level,
    interaction description) -- see tests/test_ddinter_ingest.py.
  - The output schema exactly matches data/interactions.json, so the
    Cross-Check Agent picks up ingested data with zero code changes
    (see src/agents/cross_check_agent.py, which now loads both files).

---- What you need to do ----
1. Download the DDI CSV from https://ddinter.scbdd.com/download/
   (their download page lists several CSVs by drug category -- grab the
   ones covering your drug vocabulary, or all of them for full coverage).
2. Run:
       python scripts/ingest_ddinter.py path/to/ddinter_export.csv
   This writes data/interactions_ddinter.json.
3. Restart the backend -- src/agents/cross_check_agent.py automatically
   merges this file in alongside the curated data/interactions.json if
   it exists.

If your downloaded CSV's column headers don't match what this script
expects, it will print the headers it found and exit without guessing --
adjust COLUMN_ALIASES below to match (this is deliberately defensive
rather than silently mis-mapping columns, since a wrong drug-pair mapping
here is a patient-safety bug, not a cosmetic one).
"""

import csv
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import DATA_DIR

OUTPUT_FILE = DATA_DIR / "interactions_ddinter.json"

# Column name variants seen across different DDInter export formats.
# All matching is case-insensitive and whitespace-trimmed.
COLUMN_ALIASES = {
    "drug_a": ["drug_a", "druga", "drug1", "drug a", "drugname1"],
    "drug_b": ["drug_b", "drugb", "drug2", "drug b", "drugname2"],
    "severity": ["level", "risk level", "severity", "risk_level"],
    "description": ["description", "mechanism", "interaction description", "detail"],
    "management": ["management", "strategy", "management strategy", "recommendation"],
}

SEVERITY_MAP = {
    "major": "high", "severe": "high", "high": "high",
    "moderate": "medium", "medium": "medium",
    "minor": "low", "mild": "low", "low": "low",
}


def _normalize_headers(fieldnames):
    return {name.strip().lower(): name for name in fieldnames}


def _find_column(normalized_headers, aliases):
    for alias in aliases:
        if alias in normalized_headers:
            return normalized_headers[alias]
    return None


def ingest(csv_path: str, known_drugs: list = None) -> list:
    """Reads a DDInter-format CSV and returns a list of drug_drug interaction
    rules in the same shape as data/interactions.json.

    If known_drugs is given, only pairs where BOTH drugs are in that list
    are kept -- use this to scope ingestion to your existing drug
    vocabulary rather than pulling in all 300k+ records. Pass None to
    ingest everything in the file (only recommended for a pre-filtered
    export, given the full dataset's size).
    """
    known_set = {d.lower() for d in known_drugs} if known_drugs else None

    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        normalized = _normalize_headers(reader.fieldnames)

        col_a = _find_column(normalized, COLUMN_ALIASES["drug_a"])
        col_b = _find_column(normalized, COLUMN_ALIASES["drug_b"])
        col_severity = _find_column(normalized, COLUMN_ALIASES["severity"])
        col_description = _find_column(normalized, COLUMN_ALIASES["description"])
        col_management = _find_column(normalized, COLUMN_ALIASES["management"])

        if not col_a or not col_b:
            print(f"ERROR: could not find drug-pair columns in this CSV.")
            print(f"Headers found: {reader.fieldnames}")
            print(f"Expected one of {COLUMN_ALIASES['drug_a']} and one of {COLUMN_ALIASES['drug_b']}.")
            print("Adjust COLUMN_ALIASES in this script to match, then re-run.")
            sys.exit(1)

        rules = []
        skipped_unknown_severity = 0
        for row in reader:
            drug_a = row.get(col_a, "").strip().lower()
            drug_b = row.get(col_b, "").strip().lower()
            if not drug_a or not drug_b:
                continue
            if known_set and (drug_a not in known_set or drug_b not in known_set):
                continue

            raw_severity = (row.get(col_severity, "") or "").strip().lower() if col_severity else ""
            severity = SEVERITY_MAP.get(raw_severity)
            if severity is None:
                skipped_unknown_severity += 1
                continue  # don't guess a severity for a patient-safety field

            description = (row.get(col_description, "") or "").strip() if col_description else ""
            management = (row.get(col_management, "") or "").strip() if col_management else ""

            rules.append({
                "drugs": [drug_a, drug_b],
                "severity": severity,
                "effect": description or "See DDInter 2.0 for full interaction details.",
                "guideline_source": "DDInter 2.0 (ddinter2.scbdd.com)",
                "recommendation": management or "Consult full prescribing information before co-administering.",
            })

    if skipped_unknown_severity:
        print(f"Note: skipped {skipped_unknown_severity} row(s) with an unrecognized severity value "
              f"(add it to SEVERITY_MAP if it should be included).")

    return rules


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/ingest_ddinter.py path/to/ddinter_export.csv")
        sys.exit(1)

    from src.config import KNOWN_DRUGS

    csv_path = sys.argv[1]
    rules = ingest(csv_path, known_drugs=KNOWN_DRUGS)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump({"drug_drug": rules}, f, indent=2)

    print(f"Ingested {len(rules)} interaction rule(s) covering the current drug vocabulary -> {OUTPUT_FILE}")
    print("Restart the backend to pick these up (cross_check_agent.py merges this file in automatically).")
