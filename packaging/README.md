# Windows packaging

The installer is built only from a clean Git worktree. The application source
must match the annotated `v0.1.0-beta.1-functional-baseline` tag; later changes
are limited to the packaging files listed by `scripts/build_windows_installer.ps1`.

Build from PowerShell:

```powershell
.\.desktop-venv\Scripts\python.exe -m pip install -r requirements-lock.txt
.\scripts\build_windows_installer.ps1
```

`requirements-build.txt` declares the intended direct build tools;
`requirements-lock.txt` pins the exact Windows/Python 3.12 transitive environment
used for this Beta.

Generated files are written below `artifacts/` and are not tracked. The build
downloads Microsoft's signed WebView2 Evergreen Bootstrapper, produces a
PyInstaller one-folder application, compiles a per-user NSIS installer,
and writes hashes and source identities to `build-manifest.json`.

The installer is currently unsigned. Windows SmartScreen can therefore show an
unknown-publisher warning even when the SHA-256 matches the build manifest.

The packaged application also contains the exact CycloneDX SBOM files,
`THIRD_PARTY_NOTICES.md`, `THIRD_PARTY_LICENSES.md`, and the NSIS license text.
The build manifest records hashes for the tracked SBOM and license inventory.

Before a signed public binary release, configure an Authenticode certificate
and validate the exact signed installer on an independent clean Windows 10/11
machine. The current script intentionally does not pretend to sign when no
certificate or `signtool.exe` is available.
