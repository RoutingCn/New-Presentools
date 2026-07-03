import json
import tempfile
import unittest
from pathlib import Path

from app.server import create_app


class HtmlTransport:
    def __init__(self):
        self.calls = []

    def __call__(self, url, headers, payload, timeout):
        self.calls.append((url, headers, payload, timeout))
        return {
            "choices": [
                {
                    "message": {
                        "content": "<!doctype html><html><body><main>preview html</main></body></html>"
                    }
                }
            ]
        }


class OperationChainTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.transport = HtmlTransport()
        self.app = create_app(Path(self.temp.name), environ={}, transport=self.transport)

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

        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{revision['id']}/accept",
            {},
        )
        updated = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        updated_node = next(item for item in updated["content_nodes"] if item["id"] == node["id"])
        self.assertEqual(updated_node["title"], "Revised title")
        self.assertEqual(updated_node["body"], "Revised body with a concrete example.")

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

    def test_html_provider_can_be_replaced_tested_previewed_and_locked(self):
        summary = self.app.handle("GET", "/api/html-provider", {})
        self.assertEqual(summary["provider"], "local-template")
        self.assertNotIn("api_key", json.dumps(summary))

        updated = self.app.handle(
            "POST",
            "/api/html-provider",
            {
                "provider": "ark",
                "api_key": "runtime-secret",
                "model": "doubao-html",
                "base_url": "https://ark.example.test/api/v3",
                "timeout_seconds": 12,
                "require_remote": True,
            },
        )
        self.assertEqual(updated["provider"], "ark")
        self.assertEqual(updated["model"], "doubao-html")
        self.assertNotIn("runtime-secret", json.dumps(updated))

        tested = self.app.handle("POST", "/api/html-provider/test", {})
        self.assertEqual(tested["status"], "ok")
        self.assertEqual(self.transport.calls[-1][0], "https://ark.example.test/api/v3/chat/completions")

        project = self._project_with_content()
        preview = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/preview",
            {},
        )
        self.assertFalse(preview["locked"])
        self.assertIn("preview html", preview["html"])

        locked = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/{preview['id']}/lock",
            {},
        )
        self.assertTrue(locked["locked"])
        self.assertEqual(locked["html"], preview["html"])


if __name__ == "__main__":
    unittest.main()
