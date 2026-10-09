"""Deterministic parser for the inspected Finnish, indented Lapland PDF layout.

Ungraded headings are source subtotals, not achievements. Hierarchy comes from
layout indentation, never title equivalence. Names, student IDs and assessors
are not retained. Unsupported structures fail rather than silently dropping rows.
"""

import hashlib
import re
from datetime import datetime, timezone
from decimal import Decimal

from pydantic import ValidationError

from peppi_mcp.errors import PeppiError
from peppi_mcp.models import Achievement, Provenance, ScopedArguments, Snapshot, SourceGroup, StudyRight
from peppi_mcp.pdf_extract import extract_pages

FORMAT = "lapland-transcript-fi-indented-v1"
PARSER_VERSION = "1"
DATE = r"\d{1,2}\.\d{1,2}\.\d{4}"
CODE = re.compile(r"[A-Z][A-Z0-9_.:-]*\d[A-Z0-9_.:-]*\Z")
WARNINGS = ("Imported document snapshot, not live Peppi data.",
            "Study-right identifier is a caller-selected local alias; personal identity is not verified.",
            "PDF authenticity and digital signatures have not been verified.")


def fail(page=None, line=None):
    location = f" (page {page}, extracted line {line})" if page else ""
    raise PeppiError("IMPORT_UNSUPPORTED_LAYOUT", "Transcript does not match the verified Finnish layout" + location + "; no rows were silently skipped.")


def day(value):
    return datetime.strptime(value, "%d.%m.%Y").date()


def parse_pdf(source: bytes, study_right_id: str) -> Snapshot:
    return parse_pages(extract_pages(source), source_sha256=hashlib.sha256(source).hexdigest(), study_right_id=study_right_id)


def parse_pages(pages: list[str], *, source_sha256: str, study_right_id: str, now=None) -> Snapshot:
    """Text-only seam for fictional layout tests; not a user import format."""
    try:
        ScopedArguments(study_right_id=study_right_id)
        return _parse(pages, source_sha256, study_right_id, now or datetime.now(timezone.utc))
    except ValidationError:
        raise PeppiError("IMPORT_INVALID", "Transcript records or the selected study-right alias failed validation.") from None
    except (ValueError, IndexError, TypeError, ArithmeticError):
        raise PeppiError("IMPORT_UNSUPPORTED_LAYOUT", "Transcript contains unsupported dates, amounts or structure; no import was saved.") from None


