# Paneloom / StoryboardGenie Delivery Audit

> Superseded for product positioning and delivery gating by `desktop_local_audit_2026-07-10.md`. The product target is Windows local desktop, not Web SaaS.

Audit date: 2026-07-10  
Audit scope: source, runtime data shape, HTTP API, browser rendering, build, tests, and delivery gate  
Release/package actions: none

## 1. Project Status

The repository is a working local-first alpha, not a delivery-ready AI comic platform.
It has a real FastAPI/React workflow, local project persistence, document parsing,
model clients, reference-image generation/edit paths, image version storage, exports,
and production review data. It is strongest for a single creator preparing AI comic
panels or narrated vertical-comic assets.

The remaining delivery blockers are live provider acceptance, public-Web security and
user isolation, plaintext local credentials in a snapshot with no Git history, and an
insufficiently structured continuity/asset model for a professional multi-project product.

## 2. Technical Architecture Map

| Area | Confirmed implementation |
| --- | --- |
| Frontend | React 19.2.6, Vite 8.1.3, JavaScript/JSX, Lucide icons |
| Backend | Python 3.12 runtime used for audit, FastAPI 0.116.1, Uvicorn |
| Database | No database; per-project JSON and CSV files |
| ORM | None |
| State | React hooks; project/language in localStorage; creative workspace in backend JSON |
| Routing | URL hash navigation in frontend; FastAPI APIRouter modules |
| File storage | Local `db/projects/<project_id>/` with atomic JSON replacement and backups |
| Image storage | Local `assets/generated/<project_id>/` and `assets/references/<project_id>/` |
| AI text | Direct HTTP clients for OpenAI-compatible, GLM, and Gemini-native modes |
| OCR | No scanned-PDF OCR; social screenshots use a multimodal text/vision model |
| Documents | TXT, MD, SRT, CSV, text PDF, DOCX, EPUB, basic RTF, HTML, XLSX |
| Image generation | OpenAI-compatible `/images/generations` and `/images/edits` |
| Export | JSON, CSV, XLSX, SRT, HTML, browser canvas PNG grid, image download |
| Authentication | None |
| User isolation | None; this is a single-user local application |
| Project isolation | Validated project IDs and separate project/asset/export directories |
| Desktop | No Tauri/Electron shell; PowerShell only starts local Web dev services |
| Mobile | No app; responsive Web CSS only |
| Deployment | Manual local Uvicorn + Vite; no production server/container/deployment config |
| Tests | Standard-library unit/integration tests plus document smoke test |
| Build | `compileall` and Vite production build |
| Environment | Settings JSON or process environment; `.env` is not auto-loaded |
| Logs | Uvicorn console plus per-project generation/failure/time/publishing CSV files |
| Errors | HTTP errors and UI messages; provider failures persisted; no centralized observability |
| Concurrency | In-process project/shot/log locks; not safe for multiple backend processes |

## 3. Core Business Flow

```text
Single local operator (no account/auth)
  -> Project directory
     -> workspace.json
        -> current script -> script snapshots -> optimization result -> generation preferences
     -> project_bible.json
        -> style -> characters -> locations -> props -> world rules
     -> references/<project_id>/
        -> uploaded/generated character, location, prop, and style images
     -> shots.json
        -> panel description/prompt/notes/status
        -> generated outputs -> versions -> selected version
     -> generated/<project_id>/
        -> local panel image files
     -> exports/<project_id>/
        -> JSON/CSV/XLSX/SRT/HTML
     -> schedule.json + tasks.json + CSV logs + review JSON
        -> plan -> manual work log -> manual/social screenshot metrics -> recap
```

There is no separate Story, Character, Scene, Prop, Layout, Publication, User, or
organization entity. Characters/locations/props are editable project-level text plus
reference files. Scene IDs are strings on shots. Publishing is manual metric logging,
not platform delivery.

## 4. Completed Functions (A)

- Project create, reopen, rename, archive flag, duplicate creative content, recoverable delete.
- Project-scoped script persistence, import metadata, undo snapshots, and generation preferences.
- Local non-AI script breakdown, shot CRUD/reorder/edit, project Bible persistence.
- Real parsers for the supported text/document formats listed above.
- Reference upload validation, generated reference concepts, style extraction fallback.
- Real model HTTP clients, error classification, timeout, failure log, and retry on timeout.
- Generated image files, multi-aspect outputs, version history, current-version selection.
- JSON/CSV/XLSX/SRT/HTML exports and a real browser-generated PNG grid.
- Schedule/task/time/feedback persistence and latest-snapshot review calculations.
- Settings persistence, both-key response masking, and business-result-aware connection test UI.

## 5. Partially Completed Functions (B/C)

