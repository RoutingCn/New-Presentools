import unittest

from app.aesthetic_html import AestheticHtmlProvider, nodes_to_markdown
from app.domain import ContentNode, ProjectState


class AestheticHtmlProviderTest(unittest.TestCase):
    def test_nodes_are_converted_to_presentation_markdown_without_scripts(self):
        nodes = (
            ContentNode(
                id="n1",
                kind="concept",
                title="Core claim",
                body="The product should make structure visible.",
            ),
            ContentNode(
                id="n2",
                kind="script",
                title="Speaker script",
                body="This should stay out of the display HTML.",
            ),
        )

        markdown = nodes_to_markdown("HTML first", "Founders", nodes)

        self.assertIn("# HTML first", markdown)
        self.assertIn("## Core claim", markdown)
        self.assertIn("The product should make structure visible.", markdown)
        self.assertNotIn("Speaker script", markdown)
        self.assertNotIn("This should stay out", markdown)

    def test_provider_renders_self_contained_aesthetic_html(self):
        state = ProjectState(id="p1", title="HTML first", audience="Founders")
        nodes = (
            ContentNode(
                id="n1",
                kind="concept",
                title="Core claim",
                body="The product should make structure visible.",
            ),
            ContentNode(
                id="n2",
                kind="relationship",
                title="Why HTML",
                body="- Links keep context\n- Sections can be folded\n- Layout can be programmed",
            ),
        )

        html = AestheticHtmlProvider().render(state, nodes)

        self.assertIn("<!doctype html>", html.lower())
        self.assertIn('data-paradigm="swiss"', html)
        self.assertIn('<nav id="outline"', html)
        self.assertIn('href="#core-claim"', html)
        self.assertIn('<section id="core-claim"', html)
        self.assertIn("The product should make structure visible.", html)
        self.assertIn("Links keep context", html)
        self.assertNotIn("https://fonts", html)

    def test_provider_promotes_numeric_tables_to_stat_cards(self):
        state = ProjectState(id="p1", title="Metrics", audience="Team")
        nodes = (
            ContentNode(
                id="n1",
                kind="evidence",
                title="Adoption",
                body=(
                    "| Metric | Value |\n"
                    "| --- | --- |\n"
                    "| Teams | 12 |\n"
                    "| Growth | 34% |"
                ),
            ),
        )

        html = AestheticHtmlProvider().render(state, nodes)

        self.assertIn('class="stat-card-row"', html)
        self.assertIn("Growth", html)
        self.assertIn("34%", html)


if __name__ == "__main__":
    unittest.main()
