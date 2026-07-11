import json
import sys
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.app.models.schemas import ProjectCreate, ProjectWorkspacePayload, ShotCreate  # noqa: E402
from backend.app.services import export_service, project_service  # noqa: E402
from backend.app.services.shotlist_service import add_shot, update_shot  # noqa: E402


FIXTURE_NAME = "Paneloom 人工验收素材（可删除）"


def main() -> int:
    existing = next(
        (project for project in project_service.list_projects() if project.get("name") == FIXTURE_NAME),
        None,
    )
    if existing:
        print(
            json.dumps(
                {
                    "status": "already_exists",
                    "project_id": existing["project_id"],
                    "name": existing["name"],
                },
                ensure_ascii=False,
            )
        )
        return 0

    project = project_service.create_project(
        ProjectCreate(
            name=FIXTURE_NAME,
            description="非计费人工验收 fixture：两个本地图片版本、角色和场景参考图。",
        )
    )
    project_id = project["project_id"]
    project_service.save_project_workspace(
        project_id,
        ProjectWorkspacePayload(
            script="雨夜站台。角色小织撑着红伞等待列车。旁白：她决定从这里重新开始。",
            use_ai=False,
        ),
    )
    project_service.save_project_bible(
        project_id,
        {
            "characters": "小织：短黑发、红色外套、红伞。",
            "locations": "雨夜站台：蓝灰灯光、湿润地面、远处列车灯。",
            "props": "红色雨伞。",
            "visual_style": "清晰漫画线稿，低饱和蓝灰背景，红色作为强调色。",
            "prompt_prefix": "保持小织的短黑发、红色外套和红伞一致。",
        },
    )

    references = project_service.get_project_reference_dir(project_id)
    generated = project_service.get_project_generated_dir(project_id)
    references.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)
    Image.new("RGB", (256, 256), color=(180, 35, 45)).save(references / "character-xiaozhi.png")
    Image.new("RGB", (256, 256), color=(45, 70, 110)).save(references / "scene-rainy-station.png")
    Image.new("RGB", (512, 512), color=(165, 45, 55)).save(generated / "manual-version-a.png")
    Image.new("RGB", (512, 512), color=(45, 85, 145)).save(generated / "manual-version-b.png")

    shot = add_shot(
        project_id,
        ShotCreate(
            scene_id="MANUAL-001",
            visual_description="小织站在雨夜站台，红伞位于画面中央。",
            prompt="小织，短黑发，红色外套，撑红伞，雨夜站台，中景，漫画线稿。",
            negative_prompt="文字，水印，人物重复，服装颜色错误。",
            revision_notes="人工验收时切换 A/B 版本并测试锁定。",
        ),
    )
    versions = []
    for version_id, filename in (("manual-a", "manual-version-a.png"), ("manual-b", "manual-version-b.png")):
        output = generated / filename
        versions.append(
            {
                "version_id": version_id,
                "output_path": project_service.to_project_relative_path(project_id, output),
                "output_url": project_service.project_file_url(project_id, "generated", filename),
                "outputs": [],
                "status": "done",
                "created_at": project_service.utc_now(),
            }
        )
    update_shot(
        project_id,
        shot["shot_id"],
        {
            "status": "done",
            "output_path": versions[0]["output_path"],
            "output_url": versions[0]["output_url"],
            "versions": versions,
            "selected_version_id": versions[0]["version_id"],
        },
    )
    export_service.export_project(project_id, "json")
    export_service.export_project(project_id, "html")
    print(
        json.dumps(
            {
                "status": "created",
                "project_id": project_id,
                "name": FIXTURE_NAME,
                "project_directory": str(project_service.get_project_dir(project_id)),
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