- AI story optimization: persisted accept/reject/undo exists; no visual diff or partial accept.
- Character consistency: Bible text and image references reach prompts/edits; no per-character entity,
  shot assignment, pose sheet, turnarounds, or measurable identity consistency.
- Scene/prop continuity: project text and references exist; no structured searchable entities.
- Image generation: single/batch queue and retry exist; running requests cannot be cancelled,
  jobs are process-memory only, and no cost estimate/budget/rate policy exists.
- Image versions: selectable, but no compare view, labels, approval/lock state, or cleanup policy.
- Comic layout: fixed grid canvas only; no templates, speech/narration boxes, typography,
  safe areas, custom panel geometry, or print/PDF output.
- Production archive: shows saved current script, references, and selected outputs; it is not a
  searchable immutable archive of every asset/version.
- Project deletion: recoverable on disk, but no restore UI/API.
- Five languages: fallback prevents missing labels, but newly added commands are not fully localized.

## 6. False UI

No confirmed core pure-UI button remains after repair. Two false-completion cases were removed/fixed:

- A failed model connection test previously displayed success.
- “Generate image” and “Generate with references” previously executed the same selected-reference path.

The remaining risk is naming/expectation: “archive” and “asset library” are limited project views,
not full asset-management systems. Social platform names are metric categories, not publish buttons.

## 7. Broken or Incomplete Flows

- Hosted Web: no login, tenant boundary, access control, remote object storage, or worker service.
- Pro continuity: script extraction does not produce editable character/scene/prop entities linked to shots.
- Professional storyboard: dialogue, narration, character assignment, camera, composition, lighting,
  approval/lock, and production state remain mostly embedded in free text.
- Layout: generated panels cannot enter a real lettering/layout editor.
- AI job lifecycle: browser queue can stop pending items, but a submitted provider request cannot be cancelled.
- Scanned PDF: rejected with an honest OCR-required error; no OCR workflow exists.

## 8. Remaining P0 Issues

1. Live text generation, text-to-image, and reference-edit acceptance were not run after repair because
   provider quota use was not explicitly approved. Core AI delivery therefore cannot be certified.
2. A public/multi-user Web deployment would expose all local projects because authentication and user
   isolation do not exist.
3. `db/settings.json` contains local credentials in plaintext. API responses are now masked, but at-rest
   secret storage is not hardened and this snapshot has no Git metadata to audit secret history.
4. The workspace contains real project/asset/export data. It is ignored by the supplied Git rules, but a
   clean source-release boundary cannot be proven without Git metadata and a sanitized release process.

## 9. Remaining P1 Issues

- Provider jobs are not durable across process restart; shots recover to retryable failure instead of resume.
- Running image calls have a ten-minute timeout but no cooperative cancellation.
- JSON/CSV persistence is single-process only and not suitable for hosted collaboration or 1000+ active shots.
- Asset search/filter/tags/provenance/dependency UI and cross-project reuse are absent.
- Schedule tasks are not automatically linked to actual shot/image approval state.
- Layout/lettering and platform-ready export packages are absent.
- No local scanned-PDF OCR, offline model, GPU pipeline, or filesystem watcher.
- No full five-language regression pass or accessibility automation.

## 10. P2 Issues

- `StoryboardPage.jsx` and `i18n.jsx` remain large and expensive to maintain.
- The mobile responsive page is long and navigation-heavy even though clipping was fixed.
- Some backend direct/synchronous endpoints are retained for API use but have no current frontend consumer.
- Error messages mix localized UI text with provider/backend English text.
- No configured frontend linter or static type checker; build is the available JSX syntax gate.

## 11. Automatically Fixed

- Persisted scripts, optimization output, undo snapshots, and per-project generation preferences.
- Added project rename, duplicate, archive, recoverable delete, and URL hash page restoration.
- Masked text API key; corrected failed connection-test success message.
- Blocked Windows path traversal through project IDs.
- Added atomic JSON writes, backups, corruption refusal, locks, and interrupted-generation recovery.
- Fixed schedule low-capacity infinite loop and social snapshot double counting/best-platform logic.
- Added provider timeouts, job validation/pruning, partial multi-aspect result preservation.
- Added real image validation/size limits and bounded document/screenshot uploads.
- Added Gemini-native image input, structured props/world rules, version selection, queue stop.
- Fixed cross-origin configuration, mobile topbar clipping, CSV formula injection, numeric validation.
- Removed empty components/scripts, unused dependency, stale duplicate frontend API wrappers.
- Pinned frontend/backend dependencies and corrected false release checklist state.

## 12. Unresolved

The P0/P1 items in sections 8 and 9 remain. No package, installer, deployment, or release was created.

## 13. Asset Accumulation Assessment

