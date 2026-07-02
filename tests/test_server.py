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
        accepted = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/proposals/{analysis['proposal']['id']}/accept",
            {},
        )
        locked = self.app.handle(
            "POST",
            f"/api/projects/{project['id']}/artifacts/lock",
            {"name": "正式版"},
        )

        self.assertEqual(accepted["status"], "accepted")
        self.assertTrue(locked["locked"])
        self.assertGreaterEqual(len(locked["node_ids"]), 12)
        self.assertIn("<!doctype html>", locked["html"])
        self.assertIn("<section", locked["html"])

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
                "html_provider": "local-template",
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
        self.assertEqual(health["html_provider"], "local-template")
        self.assertNotIn("server-secret", json.dumps(health))

    def test_health_reports_ark_html_without_exposing_key(self):
        app = create_app(
            Path(self.temp.name),
            environ={"ARK_API_KEY": "ark-secret", "ARK_MODEL": "doubao-seed-1-6"},
        )
        health = app.handle("GET", "/api/health")

        self.assertEqual(health["html_provider"], "ark")
        self.assertEqual(health["html_model"], "doubao-seed-1-6")
        self.assertNotIn("ark-secret", json.dumps(health))

    def test_required_deepseek_rejects_missing_key(self):
        with self.assertRaisesRegex(ValueError, "DEEPSEEK_API_KEY"):
            create_app(Path(self.temp.name), environ={"REQUIRE_DEEPSEEK": "1"})

    def test_required_ark_html_rejects_missing_key(self):
        with self.assertRaisesRegex(ValueError, "ARK_API_KEY"):
            create_app(Path(self.temp.name), environ={"REQUIRE_ARK_HTML": "1"})


if __name__ == "__main__":
    unittest.main()
