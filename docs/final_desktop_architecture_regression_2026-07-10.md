# Paneloom Final Desktop Architecture Regression

Date: 2026-07-10 to 2026-07-11 local execution window

Scope: Windows local desktop architecture regression before packaging
Installer, package, Release, remote push, and publication: NOT PERFORMED

## 1. Executive Summary

The final desktop architecture regression passed. The production Vite build was loaded by pywebview/WebView2, FastAPI used a random `127.0.0.1` port, the rendered React application used the same runtime origin for `/health` and `/projects`, and no production bundle reference to port 8000 remained.

The measured cold-cache time to an actually interactive UI with the current 17 registered projects was 32.266 seconds, not 290 seconds. The earlier 290-second observation included shell/tool overhead and an older smoke process exit problem. A separate clean, zero-project profile became interactive in 20.656 seconds. The cold smoke released its Python process and listener in 40.547 seconds total; closing-to-process/listener-zero took 8.281 seconds.

Regression exposed and fixed two real architecture blockers:

1. Startup still created and mounted legacy `db/assets/exports` under the source directory. That could fail under a read-only installed location. Legacy storage is now read-only and conditionally mounted only when it exists.
2. Closing while a synchronous provider-backed FastAPI request was running could leave the launcher alive for more than 60 seconds. Shutdown now attempts graceful stop, then forces the local server boundary after a bounded wait, recovers `generating` shots to a retryable failed state, and releases the port.

One external acceptance item remains: no fresh paid image-provider call was authorized. Current text-provider acceptance is real; image request construction, HTTP transport boundary, persistence, versioning, failure, timeout, lock prevention, cancellation, and recovery were verified without charging a vendor. This external condition is not represented as a pass.

## 2. Final Gates

```text
HARDCODED_PRODUCTION_PORT = NO
DESKTOP_RUNTIME_API_URL_INJECTION = PASS
ALL_PRODUCTION_API_REQUESTS_USE_RUNTIME_ENDPOINT = YES

PRODUCTION_BUILD_DESKTOP_BOOT = PASS
NODE_REQUIRED_AT_RUNTIME = NO
MANUAL_BROWSER_REQUIRED = NO
MANUAL_BACKEND_START_REQUIRED = NO

BACKEND_READY_TIME = 4.484 seconds
FIRST_WINDOW_TIME = 28.859 seconds
FIRST_RENDER_TIME = 32.016 seconds
TIME_TO_INTERACTIVE = 32.266 seconds
CLEAN_SHUTDOWN_TIME = 8.281 seconds
TOTAL_SMOKE_DURATION = 40.547 seconds

PROJECT_PORTABILITY_FULL_E2E = PASS
PROJECT_BACKUP_INTEGRITY = PASS
PROJECT_RESTORE_INTEGRITY = PASS
BACKUP_CONTAINS_PLAINTEXT_SECRET = NO
RESTORE_OVERWRITES_EXISTING_PROJECT = NO

NORMAL_SHUTDOWN = PASS
ACTIVE_TASK_SHUTDOWN = PASS
INTERRUPTED_WRITE_RECOVERY = PASS
STALE_RUNNING_TASK_RECOVERY = PASS
GHOST_PROCESS_COUNT = 0
LEFTOVER_LISTENING_PORT_COUNT = 0

OFFLINE_DESKTOP_BOOT = PASS
OFFLINE_LOCAL_EDITING = PASS
OFFLINE_LOCAL_EXPORT = PASS
CLOUD_AI_OFFLINE_FAILURE_HANDLING = PASS

HISTORICAL_PROJECTS_ORIGINALS_PRESERVED = YES
HISTORICAL_MIGRATION_SAMPLE_VALIDATED = PASS

LOCAL_GIT_BASELINE = CREATED
PLAINTEXT_SECRET_IN_TRACKED_FILES = NO
USER_PROJECT_ASSETS_IN_TRACKED_FILES = NO

PROJECT_SCHEMA_VERSIONING = PASS
OLD_PROJECT_FORWARD_COMPATIBILITY = PARTIAL
SCHEMA_MIGRATION_REQUIRED_BEFORE_PACKAGING = NO

TEXT_AI_REAL_PROVIDER_VALIDATED = YES
IMAGE_AI_REQUEST_CONSTRUCTION_VALIDATED = YES
IMAGE_AI_REAL_PROVIDER_VALIDATED = EXTERNAL_BLOCKED
IMAGE_AI_RESULT_PERSISTENCE_VALIDATED = YES
IMAGE_AI_FAILURE_HANDLING_VALIDATED = YES
IMAGE_AI_TIMEOUT_HANDLING_VALIDATED = YES

FINAL_DESKTOP_ARCHITECTURE_REGRESSION = PASS
DESKTOP_LOCAL_BETA_READY = YES
PACKAGING_READY = YES
```

