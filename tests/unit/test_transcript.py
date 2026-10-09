import hashlib
import subprocess
from decimal import Decimal

import pytest

from peppi_mcp.adapters.lapland_transcript import parse_pages, parse_pdf
from peppi_mcp.errors import PeppiError
from peppi_mcp.pdf_extract import extract_pages
from peppi_mcp.services.achievements import credit_summary
from tests.transcript_fixtures import pages, pdf_bytes, row


def parse(text=None):
    return parse_pages(text or pages(), source_sha256="a" * 64, study_right_id="test-right")


def test_selectable_pdf_extraction_and_reconciliation():
    source = pdf_bytes()
    snapshot = parse_pdf(source, study_right_id="test-right")
    summary = credit_summary(snapshot, "test-right")
    assert summary.total_credits == Decimal("3.5") and summary.difference_from_source_total == 0
    assert len(snapshot.achievements) == 3 and len(snapshot.source_groups) == 2
    first = snapshot.achievements[0]
    assert first.title == "Invented title with ä and ö continued fictional title"
    assert first.credits == Decimal("0.5") and first.grade == "HYV" and first.grading_scale == "HYV/HYL"
    assert first.provenance.source_page == 2 and first.provenance.source_line > 1
    assert first.provenance.source_sha256 == hashlib.sha256(source).hexdigest()
    assert first.provenance.source_issued_on.isoformat() == "2026-03-01"
    assert snapshot.achievements[-1].provenance.source_page == 3
    assert snapshot.achievements[-1].id in snapshot.source_groups[0].component_ids
    assert snapshot.achievements[-1].id not in snapshot.source_groups[1].component_ids
    assert all(dec.disposition == "excluded" for dec in summary.decisions if dec.achievement_id.startswith("g:"))
    assert len(summary.source_groups) == 2
    assert "INVENTED PERSON" not in snapshot.model_dump_json()
    assert "INVENTED ID" not in snapshot.model_dump_json()
    assert "INVENTED ASSESSOR" not in snapshot.model_dump_json()


@pytest.mark.parametrize("field,expected", [("date", "partial"), ("grade", "unresolved"), ("credits", "unresolved")])
def test_missing_fields_are_not_filled_in(field, expected):
    text = pages()
    values = dict(amount="2", grade="3", date="3.2.2026")
    values[{"credits": "amount", "grade": "grade", "date": "date"}[field]] = None
    text[2] = text[2].replace(row("TEST003V1 Invented third course", "2", "3", "3.2.2026"), row("TEST003V1 Invented third course", **values))
    snapshot = parse(text)
    summary = credit_summary(snapshot, "test-right")
    assert summary.status == expected and summary.total_credits is None
    record = snapshot.achievements[-1]
    assert record.provenance.completeness == "partial"
    assert getattr(record, "completed_on" if field == "date" else field) is None
    if field == "grade":
        assert record.status == "unknown"


def test_repeated_code_does_not_infer_correction_or_additional_credit():
    text = pages()
    text[2] = text[2].replace("TEST003V1", "TEST001V1")
    summary = credit_summary(parse(text), "test-right")
    assert summary.status == "unresolved" and summary.total_credits is None
    assert any("Multiple completions" in decision.reason for decision in summary.decisions)


@pytest.mark.parametrize("grade", ["HYL", "0"])
def test_failed_attempt_is_preserved_but_excluded(grade):
    text = pages()
    text[2] = text[2].replace("Arvosana-asteikon", row("TEST004V1 Invented failed attempt", "5", grade, "1.2.2026") + "\nArvosana-asteikon")
    snapshot = parse(text)
    assert snapshot.achievements[-1].status == "failed"
    assert credit_summary(snapshot, "test-right").total_credits == Decimal("3.5")


@pytest.mark.parametrize("marker", ["KHYV", "TRANSFER", "incomplete"])
def test_unverified_transfer_and_status_markers_fail_explicitly(marker):
    text = pages()
    text[2] = text[2].replace(row("TEST003V1 Invented third course", "2", "3", "3.2.2026"), row("TEST003V1 Invented third course", "2", marker, "3.2.2026"))
    with pytest.raises(PeppiError) as error:
        parse(text)
    assert error.value.code == "IMPORT_UNSUPPORTED_STATUS"


