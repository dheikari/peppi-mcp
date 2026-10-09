# Access and feasibility investigation

Checked on **3 October 2026 (Europe/Helsinki)**. Evidence is separated into
documentation, direct anonymous reads, and observed personal browser access.

## Recommendation

The public catalogue is now the first real source connected through MCP. The
experimental adapter uses anonymously readable website backing routes, not a
documented third-party API contract. Completeness and cancellation limitations
are exposed in results. Usage conditions and a supported contract remain unresolved.

For personal completions, a deliberately supplied redacted transcript now works
through the local importer and MCP. One Finnish indented PDF layout was visually
inspected and reconciled; see [supported import scope](imports.md).
The isolated personal browser route has now been observed and implemented:
[session mechanism and limits](live-personal-access.md). It uses fresh account
checks, the authenticated study-right selector and visible completed transcript.
End-to-end MCP reads passed; full verification evidence is tracked separately in [verification](verification.md).
A supported student API contract and university automation guidance remain unresolved.

## Capability matrix

| Capability | Source and method | Evidence | Current server / limitation |
|---|---|---|---|
| Public course search | Study guide browser; anonymous JSON GET | Two-result search through MCP; broader search reports 259 but returns 224 | Experimental adapter with explicit discrepancy; upstream pagination unverified |
| Course details | Study guide course page; anonymous JSON GET | Code, multilingual name, 2-credit value and descriptive sections agree | Experimental adapter; missing content stays missing; request ID retained when response ID is null |
| Teaching offerings | Public catalogue realization routes | 13 past offerings through MCP for course 7300; sampled dates and enrolment window agree with browser | Current sample empty; cancellation and source-wide completeness unknown |
| Completed studies | User-selected PDF download | One redacted document inspected and reconciled through real MCP | Verified Finnish layout import; isolated live transcript reader verified through MCP; no signature verification |
| Study rights | PDF programme context and caller-selected local alias | Imported context remains separate; official guide documents switching rights | Import aliases remain local; live selector IDs bind to a freshly verified account |
| Personal enrolments | Authenticated Peppi | Student functions documented | Access and extraction unverified; tool unavailable |
| Personal study plan | Authenticated HOPS | Student functions documented | Access, curriculum version and equivalence relationships unverified |
| Public schedule | Separate Lukkarikone site | Lapland guide says anonymous timetable search is available | Runtime data retrieval and feed format unverified |
| Personal calendar feed | Peppi / university Outlook | Outlook synchronization documented | No iCalendar URL or supported third-party feed verified |

## Primary evidence and bounded checks

