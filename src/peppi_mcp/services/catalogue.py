"""Public catalogue normalization, expiring snapshots and bound local pagination."""

import base64
import hashlib
import hmac
import json
import secrets
import threading
import time
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from urllib.parse import quote
from zoneinfo import ZoneInfo

from pydantic import TypeAdapter, ValidationError

from peppi_mcp.adapters.public_catalogue import HOST, SOURCE_WARNING, PublicFetcher
from peppi_mcp.catalogue_models import CourseResponse, OfferingResponse, SearchResponse
from peppi_mcp.errors import PeppiError

TTL_SECONDS = 300
MAX_ENTRIES = 32
HELSINKI = ZoneInfo("Europe/Helsinki")
OFFERINGS = TypeAdapter(list[OfferingResponse])


def sections(rows):
    # Preserve each source language and source markup as inert strings. Never render it.
    return [{"heading": row.title.texts(), "content": row.content.texts(), "format": "source_html_or_text"} for row in rows]


def credit(value):
    return None if value is None else format(value, "f")


def local_time(milliseconds):
    if milliseconds is None:
        return None
    return (datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(milliseconds=milliseconds)).astimezone(HELSINKI)


def normalize_search(raw):
    response = SearchResponse.model_validate(raw)
    ids = [row.learningUnitId for row in response.learningUnits]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate course IDs")
    items = [{"id": row.learningUnitId, "code": row.code, "title": row.name.texts(),
              "url": f"{HOST}/fi/opintojakso/{quote(row.code, safe='')}/{row.learningUnitId}"}
             for row in response.learningUnits]
    mismatch = len(items) != response.numberOfAllMatchedRows
    return {"items": items, "source_reported_count": response.numberOfAllMatchedRows,
            "completeness": "partial" if mismatch else "complete",
            "warnings": (["Source-reported count differs from received rows; refine the query. Upstream pagination is not verified."] if mismatch else [])}


def normalize_course(raw, course_id):
    row = CourseResponse.model_validate(raw)
    if row.id is not None and row.id != course_id:
        raise ValueError("Source course ID mismatch")
    warnings = []
    if row.credits is None:
        warnings.append("Source credits are missing; no credit value is inferred.")
    if not any(any(section.content.texts().values()) for section in row.contentList):
        warnings.append("The source supplied no descriptive content.")
    return {"id": course_id, "id_basis": "requested_source_identifier", "code": row.code, "title": row.name.texts(),
            "credits": credit(row.credits), "minimum_credits": credit(row.minCredits), "maximum_credits": credit(row.maxCredits),
            "sections": sections(row.contentList), "url": f"{HOST}/fi/opintojakso/{quote(row.code, safe='')}/{course_id}",
            "completeness": "unknown", "warnings": warnings}


