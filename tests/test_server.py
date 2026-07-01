import tempfile
import unittest
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
        self.assertEqual(len(locked["node_ids"]), 5)

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


if __name__ == "__main__":
    unittest.main()