1. [Peppi architecture](https://www.peppi-konsortio.fi/kehitys-ja-kumppanit/)
   describes REST/SOAP integration mechanisms. [Integration overview](https://www.peppi-konsortio.fi/integraatiot-ja-liitannaiset/)
   describes institutional integrations. Neither establishes a Lapland student
   developer API or authorization to use it.
2. The [Lapland public study guide](https://opinto-opas-lay.peppi4.lapit.csc.fi/fi/etusivu/53896)
   loaded without sign-in. Searching `tutkimus` produced course definitions,
   including older and versioned codes. Do not equate a search hit with a future
   teaching offering or assume all returned records are current.
3. The [sample course page](https://opinto-opas-lay.peppi4.lapit.csc.fi/fi/opintojakso/XAKA0103V24/27674)
   displayed `XAKA0103V24`, `Tutkimuskirjoittaminen`, 2 credits, and a link to a
   2024–2027 curriculum. Its past-offerings control showed no entries. No
   descriptions or dated future offerings were visible for this sample.
4. The page's initial HTTP document was only a 1,003-character application shell.
   Its [published JavaScript bundle](https://opinto-opas-lay.peppi4.lapit.csc.fi/main.74996766f8e2f1f4ad6e.js)
   identified its backend host and URL construction. The following requests were
   derived from that code and observed source IDs, not guessed endpoints:

   | Request path on the study-guide host | Direct result |
   |---|---|
   | `/api/lu/units/XAKA0103/COURSE_UNIT` | HTTP 200; `learningUnits` with IDs `7300`, `27674`; `numberOfAllMatchedRows=2` |
   | `/api/course/27674` | HTTP 200 JSON; code/title/2 credits match the browser; `id=null`, content values empty |
   | `/api/course/7300` | JSON with code `XAKA0103`, Finnish and English names, 2 credits |
   | `/api/realizations/course/27674` | HTTP 200, `[]` |
   | `/api/realizations/course/7300` | Empty result |
   | `/api/realizations/past/course/7300` | 13 historical offerings; sampled dates and enrolment window matched browser |
   | `/api/lu/units/johdatus/COURSE_UNIT` | 259 reported matches but 224 received rows; MCP reports partial completeness |

   Optional `period` query values remain untested. The historical offering
   `XAKA0103-3001` spans 17 March–22 April 2020; enrolment is shown as
   2 December 2019 00:00–31 December 2019 23:59. Epoch timestamps converted to
   Europe/Helsinki agree with both displays. No verified cancellation field
   was found. A `createdAt` field
   was observed but its meaning is unverified: do not relabel it as a record's
   last-update time. The response ID can be null, so retain the observed request
   identifier separately. No authenticated endpoint was inspected.
5. [Lapland transcript guidance](https://ulapland.fi/opiskelijalle/opintojen-suorittaminen/opintosuoritukset/opintosuoritusote-ja-opiskelutodistus/)
   confirms digitally signed PDFs downloadable through Peppi. The
   [student transcript guide](https://blogi.eoppimispalvelut.fi/peppiopaslay/ohjekeskus/opiskelijalle/omat-opintotiedot/opintosuoritusten-tarkastelu-ja-opintosuoritusotteen-tulostus/)
   describes ordering a document, selecting its language and saving it from the
   documents tab. It also states that achievements are scoped by study right.
   A deliberately supplied redacted PDF was subsequently inspected and verified
   in milestone 3. No CSV, JSON or XML export format is established or advertised.
6. [Lapland's Peppi introduction](https://blogi.eoppimispalvelut.fi/peppiopaslay/ohjekeskus/opiskelijalle/mika-on-peppi/mika-on-peppi/)
   specifies HAKA login with two-step authentication, selecting University of
   Lapland. It documents personal records, study rights and HOPS functionality.
   This describes interactive sign-in; it does not document OAuth scopes or a
   student access token. The public [student landing page](https://opiskelija-lay.peppi4.lapit.csc.fi/)
   was reachable. No private login or MFA was attempted.
7. [Lapland timetable guidance](https://blogi.eoppimispalvelut.fi/peppiopaslay/ohjekeskus/opiskelijalle/opintojen-suunnittelu-ja-hops/lukujarjestysten-tarkastelu/)
   links to [Lukkarikone](https://lukkarikone-lay.peppi4.lapit.csc.fi/) and describes
   anonymous searches by implementation, group or room. The separate
   [Outlook synchronization guidance](https://blogi.eoppimispalvelut.fi/peppiopaslay/ohjekeskus/opiskelijalle/opintojen-suunnittelu-ja-hops/pepin-ajanvaraukset-ja-outlook-synkronointi/)
   describes Peppi-to-email-calendar synchronization. That is not evidence of an
   exportable ICS feed. These guides were last updated in 2023; verify present
   behavior before an adapter is advertised.

## Access conditions and maintenance

| Route | Authentication | Pagination / limits | Expected maintenance and unresolved conditions |
|---|---|---|---|
| Public catalogue backing JSON | None in the sampled reads | Count discrepancy verified; upstream page parameters and caps unverified; adapter paginates only received rows | Experimental; no verified automation contract or upstream quota. Local throttle/cache are conservative choices, not institution-approved limits |
| Transcript import | User selects an already downloaded PDF; no login during import | One verified Finnish layout; 20 MiB, 50 pages; bounded extraction | Deterministic parser, checksum/provenance and explicit immutable snapshot selection; other formats and signatures unverified |
| Live personal API | Not established | Unknown | Institution clarification needed: availability, scopes, client registration, expiry and permitted destinations |
| Personal browser session | HAKA + MFA for ordinary UI | Unknown | Potentially fragile; suitability and access conditions not established; never request cookies/passwords in chat |
| Lukkarikone / calendar | Anonymous timetable viewing documented; personal sync uses account | Unknown | Independent investigation; do not treat institutional Outlook sync as a public feed |

No bulk crawl, load testing, repeated authentication, mutation or staff contact
was performed. Source descriptions and imports must remain inert data.
The host's `/robots.txt` returned the HTML application shell, not machine-readable
robot directives. This does not establish permission or stability guarantees.

## Existing implementations and reuse

The owner subsequently supplied [ink-waffle/moodle-mcp](https://github.com/ink-waffle/moodle-mcp)
and [ink-waffle/sisu-mcp](https://github.com/ink-waffle/sisu-mcp). Their pinned
authentication, browser, client and connection sources were inspected; see
[design comparison](reference-mcps.md). They provide concrete browser-assisted
connection patterns, but neither establishes a Lapland Peppi private endpoint.
The earlier bounded search below did not include these owner-supplied references.

The bounded search covered web queries for Peppi/MCP/Python/API and GitHub
repository searches for `peppi university`, `peppi api`, and
`peppi in:name language:Python`. It did not establish a maintained Lapland
student MCP implementation. Search failure is not proof of nonexistence.

- [NASA-PDS/peppi](https://github.com/NASA-PDS/peppi) includes MCP functionality
  for planetary data. It is unrelated to the Finnish student system.
- [hohav/peppi-py](https://github.com/hohav/peppi-py) parses game replay files;
  also unrelated despite its name and recent activity.
- [joonajuusti/peppi-google-calendar-extension](https://github.com/joonajuusti/peppi-google-calendar-extension)
  targets Turku study-guide schedules. GitHub metadata reported last push in
  August 2019. This does not establish current Lapland compatibility.
- [ouspg/PeppiMoodleJS](https://github.com/ouspg/PeppiMoodleJS) describes helper
  scripts; metadata reported an April 2026 push. Its public file list includes
  grading-page scripts and no root README. It is not established as a reusable
  student read-only connector; no code was executed or copied.
- Reuse the [official MCP Python SDK](https://github.com/modelcontextprotocol/python-sdk)
  for transport and client behavior. [PyPI metadata](https://pypi.org/pypi/mcp/json)
  reported stable `2.3.0`, requiring Python >=3.10. This project narrows its
  tested runtime to Python 3.12. The SDK supports stdio, Streamable HTTP and SSE;
  only stdio is enabled here.

## Required next evidence

Further import layouts require deliberately chosen examples outside this
repository with preserved table text/structure. For live integration,
obtain supported access conditions and authentication details from the university
or another authoritative source. An [inquiry draft](university-inquiry.md) is
prepared for the owner to send; nothing has been sent.