def normalize_offerings(raw, course_id, collection):
    if not isinstance(raw, list) or len(raw) > 1000:
        raise ValueError("Invalid or excessive offering list")
    rows = OFFERINGS.validate_python(raw)
    ids = [row.realisationId for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate offering IDs")
    items = []
    for row in rows:
        start, end = local_time(row.startDate), local_time(row.endDate)
        enrol_start, enrol_end = local_time(row.enrollmentStartDateTime), local_time(row.enrollmentEndDateTime)
        warnings = []
        if start is None or end is None:
            warnings.append("Offering dates are incomplete; date overlap may be unknown.")
        items.append({"id": row.realisationId, "course_id": course_id, "code": row.code, "title": row.name.texts(),
                      "source_collection": collection, "start_date": start.date().isoformat() if start else None,
                      "end_date": end.date().isoformat() if end else None, "time_zone": "Europe/Helsinki",
                      "enrolment_start": enrol_start.isoformat() if enrol_start else None,
                      "enrolment_end": enrol_end.isoformat() if enrol_end else None,
                      "seats": row.seats, "cancellation_status": "unknown", "sections": sections(row.contentList),
                      "warnings": warnings})
    return {"items": items, "source_reported_count": None, "completeness": "unknown",
            "warnings": ["The source provides no total count or verified cancellation status. Current/past identifies the source collection, not enrolment availability."]}


@dataclass
class Entry:
    token: str
    payload: dict
    retrieved_at: datetime
    expires: float


class PublicCatalogue:
    def __init__(self, fetcher=None, *, monotonic=time.monotonic, now=None):
        self.fetcher = fetcher or PublicFetcher()
        self.monotonic = monotonic
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.cache = OrderedDict()
        self.secret = secrets.token_bytes(32)
        self.lock = threading.Lock()

    def _load(self, path, normalizer):
        entry = self.cache.get(path)
        if entry and entry.expires > self.monotonic():
            self.cache.move_to_end(path)
            return entry, "cached"
        self.cache.pop(path, None)
        raw = self.fetcher.fetch(path)
        try:
            payload = normalizer(raw)
        except (ValidationError, ValueError, TypeError, OverflowError):
            raise PeppiError("SOURCE_CHANGED", "Public catalogue fields did not match the observed schema; no records were silently skipped.") from None
        entry = Entry(secrets.token_hex(16), payload, self.now(), self.monotonic() + TTL_SECONDS)
        self.cache[path] = entry
        while len(self.cache) > MAX_ENTRIES:
            self.cache.popitem(last=False)
        return entry, "live"

    def _provenance(self, entry, mode, path):
        return {"source_id": "ulapland-public-catalogue", "institution_id": "ulapland-public-study-guide",
                "study_right_id": None, "source_mode": mode, "source_url": HOST + path,
                "retrieved_at": entry.retrieved_at.isoformat(), "source_updated_at": None,
                "cache_expires_at": (entry.retrieved_at + timedelta(seconds=TTL_SECONDS)).isoformat(),
                "completeness": entry.payload["completeness"],
                "completeness_scope": "received source response; not all institution courses or teaching",
                "warnings": [SOURCE_WARNING, *entry.payload["warnings"]]}

    def _encode(self, entry, binding, offset):
        body = json.dumps([entry.token, binding, offset], separators=(",", ":")).encode()
        signature = hmac.digest(self.secret, body, "sha256")
        return base64.urlsafe_b64encode(signature + body).decode().rstrip("=")

    def _decode(self, cursor, binding, path):
        try:
            raw = base64.b64decode(cursor + "=" * (-len(cursor) % 4), altchars=b"-_", validate=True)
            signature, body = raw[:32], raw[32:]
            if not hmac.compare_digest(signature, hmac.digest(self.secret, body, "sha256")):
                raise ValueError()
            token, bound, offset = json.loads(body)
            if bound != binding or type(offset) is not int or offset < 1:
                raise ValueError()
        except (ValueError, TypeError, UnicodeError):
            raise PeppiError("INVALID_CURSOR", "The cursor must match the original query, filters and page size.") from None
        entry = self.cache.get(path)
        if not entry or entry.token != token or entry.expires <= self.monotonic():
            raise PeppiError("CURSOR_EXPIRED", "The result snapshot expired or was evicted. Start again without a cursor.")
        self.cache.move_to_end(path)
        return entry, offset

    def call(self, name, args):
        with self.lock:
            if name == "get_course":
                path = "/api/course/" + args.course_id
                entry, mode = self._load(path, lambda raw: normalize_course(raw, args.course_id))
                return {**entry.payload, "provenance": self._provenance(entry, mode, path)}
            binding = hashlib.sha256(args.model_dump_json(exclude={"cursor"}).encode()).hexdigest()
            if name == "search_courses":
                path = "/api/lu/units/" + quote(args.query, safe="") + "/COURSE_UNIT"
                normalizer = normalize_search
            else:
                prefix = "/api/realizations/past/course/" if args.collection == "past" else "/api/realizations/course/"
                path = prefix + args.course_id
                normalizer = lambda raw: normalize_offerings(raw, args.course_id, args.collection)
            if args.cursor:
                entry, offset = self._decode(args.cursor, binding, path)
                mode = "cached"
            else:
                if name == "list_course_offerings":
                    # An empty offerings array must not disguise an invalid course ID.
                    self._load("/api/course/" + args.course_id, lambda raw: normalize_course(raw, args.course_id))
                entry, mode = self._load(path, normalizer)
                offset = 0
            provenance = self._provenance(entry, mode, path)
            items = entry.payload["items"]
            if name == "list_course_offerings":
                today = entry.retrieved_at.astimezone(HELSINKI).date().isoformat()
                filtered = []
                for item in items:
                    start, end = item["start_date"], item["end_date"]
                    if (args.date_from and end and end < args.date_from) or (args.date_to and start and start > args.date_to):
                        continue
                    unknown_overlap = bool((args.date_from and not end) or (args.date_to and not start))
                    phase = "unknown" if not start or not end else "historical" if end < today else "upcoming" if start > today else "ongoing"
                    filtered.append({**item, "date_phase": phase, "date_phase_as_of": today,
                                     "date_filter_match": "unknown" if unknown_overlap else "overlaps" if args.date_from or args.date_to else "not_filtered"})
                items = filtered
            page = [{**item, "provenance": provenance} for item in items[offset:offset + args.limit]]
            next_offset = offset + len(page)
            return {"items": page, "source_reported_count": entry.payload["source_reported_count"],
                    "retrieved_count": len(entry.payload["items"]), "matching_records": len(items),
                    "next_cursor": self._encode(entry, binding, next_offset) if next_offset < len(items) else None,
                    "pagination_scope": "local snapshot only", "provenance": provenance,
                    "warnings": ["Catalogue host identifies the publisher; individual course ownership is not established.",
                                 *(["Date filters use inclusive overlap in Europe/Helsinki. Records with uncertain overlap are retained and marked unknown."] if name == "list_course_offerings" else []),
                                 *provenance["warnings"]]}
