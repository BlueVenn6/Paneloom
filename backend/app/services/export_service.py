import csv
import json
import zipfile
from html import escape
from pathlib import Path

from backend.app.services.project_service import (
    get_project,
    get_project_bible,
    get_project_export_dir,
    project_file_url,
    require_project,
)
from backend.app.services.shotlist_service import list_shots


def export_project(project_id: str, export_format: str = "json") -> dict:
    project = require_project(project_id)
    shots = list_shots(project_id)
    bible = get_project_bible(project_id)
    output_dir = get_project_export_dir(project_id)
    output_dir.mkdir(parents=True, exist_ok=True)

    if export_format == "csv":
        path = output_dir / "storyboard.csv"
        _export_csv(path, shots)
    elif export_format == "xlsx":
        path = output_dir / "storyboard.xlsx"
        _export_xlsx(path, shots)
    elif export_format == "srt":
        path = output_dir / "storyboard.srt"
        _export_srt(path, shots)
    elif export_format == "html":
        path = output_dir / "manga_storyboard.html"
        _export_html(path, project, bible, shots)
    else:
        path = output_dir / "storyboard.json"
        path.write_text(
            json.dumps(
                {"project": get_project(project_id), "bible": bible, "shots": shots},
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

    return {
        "format": export_format,
        "path": f"exports/{path.name}",
        "url": project_file_url(project_id, "exports", path.name),
    }


def _export_csv(path: Path, shots: list[dict]) -> None:
    fieldnames = [
        "shot_id",
        "scene_id",
        "visual_description",
        "prompt",
        "negative_prompt",
        "revision_notes",
        "status",
        "output_url",
    ]
    with path.open("w", newline="", encoding="utf-8-sig") as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for shot in shots:
            writer.writerow(
                {
                    key: _safe_spreadsheet_text(shot.get(key, ""))
                    for key in fieldnames
                }
            )


def _export_xlsx(path: Path, shots: list[dict]) -> None:
    headers = [
        "shot_id",
        "scene_id",
        "visual_description",
        "prompt",
        "negative_prompt",
        "revision_notes",
        "status",
        "output_url",
    ]
    rows = [headers] + [[str(shot.get(header, "")) for header in headers] for shot in shots]
    sheet_rows = []
    for row_index, row in enumerate(rows, 1):
        cells = []
        for col_index, value in enumerate(row, 1):
            cell_ref = f"{_column_name(col_index)}{row_index}"
            cells.append(
                f'<c r="{cell_ref}" t="inlineStr"><is><t>{escape(value)}</t></is></c>'
            )
        sheet_rows.append(f'<row r="{row_index}">{"".join(cells)}</row>')

    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(
            "[Content_Types].xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>
<Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>
</Types>""",
        )
        archive.writestr(
            "_rels/.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/workbook.xml",
            """<?xml version="1.0" encoding="UTF-8"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
<sheets><sheet name="Storyboard" sheetId="1" r:id="rId1"/></sheets>
</workbook>""",
        )
        archive.writestr(
            "xl/_rels/workbook.xml.rels",
            """<?xml version="1.0" encoding="UTF-8"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/>
</Relationships>""",
        )
        archive.writestr(
            "xl/worksheets/sheet1.xml",
            f"""<?xml version="1.0" encoding="UTF-8"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
<sheetData>{''.join(sheet_rows)}</sheetData>
</worksheet>""",
        )


def _column_name(index: int) -> str:
    name = ""
    while index:
        index, remainder = divmod(index - 1, 26)
        name = chr(65 + remainder) + name
    return name


def _safe_spreadsheet_text(value: object) -> str:
    text = str(value or "")
    if text.startswith(("=", "+", "-", "@", "\t", "\r")):
        return f"'{text}"
    return text


def _export_html(path: Path, project: dict, bible: dict, shots: list[dict]) -> None:
    panels = []
    for shot in shots:
        image = shot.get("output_url", "")
        image_html = (
            f'<img src="../..{escape(image)}" alt="{escape(shot.get("shot_id", ""))}">'
            if image.startswith("/assets/")
            else '<div class="placeholder">无图片 / 無圖片 / No image / 画像なし / 이미지 없음</div>'
        )
        panels.append(
            f"""
            <article class="panel">
              {image_html}
              <h2>{escape(shot.get("scene_id") or shot.get("shot_id", ""))}</h2>
              <p>{escape(shot.get("visual_description", ""))}</p>
              <small>{escape(shot.get("revision_notes", ""))}</small>
            </article>
            """
        )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{escape(project.get("name", "Storyboard"))}</title>
  <style>
    body {{ margin: 0; font-family: Arial, sans-serif; background: #f4f1ea; color: #1f2328; }}
    header {{ padding: 24px; border-bottom: 3px solid #1f2328; }}
    h1 {{ margin: 0 0 8px; }}
    main {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 14px; padding: 18px; }}
    .panel {{ border: 3px solid #1f2328; background: #fff; padding: 10px; min-height: 340px; }}
    img, .placeholder {{ width: 100%; aspect-ratio: 1 / 1; object-fit: cover; border: 2px solid #1f2328; background: #e5e0d6; display: grid; place-items: center; }}
    h2 {{ margin: 10px 0 6px; font-size: 16px; }}
    p {{ margin: 0 0 8px; line-height: 1.45; }}
    small {{ color: #555; }}
  </style>
</head>
<body>
  <header>
    <h1>{escape(project.get("name", "Storyboard"))}</h1>
    <p>{escape(project.get("description", ""))}</p>
    <small>{escape(bible.get("visual_style", ""))}</small>
  </header>
  <main>
    {''.join(panels)}
  </main>
</body>
</html>
"""
    path.write_text(html, encoding="utf-8")


def _export_srt(path: Path, shots: list[dict]) -> None:
    lines = []
    cursor = 0.0
    for index, shot in enumerate(shots, 1):
        duration = float(shot.get("duration") or 3.0)
        start = _format_srt_time(cursor)
        end = _format_srt_time(cursor + duration)
        text = shot.get("revision_notes") or shot.get("visual_description") or shot.get("prompt", "")
        lines.append(f"{index}\n{start} --> {end}\n{text}\n")
        cursor += duration
    path.write_text("\n".join(lines), encoding="utf-8")


def _format_srt_time(seconds: float) -> str:
    millis = int(round(seconds * 1000))
    hours, remainder = divmod(millis, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    secs, ms = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"
