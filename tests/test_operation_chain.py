import json
import tempfile
import unittest
from pathlib import Path

from app.server import create_app


class OperationChainTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name), environ={})

    def tearDown(self):
        self.temp.cleanup()

    def _project_with_content(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "HTML presentation", "audience": "founders"},
        )
        analysis = self.app.handle("POST", f"/api/projects/{project['id']}/analyze", {})
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept",
            {},
        )
        return self.app.handle("GET", f"/api/projects/{project['id']}", {})

    def test_revision_and_delete_are_proposals_with_accept_or_reject(self):
        project = self._project_with_content()
        node = project["content_nodes"][0]

        revision = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/nodes/{node['id']}/revision",
            {"title": "Revised title", "body": "Revised body with a concrete example."},
        )
        self.assertEqual(revision["status"], "pending")
        self.assertEqual(revision["changes"][0]["operation"], "update")
        self.assertIn("version_before", revision["changes"][0])

        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{revision['id']}/accept",
            {},
        )
        updated = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        updated_node = next(item for item in updated["content_nodes"] if item["id"] == node["id"])
        self.assertEqual(updated_node["title"], "Revised title")
        self.assertEqual(updated_node["body"], "Revised body with a concrete example.")
        self.assertGreater(updated_node["version"], node["version"])

        delete = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/nodes/{node['id']}/delete",
            {"reason": "Remove this object from the presentation structure."},
        )
        self.assertEqual(delete["changes"][0]["operation"], "delete")
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{delete['id']}/reject",
            {},
        )
        rejected = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        self.assertTrue(any(item["id"] == node["id"] for item in rejected["content_nodes"]))

    def test_html_provider_can_be_selected_tested_previewed_and_locked(self):
        summary = self.app.handle("GET", "/api/html-provider", {})
        self.assertEqual(summary["provider"], "aesthetic-markdown")
        self.assertEqual(summary["model"], "swiss")
        self.assertNotIn("api_key", json.dumps(summary))

        updated = self.app.handle(
            "POST",
            "/api/html-provider",
            {
                "provider": "aesthetic-markdown",
                "model": "editorial",
            },
        )
        self.assertEqual(updated["provider"], "aesthetic-markdown")
        self.assertEqual(updated["model"], "editorial")
        self.assertNotIn("runtime-secret", json.dumps(updated))

        tested = self.app.handle("POST", "/api/html-provider/test", {})
        self.assertEqual(tested["status"], "ok")

        project = self._project_with_content()
        preview = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/preview",
            {},
        )
        self.assertFalse(preview["locked"])
        self.assertIn('data-paradigm="editorial"', preview["html"])
        self.assertIn('<nav id="outline"', preview["html"])

        locked = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/{preview['id']}/lock",
            {},
        )
        self.assertTrue(locked["locked"])
        self.assertEqual(locked["html"], preview["html"])

    def test_remote_html_provider_is_not_supported(self):
        with self.assertRaisesRegex(ValueError, "不支持的 HTML 生成引擎"):
            self.app.handle(
                "POST",
                "/api/html-provider",
                {"provider": "remote-html", "api_key": "runtime-secret"},
            )

    def test_script_generated_via_provider(self):
        project = self._project_with_content()
        script = self.app.handle("POST", f"/api/projects/{project['id']}/script", {})
        self.assertGreaterEqual(len(script["changes"]), 5)
        self.assertTrue(all(c["kind"] == "script" for c in script["changes"]))
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{script['id']}/accept",
            {},
        )
        state = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        scripts = [n for n in state["content_nodes"] if n["kind"] == "script"]
        self.assertGreaterEqual(len(scripts), 5)
        for s in scripts:
            self.assertTrue(len(s["body"]) > 50)

    def test_preview_then_lock_state_progression(self):
        project = self._project_with_content()

        preview = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/preview",
            {},
        )
        self.assertFalse(preview["locked"])

        state_after_preview = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        self.assertNotEqual(state_after_preview["stage"], "locked")

        locked = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/{preview['id']}/lock",
            {},
        )
        self.assertTrue(locked["locked"])

        state_after_lock = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        self.assertEqual(state_after_lock["stage"], "locked")


if __name__ == "__main__":
    unittest.main()
