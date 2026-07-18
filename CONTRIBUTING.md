# Contributing to Paneloom

Thanks for helping improve Paneloom.

## Setup

Install backend dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install --upgrade pip==26.1.2
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
```

Install frontend dependencies:

```powershell
cd frontend
npm ci
```

Run locally:

```powershell
.\scripts\start_desktop_dev.ps1
```

## Verification

Before submitting a pull request, run:

```powershell
python -m ruff check backend api desktop scripts tests
python -m compileall backend api desktop scripts
python -m unittest discover -s tests -p "test_*.py" -v
python scripts\check_repository_hygiene.py
cd frontend
npm run check
npm audit --audit-level=high
cd ..
python -m pip_audit -r backend\requirements.txt --progress-spinner off
```

## Issues

When opening an issue, include:

- What you expected to happen.
- What actually happened.
- Your OS and browser.
- Whether you used official OpenAI or a compatible relay.
- Any visible error message, without API keys.

## Pull Requests

- Keep changes focused.
- Do not commit `db/settings.json`, generated images, exports, or API keys.
- Avoid changing local data paths unless migration is included.
- Keep internal API paths backward-compatible when possible.

## i18n Rules

Paneloom currently supports Simplified Chinese, Traditional Chinese, English, Japanese, and Korean.

- User-facing text must go through `frontend/src/i18n.jsx`.
- Add all five languages for new UI strings.
- Keep platform names such as Reels, Shorts, TikTok, YouTube Shorts, 小红书, and B站 as product terms.
- Technical logs may stay in English when they are not shown directly to users.
