# Changelog

All notable changes to Paneloom are recorded here.

## 0.1.0-beta.2 - 2026-07-21

- Constrained project creation, opening, migration, backup, restore, image, and reference paths to approved local roots.
- Added native desktop path authorization for user-selected locations and server-generated identifiers for new local resources.
- Prevented absolute-path and traversal inputs from escaping project storage boundaries.
- Hardened review-period file access, repository hygiene checks, GitHub Actions permissions, dependency review, and CodeQL scanning.
- Added path-security regression tests while preserving existing self-contained project and desktop workflows.

This is an unsigned security maintenance Beta. It supersedes `0.1.0-beta.1` for public testing but remains a pre-release and still requires an independent clean-machine test before a signed stable release.

## 0.1.0-beta.1 - 2026-07-18

- Added a self-contained, movable local project structure with backup and restore.
- Added storyboard image versions, final selection, approval locks, and overwrite protection.
- Added production-like pywebview/WebView2 startup on a random loopback port.
- Added project visual continuity locks, localized AI output constraints, and adjacent-shot merging.
- Added the Paneloom globe icon, Windows taskbar identity, and native window icon handling.
- Added frontend and Python lint, dependency auditing, repository hygiene checks, and CI preparation.

This is a local desktop beta. A traceable unsigned Windows Beta installer was validated on the development Windows 11 machine. The open-source release metadata includes CycloneDX SBOMs and the complete transitive dependency license inventory; code signing, remote CI execution, and an independent clean-machine test remain external release gates.