`PACKAGING_READY = YES` means only that a separate installer and clean-machine test phase may begin. It does not authorize or imply that an installer, Release, or public build was created in this stage.

## 3. Port 8000 Classification

| Location | Class | Finding |
| --- | --- | --- |
| `frontend/src/api.js` | A + C | Development defaults to `http://127.0.0.1:8000`; production uses `window.location.origin` unless an explicit build-time `VITE_API_BASE_URL` is supplied. |
| `.env.example` | A | Development example only. It is not automatically loaded by the backend or embedded in the production build. |
| `README.md` | A | Documents the browser development configuration. |
| `scripts/start_desktop_dev.ps1` | A | Browser/Vite developer launcher only. |
| `docs/user_guide_zh.md` | A | Developer/browser instructions. |
| `docs/StoryboardGenie_交接说明_2026-07-07.txt` | D | Historical handoff documentation, not executable production code. |
| `tests/acceptance_active_shutdown.py` | B | Uses a dynamically selected controlled-provider port, not fixed 8000. |
| Backend `*_BASE_URL` constants | external provider URLs | OpenAI/GLM/Google provider endpoints, unrelated to the local desktop port. |

No `localhost:8000` executable production reference was found. The final `frontend/dist` search returned `production_bundle_8000_matches=0`.

Observed WebView2 runtime evidence:

```text
window.location.origin       http://127.0.0.1:50966
Dashboard API_BASE text      http://127.0.0.1:50966
health request               http://127.0.0.1:50966/health
projects request             http://127.0.0.1:50966/projects
```

The previous screenshot showing `127.0.0.1:8000` therefore came from browser development mode or a development build-time variable. It is not the production-like desktop endpoint.

## 4. Startup and Shutdown Timeline

Authoritative cold-cache run with the current 17-project registry:

| Event | Seconds from launcher |
| --- | ---: |
| T0 launcher begins | 0.000 |
| T1 FastAPI startup begins | 0.281 |
| T2 FastAPI health ready | 4.484 |
| T3 WebView2 window shown | 28.859 |
| T4 React first render and backend online | 32.016 |
| T5 projects request complete and Projects navigation click succeeds | 32.266 |
| T6 close requested | 32.266 |
| T7 WebView closed | 32.391 |
| T8 FastAPI stopped | 33.312 |
| T9 launcher Python process zero | 39.931 |
| T10 listener check zero | 40.547 |

The smoke WebView2 helper process count reached zero 1.233 seconds after the post-check began. No Paneloom WebView2 process remained.

A clean zero-project profile also passed:

```text
backend ready       5.250 seconds
window shown       16.453 seconds
first render       20.578 seconds
interactive        20.656 seconds
backend stopped    21.281 seconds
```

The isolated three-launch E2E produced window-ready times of 15.234, 12.875, and 11.563 seconds. Normal close-to-process-exit measurements were 11.922, 10.157, and 12.328 seconds. These remain performance observations for clean-machine packaging regression, not hidden 290-second user startup.

## 5. Production Build Boundary

- Vite production build: PASS, 1,738 modules transformed.
- Vite dev server: not started.
- `frontend/dist` is served by the in-process FastAPI application.
- `scripts/start_desktop_production_like.ps1` starts only the prepared desktop Python runtime and launcher.
- Node/npm/Vite are not invoked by the production-like runtime.
- Uvicorn is created and managed in-process by `desktop/launcher.py`.
- Browser launch and localhost entry are not required.
- Random loopback host binding is `127.0.0.1`, not `0.0.0.0`.
- A prepared `.desktop-venv` is still required in this pre-package development boundary. Bundling the Python runtime belongs to the separate packaging phase.

## 6. AI Capability Matrix

| Capability in code | Classification | Evidence |
| --- | --- | --- |
| Base text provider | REAL_PROVIDER_VALIDATED | Current GPT relay/model performed one token-limited request and returned a non-empty response. |
| Story optimization | REQUEST_CONSTRUCTION_VALIDATED | Real text client, schema and local fallback are connected; no additional billed workflow call was made. |
| Bible/script analysis for characters, locations, props and style | REQUEST_CONSTRUCTION_VALIDATED | Real text client and structured parser are connected; offline fallback verified. |
| Storyboard breakdown and rewrite | REQUEST_CONSTRUCTION_VALIDATED | Real text client, local fallback and shot persistence are connected. |
| Character/location/prop/style reference concept generation | REQUEST_CONSTRUCTION_VALIDATED | Real image request path is connected; no paid concept generation was run. |
| Reference style analysis | REQUEST_CONSTRUCTION_VALIDATED | Real vision request path and local persistence are connected; no new paid call. |
| Panel image generation | EXTERNAL_BLOCKED for fresh vendor call | Current provider has historical successful records. This pass used real controlled HTTP twice, creating two distinct persisted versions. |
| Reference-image editing | EXTERNAL_BLOCKED for fresh vendor call | Request/multipart path exists and historical successful edits exist; no new paid edit. |
| Social screenshot metric extraction | REQUEST_CONSTRUCTION_VALIDATED | Real vision request path exists; offline mode returns an explicit manual-entry result. |

