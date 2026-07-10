# Paneloom Windows Desktop Beta P0 Closure

Date: 2026-07-10  
Scope: P0-A through P0-F only  
Packaging, installer, Release, and publication: not performed

## Decision

The code P0 items blocking a local Windows desktop beta are closed. One paid image-provider acceptance remains externally blocked because no new image-spend authorization was given. This is not classified as a code defect and does not authorize packaging.

| Gate | Result | Evidence |
| --- | --- | --- |
| P0-A self-contained project | PASS | New projects own metadata, workspaces, references, generated versions, exports, and backups. All 17 registered projects validate as portable. |
| P0-B relative paths and migration | PASS | Project-internal paths are relative/resolved from the project root. Legacy migration is staged, backed up, logged, repeatable, and source-preserving. |
| P0-C backup and restore | PASS | ZIP snapshot uses a manifest, file sizes, SHA-256 checksums, safe-path validation, and restores as a new project without overwriting the source. |
| P0-D desktop runtime boundary | PASS | Built Vite UI loaded in WebView2 on random loopback port; React rendered; single-instance and native close behavior verified; launcher and listener count returned to zero. |
| P0-E real AI acceptance | EXTERNAL_BLOCKED | One minimal current text-provider request returned HTTP 200. A new paid image request was not authorized; historical logs contain successful calls to the currently configured image provider. |
| P0-F active-task shutdown | PASS | Actual desktop window + actual FastAPI generation job + controlled 120-second HTTP provider: native close interrupted local state, released the port, left no temp file, and restart showed a comprehensible failed state. |

## P0-A and P0-B: Project Boundary

New/default project structure:

```text
<user-selected folder>/<project-name>-<project-id>/
  project_config.json
  workspace.json
  shots.json
  project_bible.json
  story_optimization.json
  planning.json
  schedule.json
  generation_log.csv
  social_feedback.csv
  assets/references/
  generated/
  exports/
  backups/
  metadata/
```

`%LOCALAPPDATA%/Paneloom` now contains only application settings/DPAPI secrets, the project registry, logs, cache, temporary files, and migration records. The default creative-data location is `Documents/Paneloom Projects`, but creation/opening can use a user-selected directory.

Migration results for the real project set:

- Projects discovered: 17.
- Projects passing portable-project validation: 17.
- Missing referenced assets after migration: 0.
- Registry entries: 17.
- Original legacy project directories retained: 17.
- Re-running migration produced 17 already-migrated results and no duplicate migration.
- Failed staging attempts did not replace or delete source data.

Historical-project impact: additive only. Each legacy source remains available, and migration creates a pre-migration ZIP before registering the new self-contained copy. Rollback is to remove the registry entry for the migrated copy and re-open the preserved legacy source; no legacy file must be reconstructed.

## P0-C: Backup and Restore

`Backup Project` is a real UI action backed by `POST /api/projects/{id}/backup`. Backups include project metadata, script/workspaces, Bible, references, storyboards, generated image versions, selected/lock state, and exports by default. `Restore Project` verifies the manifest and every checksum, extracts to staging, assigns a new project ID, and atomically publishes the restored directory. It never silently overwrites the current project.

Acceptance: create state A -> backup -> change to state B -> restore -> restored project contains A and its locked selected image; original project remains at B.

Rollback: backup/restore never mutates the archive or source project. A failed extraction leaves the source intact and does not register staging data.

## P0-D: Desktop Runtime

`scripts/start_desktop_production_like.ps1` starts `desktop/launcher.py` through the prepared desktop Python runtime. It does not start npm, a Vite dev server, an external uvicorn command, a browser, or a fixed localhost URL. The launcher serves the built `frontend/dist`, starts FastAPI on a random `127.0.0.1` port, opens WebView2, rejects a second instance, and stops the service on close.

Final native-window smoke:

```json
{"ok":true,"host":"127.0.0.1","port":63248,"window_loaded":true,"react_root_rendered":true,"server_stopped":true}
```

Post-check: launcher processes `0`; listeners on port `63248`: `0`. The smoke harness was corrected to return a nonzero code on render failure and to terminate its own residual WebView2 cache worker after the window/server have stopped. No installer was created.

The final smoke took 290 seconds on this machine. This is a measured performance concern, not a false pass: the window rendered and all lifecycle postconditions passed.

## P0-E: AI Capability Matrix

| Capability | State | Basis |
| --- | --- | --- |
| Base text provider | A | Current provider, one minimal token-limited request, HTTP 200 and non-empty output. |
| Story optimization | B | Real client/request construction; not separately billed in this pass. |
| Bible extraction | B | Real client/request construction; not separately billed in this pass. |
| Storyboard breakdown | B | Real client/request construction; not separately billed in this pass. |
| Current image generation | A historically / external current check blocked | Current provider has 9 historical successes; no new high-quality image charge authorized. |
| Reference-image edit | A historically | Five persisted successful reference-edit jobs. |
| Reference concept generation | B | Real image client path, no new billed acceptance. |
| Reference style analysis | B | Real vision request path plus local fallback; no new billed acceptance. |
| Social screenshot analysis | B | Real vision request path; no new billed acceptance. |

