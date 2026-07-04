import tempfile
import unittest
import json
from pathlib import Path

from app.server import create_app


class ApiApplicationTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.app = create_app(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_create_analyze_accept_and_lock(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "制造业增长", "audience": "企业决策者"},
        )
        analysis = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/analyze",
            {},
        )
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept",
            {},
        )
        preview = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/preview",
            {},
        )
        self.assertFalse(preview["locked"])
        self.assertIn("<!doctype html>", preview["html"])
        self.assertIn("<section", preview["html"])

        locked = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/html/{preview['id']}/lock",
            {},
        )
        self.assertTrue(locked["locked"])

    def test_deprecated_lock_artifact_still_works(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "制造业增长", "audience": "企业决策者"},
        )
        analysis = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/analyze",
            {},
        )
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept",
            {},
        )

        locked = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/artifacts/lock",
            {"name": "正式版"},
        )

        self.assertTrue(locked["locked"])
        self.assertIn("<!doctype html>", locked["html"])

    def test_generates_script_proposal_after_structure(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "Topic", "audience": "Audience"},
        )
        analysis = self.app.handle("POST", f"/api/projects/{project['id']}/analyze", {})
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept",
            {},
        )

        script = self.app.handle("POST", f"/api/projects/{project['id']}/script", {})

        self.assertEqual(script["status"], "pending")
        self.assertTrue(all(change["kind"] == "script" for change in script["changes"]))
        self.assertGreaterEqual(len(script["changes"]), 5)

    def test_comment_endpoint_returns_revision_proposal(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "Topic", "audience": "Audience"},
        )
        analysis = self.app.handle("POST", f"/api/projects/{project['id']}/analyze", {})
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept",
            {},
        )
        state = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        node_id = state["content_nodes"][0]["id"]

        proposal = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/comments",
            {"text": "请补充反方观点", "target_id": node_id},
        )

        self.assertEqual(proposal["status"], "pending")
        self.assertEqual(proposal["changes"][0]["kind"], "revision")
        self.assertEqual(proposal["affected_ids"], [node_id])

    def test_reject_proposal_endpoint_marks_proposal_rejected(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "Topic", "audience": "Audience"},
        )
        analysis = self.app.handle("POST", f"/api/projects/{project['id']}/analyze", {})

        rejected = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/reject",
            {},
        )
        state = self.app.handle("GET", f"/api/projects/{project['id']}", {})

        self.assertEqual(rejected["status"], "rejected")
        self.assertEqual(state["proposals"][0]["status"], "rejected")
        self.assertEqual(state["content_nodes"], [])

    def test_project_and_memory_can_be_read(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "制造业增长", "audience": "企业决策者"},
        )
        self.app.handle("POST", f"/api/projects/{project['id']}/analyze", {})

        state = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        memory = self.app.handle("GET", f"/api/projects/{project['id']}/memory", {})

        self.assertEqual(state["title"], "制造业增长")
        self.assertIn("# 项目记忆", memory["markdown"])

    def test_create_project_rejects_blank_title(self):
        with self.assertRaises(ValueError):
            self.app.handle(
                "POST",
                "/api/projects",
                {"title": "  ", "audience": "企业决策者"},
            )

    def test_health_reports_local_fallback_without_key(self):
        app = create_app(Path(self.temp.name), environ={})

        self.assertEqual(
            app.handle("GET", "/api/health"),
            {
                "status": "ok",
                "provider": "deterministic-local",
                "html_provider": "aesthetic-markdown",
                "html_model": "swiss",
            },
        )

    def test_health_reports_deepseek_without_exposing_key(self):
        app = create_app(
            Path(self.temp.name),
            environ={"DEEPSEEK_API_KEY": "server-secret"},
        )
        health = app.handle("GET", "/api/health")

        self.assertEqual(health["provider"], "deepseek")
        self.assertEqual(health["model"], "deepseek-v4-flash")
        self.assertEqual(health["html_provider"], "aesthetic-markdown")
        self.assertEqual(health["html_model"], "swiss")
        self.assertNotIn("server-secret", json.dumps(health))

    def test_remote_html_environment_is_ignored_for_html_generation(self):
        app = create_app(
            Path(self.temp.name),
            environ={"REMOTE_HTML_API_KEY": "remote-secret"},
        )
        health = app.handle("GET", "/api/health")

        self.assertEqual(health["html_provider"], "aesthetic-markdown")
        self.assertEqual(health["html_model"], "swiss")
        self.assertNotIn("remote-secret", json.dumps(health))

    def test_required_deepseek_rejects_missing_key(self):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
            create_app(Path(self.temp.name), environ={"REQUIRE_DEEPSEEK": "1"})

    def test_analyze_dispatches_5_events(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "Topic", "audience": "Audience"},
        )
        self.app.handle("POST", f"/api/projects/{project['id']}/analyze", {})
        state = self.app.handle("GET", f"/api/projects/{project['id']}", {})
        event_count = len(state.get("content_nodes", [])) + len(state.get("proposals", []))
        self.assertGreaterEqual(event_count, 1)

    def test_script_agent_event_is_recorded(self):
        project = self.app.handle(
            "POST",
            "/api/projects",
            {"title": "Topic", "audience": "Audience"},
        )
        analysis = self.app.handle("POST", f"/api/projects/{project['id']}/analyze", {})
        self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept",
            {},
        )
        self.app.handle("POST", f"/api/projects/{project['id']}/script", {})

        memory = self.app.handle("GET", f"/api/projects/{project['id']}/memory", {})
        self.assertIn("script", memory["markdown"])


if __name__ == "__main__":
    unittest.main()
