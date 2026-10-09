# Dependency inventory

Declared installed metadata for the pinned Windows Python 3.12 environment.
Project code is licensed under MIT. This records upstream declarations; dependency-license compatibility and redistribution requirements remain separate checks.

| Distribution | Version | Declared license |
|---|---|---|
| annotated-types | 0.8.0 | MIT |
| anyio | 4.15.1 | MIT |
| attrs | 26.1.0 | MIT |
| build | 1.6.1 | MIT |
| certifi | 2026.7.22 | Mozilla Public License 2.0 (MPL 2.0) |
| cffi | 2.1.1 | MIT-0 |
| click | 8.5.0 | BSD-3-Clause |
| colorama | 0.4.6 | BSD License |
| cryptography | 50.0.2 | Apache-2.0 OR BSD-3-Clause |
| h11 | 0.16.0 | MIT License |
| httpcore2 | 2.13.1 | BSD-3-Clause |
| httpx2 | 2.13.1 | BSD-3-Clause |
| idna | 3.20 | BSD-3-Clause |
| iniconfig | 2.3.0 | MIT |
| jsonschema | 4.26.0 | MIT |
| jsonschema-specifications | 2025.9.1 | MIT |
| mcp | 2.3.0 | MIT License |
| mcp-types | 2.3.0 | MIT License |
| opentelemetry-api | 1.45.0 | Apache-2.0 |
| outcome | 1.3.0.post0 | MIT License; Apache Software License |
| packaging | 26.3 | Apache-2.0 OR BSD-2-Clause |
| pluggy | 1.6.0 | MIT License |
| pycparser | 3.0 | BSD-3-Clause |
| pydantic | 2.13.5 | MIT |
| pydantic_core | 2.46.5 | MIT |
| Pygments | 2.21.0 | BSD-2-Clause |
| PyJWT | 2.15.1 | MIT |
| pypdf | 6.19.0 | BSD-3-Clause |
| pyproject_hooks | 1.3.3 | MIT |
| PySocks | 1.7.1 | BSD |
| pytest | 9.1.1 | MIT |
| python-multipart | 0.0.32 | Apache-2.0 |
| pywin32 | 312 | Python Software Foundation License |
| referencing | 0.37.0 | MIT |
| rpds-py | 2026.6.3 | MIT |
| selenium | 4.43.0 | Apache-2.0 |
| setuptools | 84.0.0 | MIT |
| sniffio | 1.3.1 | MIT License; Apache Software License |
| sortedcontainers | 2.4.0 | Apache Software License |
| sse-starlette | 3.5.0 | BSD-3-Clause |
| starlette | 1.7.0 | BSD-3-Clause |
| trio | 0.34.0 | MIT OR Apache-2.0 |
| trio-websocket | 0.12.2 | MIT License |
| truststore | 0.10.4 | MIT |
| typing-inspection | 0.4.4 | MIT |
| typing_extensions | 4.16.0 | PSF-2.0 |
| tzdata | 2026.4 | Apache-2.0 |
| urllib3 | 2.8.0 | MIT |
| uvicorn | 0.54.0 | BSD-3-Clause |
| websocket-client | 1.9.2 | Apache-2.0 |
| wsproto | 1.3.2 | MIT |

## Advisory findings

On 3 October 2026, [pip-audit](https://pypi.org/project/pip-audit/) 2.10.1 found no known vulnerabilities in either pinned lock.
The same advisory check was refreshed on 4 October after the Claude compatibility
update, again with no known vulnerabilities reported for either unchanged lock.
The scans used --no-deps --disable-pip against the complete resolved lists; no advisories were ignored and no project dependencies were upgraded.
Advisory coverage is time-bound. Locks are version-pinned, not hash-verified. The separate audit tool environment is not a runtime dependency.

On 9 October 2026, pip-audit 2.10.1 scanned the complete resolved development
and live locks (`--no-deps --disable-pip`): 51 distinct distributions, no known
vulnerabilities and no skipped distributions. No advisories were suppressed and
no versions were changed. The license inventory was refreshed from installed
metadata for the same pins. All entries declare a license; the alpha wheel
contains project code and its exact MIT notice, not vendored dependency code.
Dependencies installed separately retain their upstream notices and licenses,
including certifi's MPL declaration. This inventory is not independent legal
review of upstream declarations or a promise that no undisclosed vulnerability exists.

The [hosted Windows run on 9 October](https://github.com/dheikari/peppi-mcp/actions/runs/37963403553)
also completed its separate pip-audit 2.10.1 scan against both unchanged locks,
reporting no known vulnerabilities. It retained pip-audit's warning recommending
hash-verified pins; the current locks remain version-pinned without hashes.

The local scan was refreshed after the alpha timeout-cleanup test correction on
9 October: the same 51 pins, no known vulnerabilities or skipped distributions.
Installed license declarations still cover every pinned distribution. No
advisories were ignored and no dependencies were upgraded. The subsequent failed
hosted run did not reach its advisory step; the corrected commit requires a fresh
successful hosted run.