No AI capability is classified as mock-only UI. Local fallbacks are explicitly identified as local and are not reported as provider success.

Image boundary evidence without paid vendor use:

- Request model, prompt, size, quality, response format and `(30, 600)` connect/read timeout tuple asserted.
- Real local HTTP provider received two generation POSTs.
- Two distinct image files and two version records persisted.
- Selected version and lock state persisted after close/move/restart.
- Locked generation failed before the provider call.
- HTTP timeout maps to `request_timeout` and creates no final image.
- Partial multi-aspect failure preserves successful output without reporting full success.
- Background and synchronous long-request shutdown paths both recover to retryable failed state.

External blocker:

```text
EXTERNAL_ACCEPTANCE_BLOCKER = a fresh paid image-provider request requires explicit quota authorization
```

## 7. Full Project Portability E2E

The production-like desktop and real HTTP API created a disposable project containing:

- state A script;
- character, location and prop Bible content;
- character and scene PNG references;
- one storyboard shot;
- two HTTP-generated image versions with distinct files;
- explicit selected version;
- approved and locked state;
- valid JSON export;
- complete ZIP backup.

After normal close, the complete project directory was moved. A second production-like launch opened the moved directory through `/projects/open`. State B script, Bible, both references, both image versions, selected version, lock, generated bytes and export bytes all remained valid.

```text
PROJECT_PORTABILITY_FULL_E2E = PASS
```

## 8. Backup and Restore Integrity

The state A archive contained 19 manifest files totaling 16,350 bytes.

```text
missing files          0
extra files            0
size mismatches        0
SHA-256 mismatches     0
plaintext secrets      0
global logs/cache/temp 0
```

The source project was changed to state B after backup. Restore created a new project ID, retained the original state B project, and recovered state A script, image versions, selected version and lock state. A separately corrupted archive was rejected by size/checksum validation and registered no project or staging residue.

## 9. Shutdown, Crash and Recovery

| Scenario | Result | Evidence |
| --- | --- | --- |
| Normal close | PASS | Three native WM_CLOSE cycles, exit codes zero, ports released. |
| Background AI job during close | PASS | Controlled 120-second provider request; local job cancelled, shot failed/retryable, no `.tmp`, port and cache released. |
| Synchronous FastAPI/provider request during close | PASS after fix | Original run exceeded 60 seconds and failed. Bounded force-exit fix reduced shutdown to 11.296 seconds; restart recovered shot to failed. |
| JSON replace failure | PASS | Controlled `Path.replace` failure left original workspace/shots byte-identical and removed temp files. |
| Stale `generating` state on restart | PASS | Startup recovery changed it to failed with an understandable retry message. |

The third-party long request remained active remotely after local exit. The product does not claim vendor cancellation when the provider exposes no cancellation API.

Forced Uvicorn shutdown emits a captured `CancelledError` traceback to stderr in the test process. The production `pythonw` entry has no console and the message contains no secret. This is a residual log-quality issue, not a process, data or port leak.

## 10. Offline Acceptance

The third production-like launch used explicit offline mode and still:

- opened existing projects;
- created a new project;
- edited and reloaded script and Bible;
- created a storyboard shot;
- read historical generated image bytes;
- switched an image version;
- approved and locked the shot;
- generated and read a local export.

The cloud image job failed explicitly, did not remain loading, and did not call the controlled provider. Health returned `offline_mode=true` and `cloud_ai_available=false`.

## 11. Historical 17-Project Protection

Read-only inspection results:

```text
registered projects           17
preserved original directories 17
migrated portable directories  17
missing version files            0
```

Samples:

- Text storyboard sample: migrated and original shot counts both 1; prompt matched.
- Reference sample: one reference file, one valid image.
- Version sample: one version, file exists and image verifies.
- Export sample: six of six files parse or are non-empty in their expected formats.

Important limitation: none of the real 17 historical source projects contains a locked shot or selected-version marker, and none has non-empty `workspace.script`. Therefore a real locked historical sample does not exist to inspect. Lock/selection migration was instead verified with a copied legacy-format fixture containing an absolute image path, selected version and approved lock. This limitation is not represented as a real historical lock success.

No historical file was deleted or modified by the read-only sampling.

## 12. Local Git Baseline

Source backup before further changes:

```text
path     C:\Users\esthe\StoryboardGenie-source-baseline-20260710-233221.zip
files    101
bytes    241851
SHA-256  925B6F3A92615E73E375CD48CAAA3465720C587C48948966950C93BCFEF33795
```

