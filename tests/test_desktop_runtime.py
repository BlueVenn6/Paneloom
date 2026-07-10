import unittest
from unittest.mock import patch

from backend.app.security import redact_sensitive_text
from backend.app.routes import generation
from desktop.launcher import (
    LocalDesktopServer,
    SingleInstanceError,
    WindowsSingleInstance,
    create_desktop_app,
)


class DesktopRuntimeTests(unittest.TestCase):
    def test_built_ui_and_api_share_random_loopback_server_and_stop(self):
        server = LocalDesktopServer(create_desktop_app())
        server.start()
        try:
            self.assertEqual(server.url.split(":")[1], "//127.0.0.1")
            self.assertGreater(server.port, 0)
        finally:
            server.stop()
        self.assertFalse(server.thread.is_alive())

    def test_provider_errors_are_redacted_before_logging(self):
        secret = "custom-provider-secret-123"
        value = redact_sensitive_text(
            f"Authorization: Bearer {secret}; api_key={secret}; sk-abc123secret",
            [secret],
        )
        self.assertNotIn(secret, value)
        self.assertNotIn("sk-abc123secret", value)
        self.assertIn("[REDACTED]", value)

    def test_second_desktop_instance_is_rejected(self):
        first = WindowsSingleInstance("Local\\PaneloomDesktopTestMutex")
        try:
            with self.assertRaises(SingleInstanceError):
                WindowsSingleInstance("Local\\PaneloomDesktopTestMutex")
        finally:
            first.close()

    def test_active_ai_jobs_are_marked_cancelled_for_desktop_shutdown(self):
        generation._GENERATION_JOBS["shutdown-test"] = {
            "job_id": "shutdown-test",
            "status": "running",
        }
        try:
            with patch(
                "backend.app.services.shotlist_service.recover_interrupted_generation_states"
            ) as recover:
                self.assertTrue(generation.interrupt_active_jobs_for_desktop_shutdown())
                recover.assert_called_once()
            self.assertEqual(
                generation._GENERATION_JOBS["shutdown-test"]["status"],
                "cancelled",
            )
        finally:
            generation._GENERATION_JOBS.pop("shutdown-test", None)


if __name__ == "__main__":
    unittest.main()
