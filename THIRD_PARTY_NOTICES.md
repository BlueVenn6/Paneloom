# Third-party notices

Paneloom is licensed under the MIT License. Its direct dependencies use the
following permissive licenses; dependency packages retain their own copyright
notices and license texts.

## Python runtime

| Package | License |
|---|---|
| FastAPI | MIT |
| Starlette | BSD-3-Clause |
| Uvicorn | BSD-3-Clause |
| Requests | Apache-2.0 |
| openpyxl | MIT |
| python-multipart | Apache-2.0 |
| Pydantic | MIT |
| pypdf | BSD-3-Clause |
| python-docx | MIT |
| Pillow | MIT-CMU |
| pywebview | BSD-3-Clause |

## Frontend runtime and build

| Package | License |
|---|---|
| React | MIT |
| React DOM | MIT |
| Lucide React | ISC |
| Vite | MIT |
| Vite React plugin | MIT |
| ESLint and ESLint JS | MIT |
| React Hooks ESLint plugin | MIT |
| React Refresh ESLint plugin | MIT |
| globals | MIT |

## Packaging and external runtime components

| Component | Terms |
|---|---|
| PyInstaller 6.20.0 | GPL-2.0-or-later with the PyInstaller bootloader exception; full text is included in `THIRD_PARTY_LICENSES.md`. |
| NSIS 3.12 | zlib/libpng-style license; the compiler's `COPYING` file is included at `packaging/licenses/NSIS-COPYING.txt`. |
| Microsoft Edge WebView2 Runtime | Microsoft redistribution terms apply. The installer embeds the Microsoft-signed Evergreen Bootstrapper and records its source, signer, and SHA-256 in the build manifest. |

The complete Python and npm transitive inventory is generated in
`THIRD_PARTY_LICENSES.md`. Machine-readable CycloneDX documents are under
`sbom/`. These files describe the exact frozen Beta environment; dependencies
retain their own copyright and license terms.