Git baseline:

```text
branch        main
baseline      e7ee05923f38d958cb43211e8a6d589a73c99e2c
baseline time 2026-07-10T23:34:05+08:00
regression    74535814f5e99bed2cc22df7c7c34b96746fed70
regression time 2026-07-11T00:20:03+08:00
remote        none
```

`.gitignore` excludes the complete `db/` and `assets/` trees, exports, uploads, logs, environments, node modules, dist/build output, caches, temp/backup files, archives, SQLite files and all `.env*` files except `.env.example`.

The staged/tracked source scan found zero real key-pattern matches and zero forbidden user/runtime paths. Test strings such as `controlled-test-key` are non-secret fixtures and are not vendor credentials.

## 13. Schema and Upgrade Compatibility

- New projects store `schema_version=2` and `storage_format=self_contained`.
- The legacy-to-v2 migration is staged, backed up, source-preserving and idempotent.
- Missing workspace/Bible fields receive safe defaults.
- Unknown fields can be read without a crash.
- Pydantic ignores unknown request fields; an unknown future field may be dropped when an older application re-saves that object. Therefore forward compatibility is PARTIAL, not full round-trip preservation.
- A future schema version that changes or removes fields must add a new idempotent migrator before that version is released.
- No additional migration framework is required before packaging the current v2 schema.

## 14. Modified Files

| File | Regression reason |
| --- | --- |
| `.gitignore` | Exclude secrets, user projects/assets, logs, cache, environments and build/archive output before local Git creation. |
| `backend/app/config.py` | Make legacy source data read-only/optional and stop creating runtime data under the source/install directory. |
| `backend/main.py` | Mount legacy static directories only when they already exist. |
| `desktop/launcher.py` | Add measured T0-T8 smoke, runtime-origin/API probes, actual interaction, bounded forced shutdown and stopped-state details. |
| `backend/app/services/project_service.py` | Remove failed JSON temporary files while preserving the original. |
| `backend/app/services/shotlist_service.py` | Remove failed shot-write temporary files while preserving the original. |
| `tests/test_core_workflows.py` | Image request construction, atomic persistence and timeout classification. |
| `tests/test_project_portability.py` | Corrupt backup rejection, interrupted writes and schema compatibility. |
| `tests/acceptance_active_shutdown.py` | Isolate legacy source during background-task shutdown. |
| `tests/controlled_image_provider.py` | Non-billed real HTTP image response boundary. |
| `tests/acceptance_final_architecture.py` | Production-like HTTP/filesystem move, backup, restore, offline and repeated lifecycle E2E. |
| `tests/acceptance_inflight_request_shutdown.py` | Synchronous provider request close/restart recovery. |

All product changes are after the immutable local baseline commit and can be reverted to that commit without touching user project folders. No remote repository is configured.

## 15. Test Evidence

- `python -m compileall api backend desktop tests`: PASS.
- `python -m unittest discover -s tests -v`: 25/25 PASS.
- `npm run build`: PASS.
- `npm audit --audit-level=high`: 0 vulnerabilities.
- Cold current-profile WebView2 runtime/API/interaction timeline: PASS.
- Clean zero-project production-like WebView2 smoke: PASS.
- Three-launch full architecture E2E: PASS.
- Background long-task close: PASS.
- Synchronous in-flight request close/restart: PASS after bounded force-exit fix.
- Current text-provider minimal request: PASS, non-empty response.
- Fresh paid image-provider call: NOT RUN, EXTERNAL_BLOCKED.
- Formal package/installer/Release: NOT RUN by explicit prohibition.

## 16. Residual Risks

1. A fresh call to the configured paid image provider still requires explicit quota authorization.
2. Cold interactive startup with 17 projects is 32.266 seconds. It passes the requested 290-second guard but should be remeasured on the clean packaging test machine.
3. Normal process cleanup measured approximately 10 to 12 seconds in the isolated full E2E. Immediate window disappearance occurs earlier, but clean-machine packaging regression must verify repeat launch behavior and antivirus impact.
4. Vendor-side cancellation is provider-specific; local shutdown cannot retract a request already accepted by a provider without a cancellation endpoint.
5. Real historical data contains no locked-shot sample. The migration code path is covered by an isolated legacy fixture, not by inventing history.
6. The current phase validates a prepared Python runtime, not a bundled runtime, WebView2 bootstrapper or installer upgrade/uninstall behavior. Those belong to the next phase.

## 17. Packaging Decision

The architecture is allowed to enter a separate Windows installer and clean-machine validation stage.

```text
FINAL_DESKTOP_ARCHITECTURE_REGRESSION = PASS
DESKTOP_LOCAL_BETA_READY = YES
PACKAGING_READY = YES
```

No package, installer, Release or publication was created.
