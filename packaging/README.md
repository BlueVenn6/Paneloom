# Windows packaging

The installer is built only from a clean Git worktree. The application source
must match the annotated `v0.1.0-beta.1-functional-baseline` tag; later changes
are limited to the packaging files listed by `scripts/build_windows_installer.ps1`.

Build from PowerShell:

```powershell
.\scripts\build_windows_installer.ps1
```

Generated files are written below `artifacts/` and are not tracked. The build
downloads Microsoft's signed WebView2 Evergreen Bootstrapper, produces a
PyInstaller one-folder application, compiles a per-user NSIS installer,
and writes hashes and source identities to `build-manifest.json`.

The installer is currently unsigned. Windows SmartScreen can therefore show an
unknown-publisher warning even when the SHA-256 matches the build manifest.