def test_printed_group_mismatch_withholds_even_when_global_total_matches():
    text = pages()
    text[1] = text[1].replace("1,5 op", "1,6 op")
    summary = credit_summary(parse(text), "test-right")
    assert summary.known_subtotal == Decimal("3.5")
    assert summary.status == "unresolved" and summary.total_credits is None


def test_source_total_discrepancy_remains_visible():
    text = pages()
    text[0] = text[0].replace("3,5 op", "4,5 op")
    summary = credit_summary(parse(text), "test-right")
    assert summary.total_credits == Decimal("3.5") and summary.source_reported_total == Decimal("4.5")
    assert summary.difference_from_source_total == -1
    assert any("differs" in warning for warning in summary.warnings)


def test_explicit_graded_module_components_count_once():
    text = pages()
    text[1] = text[1].replace(row("Invented subgroup", "1,5", indent=11), row("MOD001V1 Invented module", "1,5", "HYV", "4.2.2026", indent=11))
    # The graded module and its explicitly indented components occur inside a subtotal.
    snapshot = parse(text)
    module = next(record for record in snapshot.achievements if record.kind == "module")
    assert len(module.component_ids) == 2
    summary = credit_summary(snapshot, "test-right")
    assert summary.known_subtotal == Decimal("3.5")
    assert next(d for d in summary.decisions if d.achievement_id == module.id).disposition == "excluded"
    assert summary.total_credits == Decimal("3.5") and summary.status == "complete"


@pytest.mark.parametrize("change", ["issuer", "page-count", "date", "extra-row", "extra-right", "extra-cover-right", "legend", "duplicate-header"])
def test_changed_layout_is_rejected_without_silent_row_loss(change):
    text = pages()
    if change == "issuer":
        text[0] = text[0].replace("Lapin yliopisto", "Unknown institution")
    elif change == "page-count":
        text[1] = text[1].replace("sivu 2/3", "sivu 2/4")
    elif change == "date":
        text[1] = text[1].replace("1.3.2026", "2.3.2026")
    elif change == "extra-row":
        text[1] += "\nUNKNOWN PRIVATE TEXT"
    elif change == "extra-right":
        text[1] += "\nTutkinto  Another study right"
    elif change == "extra-cover-right":
        text[0] += "\nTutkinto  Another study right"
    elif change == "legend":
        text[2] = text[2].replace("Arvosana-asteikon selitykset", "Unknown legend")
    else:
        text[1] += "\nOpintosuoritukset Laajuus Arviointi Pvm Arvioija"
    with pytest.raises(PeppiError) as error:
        parse(text)
    assert error.value.code == "IMPORT_UNSUPPORTED_LAYOUT"
    assert "PRIVATE TEXT" not in error.value.message


@pytest.mark.parametrize("kind,code", [("non-pdf", "IMPORT_UNSUPPORTED_FORMAT"), ("broken", "IMPORT_INVALID_PDF"),
    ("encrypted", "IMPORT_ENCRYPTED"), ("blank", "IMPORT_TEXT_UNAVAILABLE"),
    ("rotated", "IMPORT_UNSUPPORTED_LAYOUT"), ("too-many-pages", "IMPORT_SIZE_INVALID"), ("oversized", "IMPORT_SIZE_INVALID")])
def test_extractor_failure_boundaries(kind, code):
    source = {"non-pdf": lambda: b"not a PDF", "broken": lambda: b"%PDF-1.7\nprivate-looking malformed content",
        "encrypted": lambda: pdf_bytes(encrypted=True), "blank": lambda: pdf_bytes([""]),
        "rotated": lambda: pdf_bytes(rotate=True), "too-many-pages": lambda: pdf_bytes([""] * 51),
        "oversized": lambda: b"%PDF-" + b"x" * (20 * 1024 * 1024)}[kind]()
    with pytest.raises(PeppiError) as error:
        extract_pages(source)
    assert error.value.code == code and "private-looking" not in error.value.message


def test_extraction_timeout_is_safe(monkeypatch):
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("extractor", 30)
    monkeypatch.setattr(subprocess, "run", timeout)
    with pytest.raises(PeppiError) as error:
        extract_pages(b"%PDF-1.7")
    assert error.value.code == "IMPORT_TIMEOUT"
