# Paneloom Desktop Release Gate

This file is a gate, not evidence that a release may be created. `DESKTOP_LOCAL_BETA_READY = YES` only permits a separate final architecture regression phase; it does not authorize packaging, an installer, a Release, or publication.

## Required

- [x] LICENSE selected: MIT.
- [x] README explains project purpose, local-first design, BYO API key, alpha status, data locations, and privacy notes.
- [x] `.env.example` contains placeholders only and no real keys.
- [x] `npm audit` passes, or remaining vulnerabilities are documented.
- [x] Frontend build passes with `npm run build`.
- [x] Backend compile passes with `python -m compileall backend api`.
- [x] API keys are stored as Windows-user DPAPI ciphertext under `%LOCALAPPDATA%\Paneloom\config`.
- [x] `db/project_data.json` is ignored if present.
- [x] `db/projects/` is ignored so real user projects are not committed.
- [x] `assets/generated/` is ignored so generated images are not committed.
- [x] `assets/references/` is ignored so user reference images are not committed.
- [x] Legacy local asset folders such as `assets/reference_images/` and `assets/anchors/` are ignored.
- [x] `uploads/` is ignored if local uploads are added later.
- [ ] Five-language main UI pass: Simplified Chinese, Traditional Chinese, English, Japanese, Korean.
- [x] Native WebView2 smoke: random loopback port, React render, close, no residual launcher process/listener.
- [x] User-selected self-contained project folder with relative asset paths and verified legacy migration.
- [x] Whole-project checksum backup and non-destructive restore acceptance.
- [x] Atomic project writes and controlled long-request close/restart acceptance.
- [x] Production-like built-UI launch, single instance, native close, and port release acceptance.

## Real Generation Acceptance

- [ ] Text-to-image generation checked with a disposable panel.
- [ ] Reference image edit generation checked with a disposable reference image.
- [ ] Generated image appears in the browser.
- [ ] `versions` array increases after generation.
- [ ] Regeneration creates a new file rather than overwriting the previous one.

Status: current text provider was validated with one minimal request. Current paid image
generation was not re-run without explicit quota approval. This is an external acceptance
condition, not a code P0; it still must be completed before a formal release candidate.

## Known Issues

- Real image generation acceptance still needs an explicit quota-approved run.
- Repository snapshot contains no Git metadata, so ignored-file history cannot be verified.
- The pywebview shell is production-like architecture validation, not a distributable desktop build.
- WebView2 startup was functionally successful but unusually slow on the final validation machine.
- Controlled long HTTP shutdown is validated; vendor-specific remote cancellation remains provider-dependent.

DESKTOP_LOCAL_BETA_READY = YES

PUBLIC_SAAS_READY = NO
