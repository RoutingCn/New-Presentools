import unittest
from pathlib import Path
import re


class WebContractTest(unittest.TestCase):
    def test_workspace_has_stable_regions_and_agent_actions(self):
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertIn('data-region="outline"', html)
        self.assertIn('data-region="workspace"', html)
        self.assertIn('data-region="utility"', html)
        self.assertIn('id="analyze-topic"', html)
        self.assertIn('id="generate-script"', html)
        self.assertIn('id="script-download"', html)
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
        self.assertIn("/script", script)
        self.assertIn("/accept", script)
        self.assertIn("/artifacts/lock", script)
        self.assertIn("artifact.html", script)
        self.assertIn("window.open", script)
        self.assertIn("downloadScript", script)
        self.assertIn("cleanScriptTitle", script)
        self.assertIn('kind!=="script"', script)
        self.assertIn("/comments", script)
        self.assertIn("/memory", script)

    def test_topic_form_does_not_ship_with_test_data(self):
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertNotIn('value="中国制造业的下一轮增长"', html)
        self.assertNotIn('value="企业决策者与投资人"', html)
        self.assertIn('placeholder="请输入演示主题"', html)

    def test_creating_project_immediately_starts_analysis(self):
        script = Path("web/app.js").read_text(encoding="utf-8")

        self.assertRegex(
            script,
            re.compile(r"renderProject\(\);[\s\S]{0,160}await analyze\(\);"),
        )


    def test_provider_badge_loads_safe_health_status(self):
        html = Path("web/index.html").read_text(encoding="utf-8")
        script = Path("web/provider-status.js").read_text(encoding="utf-8")

        self.assertIn('id="provider-status"', html)
        self.assertIn('/api/health', script)
        self.assertIn('health.provider==="deepseek"', script)
        self.assertIn('本地模拟', script)


if __name__ == "__main__":
    unittest.main()
