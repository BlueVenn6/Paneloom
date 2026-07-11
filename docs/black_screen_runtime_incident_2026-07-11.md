# Paneloom desktop black-screen incident - 2026-07-11

## Gate status

- Pre-fix commit: `fff96ac29490d2e6355bf1cfdab4bb817f5bfe7a`
- User-reported manual acceptance status at incident discovery: `FAIL`
- Packaging allowed: `NO`
- The fix does not constitute user acceptance. Manual acceptance returns to `PENDING` only after the regression gates below pass.

## Observed boundary

The failure happened while the application was already running. The native pywebview/WebView2 window remained visible and responsive, but navigation and all React page content disappeared, leaving only the global dark body background. The user identified the schedule/review area as a trigger.

The original user session did not have frontend runtime diagnostics enabled, so its exact previous route and last click could not be reconstructed after the render tree had already been removed. A production-build WebView2 reproduction established the minimum deterministic sequence:

1. Start the production desktop UI.
2. Keep a project with no saved weekly or monthly review selected.
3. Navigate through the application to `#schedule`.
4. Wait for `GET /projects/{project_id}/schedule` to complete.
5. The React root becomes empty and all five navigation entries disappear.

## Root cause

`get_schedule()` correctly returned empty review placeholders:

```json
{"reviews":{"week":{},"month":{}}}
```

`SchedulePage` used `data.reviews?.week || data.reviews?.month || null`. In JavaScript an empty object is truthy, so `review` became `{}`. Rendering then executed `review.advice.map(...)`; `advice` was undefined and React raised:

```text
TypeError: Cannot read properties of undefined (reading 'map')
```

There was no React Error Boundary. React therefore unmounted the complete application root, producing the observed dark blank window.

## Pre-fix evidence

- Production WebView2 URL at failure: `http://127.0.0.1:64185/?desktop-test=1#schedule`
- `document.readyState`: `complete`
- React mounted flag: `true`
- Root children before schedule: `1`
- Root children after schedule: `0`
- Navigation entries before schedule: `5`
- Navigation entries after schedule: `0`
- Main bundle loaded: `YES`
- CSS loaded: `YES`
- Static asset failures: `0`
- Chunk load failure: `NO`
- Unhandled promise rejection: `NO`
- Backend health during the user's black screen: `YES`
- `/projects` during the user's black screen: `YES`
- Schedule API during reproduction: `YES`

The captured pre-fix artifact is `%TEMP%\paneloom-black-screen-before-fix.json`. It contains no project text, request body, or credentials.

## Fix

- Normalize schedule response collections and treat empty/invalid review values as no review.
- Defensively render advice only when it is an array.
- Add a page-level Error Boundary that preserves the application shell and offers retry and return-to-dashboard actions.
- Add a root Error Boundary as a final recovery surface.
- Add desktop-test-only, in-memory browser diagnostics for `console.error`, `window.onerror`, `unhandledrejection`, and React render exceptions.
- Persist only sanitized diagnostic fields in `%LOCALAPPDATA%\Paneloom\logs\frontend-runtime.log` when the explicit desktop test launcher is used.
- Add a production WebView2 regression driver for all five routes, project switching, controlled fetch failure, offline UI, focus/window transitions, and Error Boundary recovery.

## Regression evidence

- Vite production build: `PASS` (`1740` modules)
- Python compileall: `PASS`
- Python tests: `27/27 PASS`
- Single WebView2 post-fix route run: `PASS`
- Ten WebView2 runs: `PASS`
- Total route transitions in the ten-run test: `50`
- Schedule route passes: `10/10`
- Window maximize/restore/minimize/restore cycles: `10/10`
- Project switch: `PASS`
- Controlled fetch failure keeps UI mounted: `PASS`
- Simulated offline UI: `PASS`
- Page render failure fallback visible: `PASS`
- Navigation preserved during page failure: `PASS`
- Return to dashboard recovery: `PASS`
- Global render failure fallback visible: `PASS`
- Global fallback reloads the same WebView to the dashboard: `PASS`
- Static asset failures: `0`
- Main bundle loaded: `YES`
- CSS loaded: `YES`
- Local test service stopped after each completed regression: `YES`

Post-fix artifacts:

- `%TEMP%\paneloom-black-screen-after-fix-1.json`
- `%TEMP%\paneloom-black-screen-after-fix-10.json`
- `%TEMP%\paneloom-black-screen-after-fix-final-10.json`

## Environment note

The first post-fix attempt exposed a test-driver defect: window maximize/minimize calls were made from the pywebview loaded-event callback and could block its GUI loop. The driver now runs UI work on a dedicated worker thread. The Windows session also retained Node/WebView2 processes after timed-out attempts; these test processes were cleared before the successful regressions. Neither condition modified project data.

## Final incident gates

```text
FRONTEND_RUNTIME_EXCEPTION = YES (pre-fix), NO (post-fix except controlled boundary probe)
UNHANDLED_PROMISE_REJECTION = NO
CHUNK_LOAD_FAILURE = NO
REACT_ROOT_MOUNTED = YES
BACKEND_HEALTHY_DURING_BLACK_SCREEN = YES
MAIN_BUNDLE_LOADED = YES
DYNAMIC_CHUNKS_LOADED = NOT_APPLICABLE (no lazy route chunks)
STATIC_ASSET_FAILURE_COUNT = 0

ROUTE_OVERVIEW = PASS
ROUTE_PROJECTS = PASS
ROUTE_STORYBOARD = PASS
ROUTE_SCHEDULE_REVIEW = PASS
ROUTE_MODEL_SETTINGS = PASS

BLACK_SCREEN_REPRODUCED_BEFORE_FIX = YES
BLACK_SCREEN_REPRODUCED_AFTER_FIX = NO
BLACK_SCREEN_REGRESSION_10_RUNS = PASS
GLOBAL_ERROR_BOUNDARY = PASS
PAGE_FAILURE_RECOVERY = PASS

FUNCTIONAL_ACCEPTANCE_READY_FOR_USER = YES
USER_MANUAL_FUNCTIONAL_ACCEPTANCE = PENDING
PACKAGING_ALLOWED = NO
```
