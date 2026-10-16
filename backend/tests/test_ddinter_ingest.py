"""
Tests for scripts/ingest_ddinter.py, against a synthetic CSV shaped like
DDInter 2.0's documented export format (drug pair, risk level, mechanism
description). The real DDInter CSV could not be downloaded and tested
against directly -- this build environment has no internet access to
ddinter2.scbdd.com -- so this confirms the mapping/filtering LOGIC is
correct, not the exact real-world column names (see the script's
docstring for what to check once you have the real file).
"""
import csv
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.ingest_ddinter import ingest


def _write_csv(rows, fieldnames):
    f = tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False, newline="", encoding="utf-8")
    writer = csv.DictWriter(f, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(rows)
    f.close()
    return f.name


def test_ingests_known_column_format():
    path = _write_csv(
        [
            {"Drug_A": "Warfarin", "Drug_B": "Aspirin", "Level": "Major",
             "Description": "Increased bleeding risk.", "Management": "Avoid combination."},
            {"Drug_A": "Metformin", "Drug_B": "Contrast Dye", "Level": "Moderate",
             "Description": "Risk of lactic acidosis.", "Management": "Hold before procedure."},
        ],
        fieldnames=["Drug_A", "Drug_B", "Level", "Description", "Management"],
    )
    rules = ingest(path, known_drugs=None)
    assert len(rules) == 2
    assert rules[0]["drugs"] == ["warfarin", "aspirin"]
    assert rules[0]["severity"] == "high"  # Major -> high
    assert rules[1]["severity"] == "medium"  # Moderate -> medium
    assert "DDInter 2.0" in rules[0]["guideline_source"]
    print("PASS: ingests a known DDInter-style column format correctly")


def test_filters_to_known_drug_vocabulary():
    path = _write_csv(
        [
            {"Drug_A": "Warfarin", "Drug_B": "Aspirin", "Level": "Major", "Description": "", "Management": ""},
            {"Drug_A": "SomeObscureDrug", "Drug_B": "AnotherObscureDrug", "Level": "Minor", "Description": "", "Management": ""},
        ],
        fieldnames=["Drug_A", "Drug_B", "Level", "Description", "Management"],
    )
    rules = ingest(path, known_drugs=["warfarin", "aspirin", "metformin"])
    assert len(rules) == 1, f"Expected only the Warfarin/Aspirin row to survive filtering, got {rules}"
    print("PASS: filters out pairs where a drug isn't in the known vocabulary")


def test_skips_rows_with_unrecognized_severity():
    path = _write_csv(
        [
            {"Drug_A": "Warfarin", "Drug_B": "Aspirin", "Level": "Major", "Description": "", "Management": ""},
            {"Drug_A": "DrugX", "Drug_B": "DrugY", "Level": "???", "Description": "", "Management": ""},
        ],
        fieldnames=["Drug_A", "Drug_B", "Level", "Description", "Management"],
    )
    rules = ingest(path, known_drugs=None)
    assert len(rules) == 1, "Expected the row with an unrecognized severity to be skipped, not guessed"
    print("PASS: rows with an unrecognized severity value are skipped rather than guessed")


def test_missing_optional_columns_dont_crash():
    path = _write_csv(
        [{"Drug_A": "Warfarin", "Drug_B": "Aspirin", "Level": "Major"}],
        fieldnames=["Drug_A", "Drug_B", "Level"],  # no Description/Management columns at all
    )
    rules = ingest(path, known_drugs=None)
    assert len(rules) == 1
    assert "DDInter" in rules[0]["effect"]  # falls back to a generic pointer, doesn't crash
    print("PASS: a CSV missing the optional description/management columns doesn't crash")


if __name__ == "__main__":
    test_ingests_known_column_format()
    test_filters_to_known_drug_vocabulary()
    test_skips_rows_with_unrecognized_severity()
    test_missing_optional_columns_dont_crash()
    print("\nAll DDInter ingestion tests passed (against a synthetic CSV, not the real download).")
