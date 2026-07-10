# Design Notes

## System Goal

Paneloom is intended to become an open-source, local-first workspace for comic
panel planning and visual continuity: creative planning, project organization,
character and scene assets, shot list management, style locks, reference images,
logging, recovery, exports, and production feedback.

## Current MVP Structure

Milestone 1 keeps the system simple and file-based:

- `backend/`: FastAPI API service
- `frontend/`: Vite + React interface
- `api/`: OpenAI-compatible API clients
- `db/projects/`: local project folders
- `assets/generated/`: generated storyboard images
- `docs/`: architecture and API notes

Each project folder contains:

- `project_config.json`
- `shots.json`
- `generation_log.csv`
- `failed_jobs.csv`

Settings are stored in `db/settings.json` when saved through the UI. The file is
ignored by Git because it may contain local API credentials.

## Provider Configuration

API settings separate text and image models:

```json
{
  "provider_type": "official",
  "base_url": "https://api.openai.com/v1",
  "api_key": "",
  "text_model": "gpt-5.5",
  "image_model": "gpt-image-2",
  "image_size": "1024x1024",
  "image_quality": "low"
}
```

The backend reads saved settings first, then environment variables. API calls
receive an explicit config object instead of reading global environment values
inside the image client.

## Extension Direction

Milestone 2 should add:

- Batch generation queue with retry, failure review, and breakpoint resume
- Reference image upload and `/images/edits` UI
- Shot table import/export
- CSV / JSON / Excel / SRT export
- A durable task log format that can support 1000+ shots
- Electron shell startup and packaging

Later milestones can add multi-turn planning, prompt versioning, character and
scene bibles, PDF export, and richer text-model workflows.
