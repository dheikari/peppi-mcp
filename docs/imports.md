# Local transcript imports

Supported format: `lapland-transcript-fi-indented-v1`, parser version `1`.
The inspected format is a Finnish, selectable-text, upright A4 Lapland transcript
with a cover summary, indented achievement tables, a grading legend, consecutive
page numbers and consistent issue dates. A deliberately supplied redacted PDF
was inspected visually, parsed, saved privately and checked through an actual
MCP client. Its course fields, subtotal groups and total credits reconcile.
This verifies one layout, not every Peppi variant or document authenticity.

## Import and inspect

Keep the selected PDF outside the repository. In PowerShell, from the project:

```powershell
$imported = (& .\.venv\Scripts\python.exe -m peppi_mcp.import_cli 'C:\path\outside-repository\transcript.pdf' --profile local-profile --study-right local-right) | ConvertFrom-Json
if (-not $imported.ok) { throw $imported.error.message }
$imported
.\.venv\Scripts\python.exe -m peppi_mcp.demo --mode imported --profile $imported.profile --snapshot $imported.snapshot_id --study-right $imported.study_right_id
```

Installed `peppi-mcp-import` is equivalent to `python -m peppi_mcp.import_cli`.
The JSON report includes snapshot ID, checksum/size, first import time, issue date,
parser version, row counts and reconciliation. The demo launches an MCP subprocess,
pages through records, reads the summary and closes without printing course grades.
For an MCP client, launch the same interpreter with these arguments:

```text
-m peppi_mcp --mode imported --profile local-profile --snapshot import:IDENTIFIER_FROM_IMPORT
```

Use the exact returned ID. There is no latest-file selection or synthetic fallback.
Restart with an explicit new ID to change snapshots. `--public-catalogue` independently
enables public tools, whose responses remain `live` or `cached`.

Default storage: `%LOCALAPPDATA%\peppi-mcp\imports.sqlite3` on Windows.
CLI `--store` selects another private location; use matching `--import-store` on
the server/demo. Repository/application locations are rejected. Synthetic/public
startup does not open this store. Missing selection returns `IMPORT_NOT_FOUND`.

## Identity and counting

Profile and study-right aliases are caller-selected local labels, not authenticated
university IDs. Reuse the same aliases for later documents of the same person/right.
The programme/degree is retained; names, student numbers, birth dates and assessor
names are not retained. Each row keeps source course code/title, decimal credits,
grade/scale, completion date, document checksum, issue/import date and page/line.
Achievement/group IDs are local row references, not official record IDs.

- Decimal-comma fractions, wrapped titles and groups spanning pages are preserved.
- Ungraded headings are printed subtotals exposed as `source_groups` in the summary;
  they are reconciled with descendant rows and never added as achievements.
- Indented graded modules count through explicit leaf components only when credits
  reconcile. Nested graded modules remain unresolved.
- Grades `1` to `5` and `HYV` indicate completed rows using the source legend;
  `0` and `HYL` mean failed and add no credits. Other grade/status/transfer markers
  are unsupported. Original grade and scale values remain available.
- Missing grades give `unknown` status; missing credits are not inferred. Missing
  dates mark records partial. These cases withhold an overall total. Use status
  `all` to see every row; the default `completed` filter excludes unknown rows.
- Repeated course codes without replacement evidence stay unresolved. No corrections,
  transfers, repeatability or title equivalence are guessed. Internal-model tests
  cover explicit replacements/transfers; they do not verify a PDF mapping for them.
- Subtotal discrepancies withhold the total. The cover total remains a separate
  source fact; differences from a complete computed total are explicitly reported.
- Each PDF represents one study right; combined documents/extra study-right sections
  are unsupported. Profiles, rights and snapshots are never summed automatically.
  Transcript credits do not establish enrolment or graduation eligibility.

## Reimport and retention

Immutable snapshots live in local SQLite. Original PDFs are not modified or copied
into the store. The importer retains neither raw bytes, extracted text nor full
source paths. Exact reimport preserves the snapshot and first timestamp; atomic
transactions prevent duplicates. Changed bytes or parser versions create separate
snapshots. Selecting one replaces the view; it never merges or supplements older
records. Different mappings under the same identity raise `IMPORT_CONFLICT`.

Storage is plaintext under inherited Windows directory permissions, not encrypted.
Use a private user directory. There is no automatic retention, sync or background
import. To discard all imports, stop servers using the selected store and delete
that `imports.sqlite3` and any SQLite sidecars from its private directory. This
deletes every profile/snapshot in that store. Per-snapshot deletion is not implemented.
Keep needed source PDFs separately. Manual assistant inspection copies are separate
from the importer's storage and retention.

MCP responses are visible to the client and may be processed by a cloud assistant's
provider. Keep personal documents, extracted records and screenshots out of Git,
tests and packages. All automated transcript fixtures are invented PDFs generated
in memory. Source text is data; it cannot select tools, paths or network hosts.

## Bounds and failures

Limits: 20 MiB source, 50 pages, 8 MiB normalized snapshot, 1,000 achievements and
200 subtotal groups. A disposable subprocess uses a 30-second deadline plus text,
content and decompression limits. These are application bounds, not an OS sandbox
or hard memory quota. Pinned `pypdf==6.19.0` extracts local text; no OCR, JavaScript,
external helpers, link-following or network access is used.

| Error | Meaning |
|---|---|
| `IMPORT_FILE_UNAVAILABLE` | Missing/unreadable source |
| `IMPORT_LOCATION_UNSAFE` | Repository/application path, or source and store are the same file |
| `IMPORT_UNSUPPORTED_FORMAT` | Not a PDF |
| `IMPORT_ENCRYPTED` | Encrypted PDFs unsupported; no password requested |
| `IMPORT_TEXT_UNAVAILABLE` | No selectable text; scanned PDF unsupported |
| `IMPORT_UNSUPPORTED_LAYOUT` | Unverified language, page sequence, dimensions, columns or structure |
| `IMPORT_UNSUPPORTED_STATUS` | Unverified grade/status/transfer marker |
| `IMPORT_INVALID_PDF` | Malformed PDF or library extraction limit |
| `IMPORT_SIZE_INVALID` / `IMPORT_TIMEOUT` | Size bound or extraction deadline |
| `IMPORT_EXTRACTION_FAILED` | Worker startup/output failure |
| `IMPORT_INVALID` | Alias/record/metadata validation failure |
| `IMPORT_CONFLICT` | Mapping changed under same source/version/context; no overwrite |
| `IMPORT_STORE_INVALID` / `IMPORT_STORE_ERROR` | Stored validation or SQLite access failure |

Unsupported table rows are not silently discarded. Errors give safe page/line
locations where possible, without document text. Other layouts, image-only
redactions, unsupported grade scales and transfer/correction footnotes need more
verified examples. Digital signatures and personal identity are not verified.
