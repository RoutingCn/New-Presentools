import unittest
from pathlib import Path


class WebContractTest(unittest.TestCase):
    def test_workspace_has_stable_regions_and_agent_actions(self):
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertIn('data-region="outline"', html)
        self.assertIn('data-region="workspace"', html)
        self.assertIn('data-region="utility"', html)
        self.assertIn('id="analyze-topic"', html)
        self.assertIn('id="lock-artifact"', html)
        self.assertIn('id="comment-input"', html)

    def test_styles_use_visible_workspace_dividers(self):
        css = Path("web/styles.css").read_text(encoding="utf-8")

        self.assertIn("--divider-width: 3px", css)
        self.assertIn("border-right: var(--divider-width)", css)
        self.assertIn("@media (max-width: 860px)", css)

    def test_client_calls_each_vertical_slice_endpoint(self):
        script = Path("web/app.js").read_text(encoding="utf-8")

        self.assertIn("/api/projects", script)
        self.assertIn("/analyze", script)
        self.assertIn("/accept", script)
        self.assertIn("/artifacts/lock", script)
        self.assertIn("/memory", script)


if __name__ == "__main__":
    unittest.main()