def _parse(pages, checksum, right_id, imported_at):
    if not 2 <= len(pages) <= 50:
        fail()
    issued = None
    for index, text in enumerate(pages, 1):
        if "Lapin yliopisto" not in text or "Opintosuoritusote" not in text or "\ufffd" in text:
            fail(index, 1)
        counter = re.findall(r"sivu\s+(\d+)/(\d+)", text)
        if counter != [(str(index), str(len(pages)))]:
            fail(index, 1)
        header = re.search(r"Opintosuoritusote[^\n]*\n\s*(" + DATE + r")\s*(?:\n|$)", text)
        if not header:
            fail(index, 1)
        current = day(header[1])
        if issued is not None and issued != current:
            fail(index, 1)
        issued = current
    first = pages[0]
    degrees = list(re.finditer(r"^\s*Tutkinto\s{2,}(\S.*?)(?:\s{2,}|$)", first, re.M))
    programmes = list(re.finditer(r"^\s*Ohjelma\s{2,}(\S.*?)(?:\s{2,}|$)", first, re.M))
    totals = re.findall(r"\bSuoritettu\s+(\d+(?:,\d+)?)\s+op\b", first)
    if len(degrees) != 1 or len(programmes) != 1 or len(totals) != 1 or first.count("Opiskeluoikeusaika") != 1:
        fail(1, 1)
    degree, programme = degrees[0], programmes[0]
    all_text = "\n".join(pages)
    if not all(label in all_text for label in ("Arvosana-asteikon selitykset", "5 = Erinomainen", "HYV = Hyväksytty", "HYL, 0 = Hylätty")):
        fail()
    official = Decimal(totals[0].replace(",", "."))
    identity = "document:" + checksum
    def provenance(page, line, warnings=(), completeness="complete"):
        return Provenance(source_id=identity, institution_id="ulapland", study_right_id=right_id,
                          source_mode="imported", retrieved_at=imported_at, source_issued_on=issued,
                          source_sha256=checksum, source_page=page, source_line=line,
                          completeness=completeness, warnings=(*WARNINGS, *warnings))
    entries, stack = [], []
    previous = None
    saw_table = False
    ended = False
    for page_number, text in enumerate(pages, 1):
        lines = text.splitlines()
        headers = [(i, line) for i, line in enumerate(lines) if all(label in line for label in ("Opintosuoritukset", "Laajuus", "Arviointi", "Pvm", "Arvioija"))]
        if not headers:
            if page_number != 1 and "Sähköinen allekirjoitus" not in text:
                fail(page_number, 1)
            continue
        if ended or len(headers) != 1 or page_number == 1:
            fail(page_number, 1)
        saw_table = True
        header_index, header = headers[0]
        credit_column = header.index("Laajuus")
        grade_column = (header.index("Laajuus") + header.index("Arviointi")) // 2 + 3
        date_column = (header.index("Arviointi") + header.index("Pvm")) // 2 + 2
        assessor_column = header.index("Arvioija") - 1
        if not 30 < credit_column < grade_column < date_column < assessor_column:
            fail(page_number, header_index + 1)
        for line_index, line in enumerate(lines[header_index + 1:], header_index + 2):
            if "Arvosana-asteikon selitykset" in line:
                ended = True
                break
            if not line.strip():
                continue
            # Ignore only the explicitly identified assessor column; never retain it.
            body = line[:assessor_column].rstrip()
            if not body.strip():
                continue
            indent = (len(body) - len(body.lstrip())) / credit_column
            left = body[:max(0, credit_column - 5)].strip()
            if not entries and left == degree[1].strip() and not body[max(0, credit_column - 5):].strip():
                continue
            amount = re.search(r"\s{2,}(\d+(?:,\d+)?)\s+op(?:\s|$)", body)
            if amount:
                title = body[:amount.start()].strip()
                credits = Decimal(amount[1].replace(",", "."))
            else:
                title, credits = left, None
            code, _, name = title.partition(" ")
            is_course = bool(CODE.fullmatch(code))
            if not amount and not is_course:
                # Verified wrapped titles continue at the same indentation in the
                # name column, with blank credit/grade/date fields.
                if previous is not None and previous["course"] and abs(indent - previous["indent"]) < 0.015 and left and left[0].islower() and not body[credit_column - 5:].strip():
                    previous["title"] += " " + left
                    continue
                fail(page_number, line_index)
            grade = body[grade_column:date_column].strip() or None
            if grade is not None and grade not in {"1", "2", "3", "4", "5", "HYV", "HYL", "0"}:
                raise PeppiError("IMPORT_UNSUPPORTED_STATUS", f"Unverified grade or transfer marker on page {page_number}; no import was saved.")
            date_text = body[date_column:].strip() or None
            if date_text is not None and not re.fullmatch(DATE, date_text):
                fail(page_number, line_index)
            completed_on = day(date_text) if date_text else None
            if not is_course and (grade or completed_on or credits is None):
                fail(page_number, line_index)
            if is_course and (not name or any(c in code for c in ("*", "/"))):
                fail(page_number, line_index)
            while stack and indent <= stack[-1]["indent"] + 0.015:
                stack.pop()
            entry = {"id": f"{'a' if is_course else 'g'}:{len(entries)+1}", "course": is_course,
                     "code": code if is_course else None, "title": name if is_course else title,
                     "credits": credits, "grade": grade, "date": completed_on,
                     "indent": indent, "children": [], "page": page_number, "line": line_index}
            for parent in stack:
                parent["children"].append(entry)
            entries.append(entry)
            stack.append(entry)
            previous = entry
    if not saw_table or not ended or (not entries and official != 0):
        fail()
    records, groups = [], []
    for entry in entries:
        children = [child for child in entry["children"] if child["course"]]
        if not entry["course"]:
            groups.append(SourceGroup(id=entry["id"], title=entry["title"], credits=entry["credits"],
                          component_ids=tuple(child["id"] for child in children),
                          provenance=provenance(entry["page"], entry["line"])))
            continue
        warnings = []
        grade = entry["grade"]
        status = "unknown" if grade is None else "failed" if grade in {"HYL", "0"} else "completed"
        if grade is None:
            warnings.append("Source grade is missing; completion status is unknown.")
        if entry["credits"] is None:
            warnings.append("Source credits are missing; no amount was inferred.")
        if entry["date"] is None:
            warnings.append("Completion date is absent from the source.")
        if entry["date"] is not None and entry["date"] > issued:
            warnings.append("Completion date is later than the document issue date.")
        records.append(Achievement(id=entry["id"], course_id=entry["code"], title=entry["title"],
            status=status, source_status=f"Transcript grade: {grade}" if grade else "Transcript grade missing",
            kind="module" if children else "course", credits=entry["credits"], completed_on=entry["date"],
            grade=grade, grading_scale="HYV/HYL" if grade in {"HYV", "HYL"} else "0-5" if grade else None,
            credit_group_id=entry["code"], component_ids=tuple(child["id"] for child in children) if children else None,
            provenance=provenance(entry["page"], entry["line"], warnings, "partial" if warnings else "complete")))
    return Snapshot(id=identity, study_rights=(StudyRight(id=right_id,
                    programme=degree[1].strip() + " / " + programme[1].strip(), official_total=official,
                    provenance=provenance(1, 1)),), achievements=tuple(records), source_groups=tuple(groups))