Current MVP value: project Bible, project references, prompt/style lock, generated image versions,
selected final version, and script snapshots. These are real and project-scoped.

MVP next: structured character/location/prop records, per-shot links, tags/search, provenance,
dependency-aware delete, and reusable project-template copy. Later: optional cross-project library,
pose/expression/clothing variants, layout templates. Avoid building a global DAM or marketplace now.

## 14. Social Media Assessment

Current code does not directly publish and does not fake publication. It records manual metrics and can
extract visible metrics from a screenshot through a vision model.

Recommended MVP: B + C + D + E: export platform-adapted packages, generate editable title/description/tags,
resize/crop with safe-area preview, and keep manual publication records. Do not implement direct platform APIs
until one or two user-validated platforms justify OAuth, review, policy, and maintenance costs.

## 15. Schedule/Review Assessment

This is a real but separate creator operations tool, not pure UI. It generates tasks, records time/blockers,
stores feedback snapshots, and produces week/month reviews. It should be redefined as production control:
shot completion, failed generation, revision needed, approved/locked, export ready, and publish plan.
Automatic linkage to shot status is the highest-value next change.

## 16. Web Recommendation

Keep Web as the primary product surface. It already supports the full local creative flow and is fastest to
iterate. Keep the backend bound to localhost for the current product. Before hosted Web, replace file storage
with a transactional database/object storage, add authentication/tenant authorization, durable workers,
quotas, secret management, observability, and backups.

## 17. Windows Recommendation

Do not build or package a Windows shell now. The current PowerShell launcher is not a desktop app.
Prefer PWA improvements first. Consider Tauri later only when it delivers concrete value: OS credential vault,
managed local backend, folder watching, large-file/OCR workers, local models/GPU, offline queue, and autosave.
Electron is not justified for a wrapper-only build.

## 18. Mobile Recommendation

Mobile is worth doing later, not now, and only as a companion. Include project/status viewing, idea/script
capture, review of generated images, A/B/final selection, approve/reject/comment, simple regenerate, and task
progress. Exclude bulk editing, advanced prompt engineering, large asset management, API-key setup, model
administration, and precision layout/lettering.

## 19. Functions to Delete or Avoid

- Do not add fake direct-publish platform icons or “publish success” simulation.
- Do not market the browser launcher as a Windows desktop application.
- Archive or remove historical handoff/milestone documents after their useful facts move into maintained docs.
- Avoid a second synchronous frontend generation path; keep one observable job flow.

## 20. Functions to Add Next

1. Structured characters/locations/props plus per-shot assignment and prompt assembly.
2. Shot approval/lock/revision state linked to schedule tasks.
3. Durable job queue with cancellation, retry policy, rate/cost limits, and restart recovery.
4. Image compare/final selection and asset metadata/search/provenance.
5. Basic lettering/layout editor and platform export package.
6. Secure OS credential storage for local mode; auth/tenant storage only if hosted Web is chosen.

## 21. Functions to Delay

- Direct social API publishing.
- Full cross-project enterprise DAM.
- Full mobile editor.
- Tauri/Electron packaging.
- Collaborative studio roles, comments, and approvals until hosted architecture is selected.
- Local GPU/model support until the Web workflow and target model stack stabilize.

## 22. Code Quality Score

68 / 100. The core is understandable and now has meaningful tests and safer persistence, but large modules,
file-database limits, incomplete observability, and no lint/type system reduce maintainability.

## 23. Product Completeness Score

56 / 100. A solo-creator local pipeline exists; professional continuity entities, lettering/layout,
collaboration, and durable AI operations do not.

## 24. User Experience Score

67 / 100. The workflow is visible, errors and empty states exist, persistence and mobile clipping are fixed.
The storyboard page remains long/dense and advanced creator decisions are still free-text heavy.

## 25. Delivery Readiness Score

42 / 100. Builds and non-provider flows pass, but the P0 gates in section 8 prevent delivery certification.

## 26. Delivery Gate

`DELIVERY_READY = NO`

This product cannot be delivered now.

## Verification Evidence

- `python -m unittest discover -s tests -v`: 11/11 passed.
- `python -m backend.app.services.test_document_import_service`: passed.
- `python -m compileall -q backend api tests`: passed.
- `npm run build`: passed with Vite 8.1.3.
- `npm audit`: 0 vulnerabilities.
- Real HTTP disposable-project flow: create, workspace reopen, isolation, local breakdown, shot edit,
  Bible save, five exports, duplicate, archive, document upload, key masking, path rejection: passed.
- Chrome screenshots at 1440x1000 and 390x844: rendered; persisted script visible; mobile clipping fixed.
- No live provider call was made and no release/package/deployment action was performed.
