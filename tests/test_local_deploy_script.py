import unittest
from pathlib import Path


class LocalDeployScriptTest(unittest.TestCase):
    def test_deepseek_start_script_requires_real_provider(self):
        script = Path("scripts/start-deepseek-local.ps1").read_text(encoding="utf-8")

        self.assertIn("REQUIRE_DEEPSEEK", script)
        self.assertIn("DEEPSEEK_API_KEY", script)
        self.assertNotIn("REQUIRE_ARK_HTML", script)
        self.assertNotIn("ARK_API_KEY", script)
        self.assertNotIn("Volcengine Ark", script)
        self.assertIn("app.server", script)


if __name__ == "__main__":
    unittest.main()
