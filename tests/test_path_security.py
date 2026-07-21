import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.app.models.schemas import ProjectCreate
from backend.app.services import path_authorization_service, project_service


class ProjectPathSecurityTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.projects_home = self.root / "projects"
        self.legacy_projects = self.root / "legacy" / "projects"
        self.registry = self.root / "app-data" / "registry" / "projects.json"
        self.patchers = [
            patch.object(project_service, "PROJECTS_HOME", self.projects_home),
            patch.object(project_service, "PROJECTS_DIR", self.legacy_projects),
            patch.object(project_service, "REGISTRY_PATH", self.registry),
        ]
        for patcher in self.patchers:
            patcher.start()

    def tearDown(self):
        for patcher in reversed(self.patchers):
            patcher.stop()
        self.temporary_directory.cleanup()

    def test_project_id_and_root_containment_reject_traversal(self):
        with self.assertRaises(FileNotFoundError):
            project_service.get_project_dir("../outside")
        with self.assertRaises(ValueError):
            project_service.resolve_path_within(self.projects_home, "..", "outside")

    def test_self_contained_project_rejects_absolute_path_outside_project(self):
        project = project_service.create_project(ProjectCreate(name="Private title"))
        project_id = project["project_id"]
        project_dir = project_service.get_project_dir(project_id)
        inside = project_dir / "generated" / "inside.png"
        inside.write_bytes(b"inside")
        outside = self.root / "outside.png"
        outside.write_bytes(b"outside")

        self.assertEqual(project_service.resolve_project_path(project_id, inside), inside.resolve())
        with self.assertRaisesRegex(ValueError, "escapes"):
            project_service.resolve_project_path(project_id, outside)
        self.assertTrue(project_id.startswith("project-"))
        self.assertNotIn("private", project_id)

    def test_existing_child_lookup_never_builds_a_path_from_request_filename(self):
        directory = self.root / "assets"
        directory.mkdir()
        expected = directory / "panel.png"
        expected.write_bytes(b"panel")
        self.assertTrue(
            os.path.samefile(
                project_service.find_existing_child_file(directory, "panel.png"),
                expected,
            )
        )
        with self.assertRaises((FileNotFoundError, ValueError)):
            project_service.find_existing_child_file(directory, "../outside.png")
        with self.assertRaises((FileNotFoundError, ValueError)):
            project_service.find_existing_child_file(directory, str(expected.resolve()))


class DesktopPathAuthorizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary_directory.name)
        self.folder = self.root / "selected folder"
        self.folder.mkdir()
        self.backup = self.root / "selected.paneloom.zip"
        self.backup.write_bytes(b"backup")
        with path_authorization_service._APPROVAL_LOCK:
            path_authorization_service._APPROVED_PATHS.clear()

    def tearDown(self):
        with path_authorization_service._APPROVAL_LOCK:
            path_authorization_service._APPROVED_PATHS.clear()
        self.temporary_directory.cleanup()

    def test_unapproved_path_is_rejected_then_native_approval_is_reused(self):
        with patch.dict(os.environ, {}, clear=False):
            os.environ.pop("PANELOOM_DESKTOP_TEST_ROOT", None)
            with self.assertRaises(PermissionError):
                path_authorization_service.require_approved_desktop_path(
                    str(self.folder),
                    "folder",
                )
            approved = path_authorization_service.approve_desktop_path(self.folder, "folder")
            self.assertEqual(
                path_authorization_service.require_approved_desktop_path(
                    str(self.folder),
                    "folder",
                ),
                approved,
            )

    def test_test_root_allows_only_contained_paths(self):
        outside_root = self.root.parent / f"{self.root.name}-outside"
        outside_root.mkdir(exist_ok=True)
        try:
            with patch.dict(
                os.environ,
                {"PANELOOM_DESKTOP_TEST_ROOT": str(self.root)},
                clear=False,
            ):
                self.assertEqual(
                    Path(
                        path_authorization_service.require_approved_desktop_path(
                            str(self.folder),
                            "folder",
                        )
                    ),
                    self.folder.resolve(),
                )
                with self.assertRaises(PermissionError):
                    path_authorization_service.require_approved_desktop_path(
                        str(outside_root),
                        "folder",
                    )
        finally:
            outside_root.rmdir()

    def test_backup_approval_requires_an_existing_file(self):
        approved = path_authorization_service.approve_desktop_path(self.backup, "backup")
        self.assertEqual(
            path_authorization_service.require_approved_desktop_path(
                str(self.backup),
                "backup",
            ),
            approved,
        )
        with self.assertRaises(FileNotFoundError):
            path_authorization_service.approve_desktop_path(self.folder, "backup")


if __name__ == "__main__":
    unittest.main()