Offline behavior is explicit: local startup, project/script/storyboard edits, historical images, and local exports remain available; cloud AI routes report or use an explicit offline fallback and do not call providers.

`AI_REAL_PROVIDER_VALIDATED = EXTERNAL_BLOCKED` means the current text provider is validated but a fresh paid image call remains an external acceptance condition. It is not being represented as passed.

## P0-F: Active Request Shutdown

Acceptance result:

```json
{
  "job_started": true,
  "shot_reached_generating": true,
  "provider_received_request": true,
  "native_windows_closed": 1,
  "active_jobs_interrupted": true,
  "remote_provider_still_running_after_local_exit": true,
  "local_port_released": true,
  "restored_shot_status": "failed",
  "restored_shot_has_error": true,
  "temporary_files": 0,
  "webview_cache_released": true
}
```

The shutdown policy does not claim remote cancellation. It stops accepting local work, persists an interrupted/failed local state, closes the local HTTP client/process boundary, releases the loopback port, and allows a clean restart. A third-party request already received by a provider may continue remotely unless that provider exposes a cancellation API.

## Modified Files

| Files | Reason | Historical-data impact / rollback |
| --- | --- | --- |
| `backend/app/config.py`, `backend/app/models/schemas.py` | LocalAppData registry, default projects home, path/backup/restore requests, explicit offline mode. | Configuration-only; old data is not removed. |
| `backend/app/services/project_service.py` | Self-contained creation, registry resolver, moved-project reopen, whole-project copy/delete behavior, project-relative file resolution. | Legacy lookup remains as fallback; registry can be removed to fall back. |
| `backend/app/services/project_portability_service.py` | Staged legacy migration, pre-backup, manifest/checksum backup, non-destructive restore. | Additive migration; source and migration backup remain rollback points. |
| `backend/app/services/image_service.py`, `shotlist_service.py`, `export_service.py` | Project-local references/generated/exports, relative stored paths, resolver URLs, offline guard. | Compatibility resolver reads migrated and legacy forms; generated files are copied, not deleted. |
| `backend/app/services/story_optimization_service.py`, `bible_analysis_service.py`, `planning_service.py`, `social_feedback_ocr_service.py` | Explicit offline behavior without blocking local editing. | No schema-destructive change. |
| `backend/app/routes/projects.py`, `backend/main.py` | Open/migrate/backup/restore/native-dialog/file-serving APIs and offline health. | Safe-path checks prevent escaping a project root. |
| `api/openai_text_client.py` | Optional output-token cap for minimal-cost provider acceptance. | Backward-compatible optional argument. |
| `frontend/src/api.js`, `ProjectEditor.jsx`, `App.jsx`, `StoryboardPage.jsx`, `i18n.jsx`, `styles/global.css` | Real create/open/migrate/backup/restore entries and explicit offline state. | UI only invokes non-destructive backend operations. |
| `desktop/launcher.py`, `scripts/start_desktop_production_like.ps1` | Runtime state, startup errors, built-UI launch, clean smoke exit. | No project-data mutation. |
| `tests/test_project_portability.py`, `tests/controlled_long_provider.py`, `tests/acceptance_active_shutdown.py` | Project move, migration, backup/restore, offline, and active-close acceptance. | Tests use isolated temporary roots and clean their artifacts. |
| `README.md`, `docs/release_checklist.md`, this report | Replace obsolete global-storage claims with verified boundaries and gates. | Documentation only. |

## Verification

- Python compile: PASS (`python -m compileall backend desktop tests`).
- Core workflows: 12/12 PASS.
- Portability/backup/offline: 4/4 PASS.
- Desktop runtime: 4/4 PASS.
- Total automated tests: 20/20 PASS.
- Vite production build: PASS, 1,738 modules transformed.
- `npm audit --audit-level=high`: PASS, 0 vulnerabilities.
- Real project validation: 17/17 portable.
- Production-like WebView2 smoke: PASS; React rendered, server stopped, process/listener counts zero.
- Active long-request native-close acceptance: PASS.
- Formal installer/package/Release: NOT RUN, intentionally prohibited.

## Final Gates

P0-A self-contained project: PASS  
P0-B relative paths and migration: PASS  
P0-C backup and restore: PASS  
P0-D desktop runtime boundary: PASS  
P0-E real AI acceptance: EXTERNAL_BLOCKED  
P0-F active-task shutdown: PASS

PROJECT_SELF_CONTAINED = YES  
PROJECT_MOVABLE = YES  
PROJECT_BACKUP_RESTORE = YES  
DESKTOP_PRODUCTION_LIKE_LAUNCH = YES  
DESKTOP_CLEAN_SHUTDOWN = YES  
AI_REAL_PROVIDER_VALIDATED = EXTERNAL_BLOCKED  
ACTIVE_TASK_SHUTDOWN_VALIDATED = YES

EXTERNAL_ACCEPTANCE_BLOCKER = fresh paid image-provider request requires explicit quota authorization

DESKTOP_LOCAL_BETA_READY = YES  
PUBLIC_SAAS_READY = NO

This gate permits the separate final desktop architecture regression phase. It does not permit or imply a formal installer, Release, or publication.
