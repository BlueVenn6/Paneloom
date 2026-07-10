import json
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image

from backend.app.models.schemas import (
    ProjectCreate,
    ProjectWorkspacePayload,
    ShotCreate,
    ShotUpdate,
    StoryOptimizationRequest,
)
from backend.app.services import export_service, image_service, project_portability_service, project_service
from backend.app.services.shotlist_service import add_shot, list_shots, patch_shot, update_shot
from backend.app.services.story_optimization_service import optimize_story


class ProjectPortabilityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name) / "含 空格"
        self.root.mkdir()
        self.legacy_projects = self.root / "legacy" / "projects"
        self.projects_home = self.root / "portable projects"
        self.registry = self.root / "app data" / "registry" / "projects.json"
        self.legacy_generated = self.root / "legacy assets" / "generated"
        self.legacy_references = self.root / "legacy assets" / "references"
        self.legacy_exports = self.root / "legacy exports"
        self.migration_log = self.root / "app data" / "logs" / "migrations.jsonl"
        self.patchers = [
            patch.object(project_service, "PROJECTS_DIR", self.legacy_projects),
            patch.object(project_service, "PROJECTS_HOME", self.projects_home),
            patch.object(project_service, "REGISTRY_PATH", self.registry),
            patch.object(project_portability_service, "PROJECTS_DIR", self.legacy_projects),
            patch.object(project_portability_service, "GENERATED_ASSETS_DIR", self.legacy_generated),
            patch.object(project_portability_service, "REFERENCE_ASSETS_DIR", self.legacy_references),
            patch.object(project_portability_service, "EXPORTS_DIR", self.legacy_exports),
            patch.object(project_portability_service, "MIGRATION_LOG", self.migration_log),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary_directory.cleanup()

    def _create_complete_project(self, name="Portable"):
        project = project_service.create_project(ProjectCreate(name=name))
        project_id = project["project_id"]
        project_service.save_project_workspace(
            project_id,
            ProjectWorkspacePayload(script="状态 A 剧本", story_goal="keep continuity"),
        )
        project_service.save_project_bible(
            project_id,
            {
                "characters": "Hero: short black hair",
                "locations": "Station platform at night",
                "props": "red umbrella",
            },
        )
        reference = project_service.get_project_reference_dir(project_id) / "hero.png"
        reference.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (24, 24), color=(80, 120, 160)).save(reference)
        shot = add_shot(project_id, ShotCreate(scene_id="S001", prompt="Hero at station"))
        generated = project_service.get_project_generated_dir(project_id) / "panel-v1.png"
        generated.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (32, 32), color=(20, 30, 40)).save(generated)
        relative = project_service.to_project_relative_path(project_id, generated)
        output_url = project_service.project_file_url(project_id, "generated", generated.name)
        version = {
            "version_id": "v1",
            "output_path": relative,
            "output_url": output_url,
            "outputs": [],
        }
        update_shot(
            project_id,
            shot["shot_id"],
            {
                "status": "done",
                "output_path": relative,
                "output_url": output_url,
                "versions": [version],
                "selected_version_id": "v1",
            },
        )
        patch_shot(
            project_id,
            shot["shot_id"],
            ShotUpdate(locked=True, approval_status="approved"),
        )
        export_service.export_project(project_id, "json")
        return project, reference, generated

    def test_self_contained_project_moves_and_reopens_with_assets_versions_and_export(self):
        project, _, _ = self._create_complete_project()
        project_id = project["project_id"]
        original = project_service.get_project_dir(project_id)
        moved = self.root / "moved elsewhere" / original.name
        moved.parent.mkdir(parents=True)
        shutil.move(str(original), str(moved))

        self.assertIsNone(project_service.get_project(project_id))
        reopened = project_service.open_project_directory(moved)
        self.assertEqual(reopened["project_id"], project_id)
        shots = list_shots(project_id)
        self.assertTrue(shots[0]["locked"])
        self.assertEqual(shots[0]["selected_version_id"], "v1")
        self.assertTrue(project_service.resolve_project_path(project_id, shots[0]["output_path"]).is_file())
        self.assertTrue((project_service.get_project_reference_dir(project_id) / "hero.png").is_file())
        exported = export_service.export_project(project_id, "html")
        self.assertTrue(project_service.resolve_project_path(project_id, exported["path"]).is_file())

    def test_backup_state_a_modify_state_b_restore_state_a_without_overwrite(self):
        project, _, _ = self._create_complete_project("Backup")
        project_id = project["project_id"]
        backup = project_portability_service.create_project_backup(project_id)
        self.assertTrue(backup["verified"])

        project_service.save_project_workspace(
            project_id,
            ProjectWorkspacePayload(script="状态 B 剧本"),
        )
        original_shot = list_shots(project_id)[0]
        patch_shot(
            project_id,
            original_shot["shot_id"],
            ShotUpdate(locked=False, approval_status="draft"),
        )

        restored = project_portability_service.restore_project_backup(backup["backup_path"])
        restored_id = restored["project_id"]
        self.assertNotEqual(restored_id, project_id)
        self.assertEqual(project_service.get_project_workspace(project_id)["script"], "状态 B 剧本")
        self.assertEqual(project_service.get_project_workspace(restored_id)["script"], "状态 A 剧本")
        restored_shot = list_shots(restored_id)[0]
        self.assertTrue(restored_shot["locked"])
        self.assertEqual(restored_shot["approval_status"], "approved")
        self.assertTrue(
            project_service.resolve_project_path(restored_id, restored_shot["output_path"]).is_file()
        )

    def test_legacy_absolute_paths_migrate_idempotently_without_modifying_source(self):
        project_id = "legacy-project-1234"
        legacy_dir = self.legacy_projects / project_id
        legacy_dir.mkdir(parents=True)
        generated = self.legacy_generated / project_id / "old-panel.png"
        reference = self.legacy_references / project_id / "old-reference.png"
        exported = self.legacy_exports / project_id / "old-export.json"
        for path, color in [(generated, (1, 2, 3)), (reference, (4, 5, 6))]:
            path.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (16, 16), color=color).save(path)
        exported.parent.mkdir(parents=True, exist_ok=True)
        exported.write_text("{}", encoding="utf-8")
        config = {
            "project_id": project_id,
            "name": "Legacy",
            "description": "",
            "created_at": project_service.utc_now(),
            "updated_at": project_service.utc_now(),
            "project_path": str(legacy_dir.resolve()),
            "archived": False,
        }
        shot = {
            "shot_id": "shot-legacy1",
            "prompt": "legacy",
            "status": "done",
            "output_path": str(generated.resolve()),
            "output_url": f"/assets/generated/{project_id}/{generated.name}",
            "selected_version_id": "v1",
            "locked": True,
            "approval_status": "approved",
            "versions": [
                {
                    "version_id": "v1",
                    "output_path": str(generated.resolve()),
                    "output_url": f"/assets/generated/{project_id}/{generated.name}",
                    "outputs": [],
                }
            ],
        }
        for filename, data in [
            ("project_config.json", config),
            ("shots.json", [shot]),
            ("workspace.json", {"script": "legacy script"}),
            ("project_bible.json", {"style_reference_filename": reference.name}),
            ("schedule.json", {}),
            ("tasks.json", []),
        ]:
            (legacy_dir / filename).write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        for filename in ["generation_log.csv", "failed_jobs.csv", "time_logs.csv", "publishing_log.csv"]:
            (legacy_dir / filename).write_text("id\n", encoding="utf-8")
        source_snapshot = {
            path.relative_to(legacy_dir).as_posix(): path.read_bytes()
            for path in legacy_dir.rglob("*")
            if path.is_file()
        }

        migrated = project_portability_service.migrate_legacy_project(project_id)
        self.assertEqual(migrated["status"], "migrated")
        self.assertTrue(Path(migrated["migration_backup"]).is_file())
        self.assertEqual(
            source_snapshot,
            {
                path.relative_to(legacy_dir).as_posix(): path.read_bytes()
                for path in legacy_dir.rglob("*")
                if path.is_file()
            },
        )
        portable_dir = project_service.get_project_dir(project_id)
        portable_config = json.loads((portable_dir / "project_config.json").read_text(encoding="utf-8"))
        portable_shot = list_shots(project_id)[0]
        self.assertEqual(portable_config["project_path"], ".")
        self.assertEqual(portable_config["storage_format"], "self_contained")
        self.assertEqual(portable_shot["output_path"], "generated/old-panel.png")
        self.assertTrue(project_service.resolve_project_path(project_id, portable_shot["output_path"]).is_file())
        self.assertTrue((project_service.get_project_reference_dir(project_id) / reference.name).is_file())
        self.assertTrue((project_service.get_project_export_dir(project_id) / exported.name).is_file())
        again = project_portability_service.migrate_legacy_project(project_id)
        self.assertEqual(again["status"], "already_migrated")

    def test_offline_mode_keeps_local_workflow_and_blocks_cloud_generation(self):
        project, _, _ = self._create_complete_project("Offline")
        project_id = project["project_id"]
        shot = list_shots(project_id)[0]
        patch_shot(
            project_id,
            shot["shot_id"],
            ShotUpdate(locked=False, approval_status="draft"),
        )
        with patch.dict(os.environ, {"PANELOOM_FORCE_OFFLINE": "1"}):
            project_service.save_project_workspace(
                project_id,
                ProjectWorkspacePayload(script="offline edit persisted"),
            )
            self.assertEqual(
                project_service.get_project_workspace(project_id)["script"],
                "offline edit persisted",
            )
            with patch.object(image_service, "generate_image") as provider_call:
                blocked = image_service.generate_shot_image(project_id, shot["shot_id"])
                provider_call.assert_not_called()
            self.assertEqual(blocked["error_code"], "offline_mode")
            local_story = optimize_story(
                StoryOptimizationRequest(script="A short offline story", use_ai=True)
            )
            self.assertEqual(local_story["source"], "local")
            self.assertTrue(any("offline" in warning.lower() for warning in local_story["warnings"]))
            exported = export_service.export_project(project_id, "json")
            self.assertTrue(
                project_service.resolve_project_path(project_id, exported["path"]).is_file()
            )
            self.assertTrue(
                project_service.resolve_project_path(project_id, shot["output_path"]).is_file()
            )


if __name__ == "__main__":
    unittest.main()
