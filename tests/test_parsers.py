from __future__ import annotations

import io

import pdfplumber
import pytest

from collect_refunding_data import (
    _parse_matrix_recommended_pages,
    categorize_security,
    parse_maturity,
    parse_recommended_pdf,
)


@pytest.mark.parametrize(
    "label,expected_value,expected_unit",
    [
        ("2-Year Note", 2.0, "YEARS"),
        ("13 Week Bill", 13.0, "WEEKS"),
        ("30 day cash management bill", 30.0, "DAYS"),
        ("6-Month Bill", 6.0, "MONTHS"),
    ],
)
def test_parse_maturity_extracts_value_and_units(label: str, expected_value: float, expected_unit: str) -> None:
    value, unit = parse_maturity(label)
    assert value == pytest.approx(expected_value)
    assert unit == expected_unit


def test_parse_maturity_handles_missing_value() -> None:
    value, unit = parse_maturity("Cash Management Bill")
    assert value is None
    assert unit == ""


@pytest.mark.parametrize(
    "label,expected",
    [
        ("2-Year Note", "NOTE"),
        ("Floating Rate Note (FRN)", "FRN"),
        ("10-Year TIPS", "TIPS"),
        ("13 Week Bill", "BILL"),
        ("20-Year Bond", "BOND"),
        ("30-Year Treasury", "OTHER"),
    ],
)
def test_categorize_security_maps_known_labels(label: str, expected: str) -> None:
    assert categorize_security(label) == expected


@pytest.mark.parametrize("label", ["Q3 2025", "Q2 2025"])
def test_parse_recommended_pdf_extracts_matrix_data(
    label: str,
    recommended_pdf_loader,
) -> None:
    pdf_bytes = recommended_pdf_loader(label)
    entries = parse_recommended_pdf(pdf_bytes, int(label.split()[0][1:]), int(label.split()[1]), "2025-01-01")
    assert entries, "Expected entries to be parsed from matrix style PDF"
    assert all(entry["Data_type"] == "RECOMMENDATION_FOR_THIS_REFUNDING" for entry in entries)
    assert {entry["Security_type"] for entry in entries} >= {"NOTE", "BOND", "FRN", "TIPS"}


@pytest.mark.parametrize(
    "label",
    ["Q3 2025", "Q2 2025"],
)
def test_parse_matrix_recommended_pages_matches_pdf_tables(
    label: str,
    recommended_pdf_loader,
):
    pdf_bytes = recommended_pdf_loader(label)
    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        entries = _parse_matrix_recommended_pages(
            pdf.pages,
            quarter_label=label,
            announcement_date="2025-01-01",
        )
    assert entries, "Matrix parser should extract entries from provided fixture"
    assert all(entry["Quarter_year"] == label for entry in entries)
    assert all(entry["Units"] == "YEARS" for entry in entries)

