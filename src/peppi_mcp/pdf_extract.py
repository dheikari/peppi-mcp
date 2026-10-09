"""Bounded local PDF text extraction in a disposable subprocess; no OCR or links."""

import io
import json
import logging
import subprocess
import sys

from peppi_mcp.errors import PeppiError
from peppi_mcp.import_store import MAX_DOCUMENT_BYTES

MAX_TEXT = 500_000


def extract_pages(source: bytes) -> list[str]:
    if not 0 < len(source) <= MAX_DOCUMENT_BYTES:
        raise PeppiError("IMPORT_SIZE_INVALID", "PDF must contain between 1 byte and 20 MiB.")
    if not source.startswith(b"%PDF-"):
        raise PeppiError("IMPORT_UNSUPPORTED_FORMAT", "Expected a PDF document; no data was imported.")
    try:
        response = subprocess.run([sys.executable, "-m", "peppi_mcp.pdf_extract"], input=source,
                                  capture_output=True, timeout=30, check=False)
    except subprocess.TimeoutExpired:
        raise PeppiError("IMPORT_TIMEOUT", "PDF extraction exceeded 30 seconds; nothing was imported.") from None
    except OSError:
        raise PeppiError("IMPORT_EXTRACTION_FAILED", "The local PDF extractor could not start.") from None
    if response.returncode or len(response.stdout) > MAX_TEXT * 8:
        raise PeppiError("IMPORT_EXTRACTION_FAILED", "PDF extraction failed; nothing was imported.")
    try:
        result = json.loads(response.stdout)
        if not result["ok"]:
            raise PeppiError(result["code"], result["message"])
        pages = result["pages"]
        if not isinstance(pages, list) or not 1 <= len(pages) <= 50 or any(not isinstance(p, str) for p in pages) or sum(map(len, pages)) > MAX_TEXT:
            raise ValueError()
        return pages
    except (ValueError, KeyError, TypeError):
        raise PeppiError("IMPORT_EXTRACTION_FAILED", "The PDF extractor returned an invalid result.") from None


def main():
    # Library warnings can contain document text. Never forward them to the CLI.
    logging.disable(logging.CRITICAL)
    try:
        from pypdf import PdfReader, apply_configuration
        source = sys.stdin.buffer.read(MAX_DOCUMENT_BYTES + 1)
        if not 0 < len(source) <= MAX_DOCUMENT_BYTES:
            raise PeppiError("IMPORT_SIZE_INVALID", "PDF exceeded the document size limit.")
        with apply_configuration(maximum_declared_stream_length=8_000_000,
                array_based_stream_maximum_output_length=8_000_000, zlib_maximum_output_length=8_000_000,
                lzw_maximum_output_length=8_000_000, run_length_maximum_output_length=8_000_000,
                image_maximum_buffer_size=8_000_000, jbig2dec_binary=None,
                page_tree_maximum_entries=200, page_tree_maximum_depth=15,
                xform_maximum_invocations_per_extraction=500):
            reader = PdfReader(io.BytesIO(source), strict=True)
            if reader.is_encrypted:
                raise PeppiError("IMPORT_ENCRYPTED", "Encrypted PDFs are not supported. Select an unencrypted transcript.")
            if not 1 <= len(reader.pages) <= 50:
                raise PeppiError("IMPORT_SIZE_INVALID", "PDF must contain 1 to 50 pages.")
            pages = []
            for page in reader.pages:
                if page.rotation or not (590 <= float(page.mediabox.width) <= 600 and 837 <= float(page.mediabox.height) <= 847):
                    raise PeppiError("IMPORT_UNSUPPORTED_LAYOUT", "Only the verified upright A4 transcript layout is supported.")
                content = page.get_contents()
                if content is not None and len(content.get_data()) > 8_000_000:
                    raise PeppiError("IMPORT_SIZE_INVALID", "PDF page content exceeded its extraction limit.")
                pages.append(page.extract_text(extraction_mode="layout"))
                if len(pages[-1]) > 100_000 or sum(map(len, pages)) > MAX_TEXT:
                    raise PeppiError("IMPORT_SIZE_INVALID", "Extracted PDF text exceeded the supported limits.")
            if not any(p.strip() for p in pages):
                raise PeppiError("IMPORT_TEXT_UNAVAILABLE", "No selectable transcript text was found; scanned PDFs are not supported.")
            result = {"ok": True, "pages": pages}
    except PeppiError as exc:
        result = {"ok": False, "code": exc.code, "message": exc.message}
    except Exception:
        result = {"ok": False, "code": "IMPORT_INVALID_PDF", "message": "The PDF is malformed or exceeds safe extraction limits; nothing was imported."}
    sys.stdout.buffer.write(json.dumps(result, ensure_ascii=True).encode("ascii"))


if __name__ == "__main__":
    main()
