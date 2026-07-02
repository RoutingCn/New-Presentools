import tempfile
import unittest
from pathlib import Path

from app.agents import AgentDelivery, DeterministicProvider
from app.orchestrator import Controller
from app.store import EventStore


class FakeHtmlProvider:
    def __init__(self):
        self.calls = []

    def render(self, state, nodes):
        self.calls.append((state, tuple(nodes)))
        return "<!doctype html><html><body><main>ark html</main></body></html>"


class DuplicateProvider:
    def run(self, role, contract, context):
        return AgentDelivery(
            agent=role,
            summary="duplicate test",
            outputs=(
                {"kind": "concept", "title": "Same Title", "body": "Same body"},
                {"kind": "concept", "title": "Same Title", "body": "Different body"},
                {"kind": "example", "title": "Example", "body": "Same body"},
            ),
            affected_ids=(),
            uncertainties=("none",),
            quality_checks=("checked",),
            next_action="next",
        )


class ControllerTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.controller = Controller(
            EventStore(Path(self.temp.name)),
            DeterministicProvider(),
        )
        self.project = self.controller.create_project("制造业增长", "企业决策者")

    def tearDown(self):
        self.temp.cleanup()

    def test_topic_analysis_dispatches_all_specialists(self):
        result = self.controller.analyze_topic(self.project.id)

        self.assertEqual(
            set(result.deliveries),
            {"content", "research", "visual", "creative"},
        )
        self.assertEqual(result.proposal.status, "pending")
        self.assertGreaterEqual(len(result.proposal.changes), 12)

    def test_topic_analysis_contains_professional_content_layers(self):
        result = self.controller.analyze_topic(self.project.id)
        changes = result.proposal.changes
        kinds = {change["kind"] for change in changes}

        self.assertIn("concept", kinds)
        self.assertIn("relationship", kinds)
        self.assertIn("example", kinds)
        self.assertTrue(all(len(change["body"]) >= 80 for change in changes))

    def test_analysis_removes_duplicate_titles_and_bodies(self):
        controller = Controller(
            EventStore(Path(self.temp.name) / "dupes"),
            DuplicateProvider(),
        )
        project = controller.create_project("Topic", "Audience")

        result = controller.analyze_topic(project.id)

        title_keys = [
            (change["kind"], change["title"].strip().lower())
            for change in result.proposal.changes
        ]
        bodies = [change["body"].strip().lower() for change in result.proposal.changes]
        self.assertEqual(len(title_keys), len(set(title_keys)))
        self.assertEqual(len(bodies), len(set(bodies)))

    def test_agent_delivery_exposes_quality_and_uncertainty(self):
        result = self.controller.analyze_topic(self.project.id)

        for delivery in result.deliveries.values():
            self.assertTrue(delivery.summary)
            self.assertTrue(delivery.quality_checks)
            self.assertTrue(delivery.next_action)
        self.assertTrue(result.deliveries["research"].uncertainties)

    def test_memory_contains_decisions_evidence_gaps_and_version(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        artifact = self.controller.lock_artifact(self.project.id, "正式版")

        memory = self.controller.memory_markdown(self.project.id)

        self.assertIn("# 项目记忆", memory)
        self.assertIn("证据缺口", memory)
        self.assertIn(artifact.id, memory)
        self.assertIn("正式版", memory)

    def test_analysis_writes_one_event_per_agent(self):
        self.controller.analyze_topic(self.project.id)

        kinds = [event.kind for event in self.controller.events(self.project.id)]

        self.assertEqual(kinds.count("agent.completed"), 4)
        self.assertIn("proposal.created", kinds)

    def test_generates_script_proposal_from_accepted_structure(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)

        proposal = self.controller.generate_script(self.project.id)

        self.assertEqual(proposal.status, "pending")
        self.assertTrue(proposal.affected_ids)
        self.assertTrue(all(change["kind"] == "script" for change in proposal.changes))
        self.assertTrue(all("讲述逻辑" in change["body"] for change in proposal.changes))
        self.assertTrue(all("例子" in change["body"] for change in proposal.changes))

    def test_comment_creates_revision_proposal(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        node = self.controller.store.project(self.project.id).content_nodes[0]

        proposal = self.controller.submit_comment(
            self.project.id,
            "这里需要补充反方观点，并让表达更具体。",
            node.id,
        )

        self.assertEqual(proposal.status, "pending")
        self.assertEqual(proposal.affected_ids, (node.id,))
        self.assertEqual(proposal.changes[0]["kind"], "revision")
        self.assertIn("反方观点", proposal.changes[0]["body"])

    def test_rejecting_proposal_marks_it_without_writing_nodes(self):
        result = self.controller.analyze_topic(self.project.id)

        rejected = self.controller.reject_proposal(self.project.id, result.proposal.id)
        state = self.controller.store.project(self.project.id)

        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(state.proposals[0].status, "rejected")
        self.assertEqual(state.content_nodes, [])

    def test_script_titles_are_unique_when_source_titles_repeat(self):
        self.controller.store.add_content_node(
            self.project.id,
            kind="concept",
            title="重复标题",
            body="第一段内容",
        )
        self.controller.store.add_content_node(
            self.project.id,
            kind="relationship",
            title="重复标题",
            body="第二段内容",
        )

        proposal = self.controller.generate_script(self.project.id)

        titles = [change["title"] for change in proposal.changes]
        self.assertEqual(len(titles), len(set(titles)))

    def test_accepting_script_proposal_moves_project_to_script_stage(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        proposal = self.controller.generate_script(self.project.id)

        self.controller.accept_proposal(self.project.id, proposal.id)
        state = self.controller.store.project(self.project.id)

        self.assertEqual(state.stage, "script")
        self.assertTrue(any(node.kind == "script" for node in state.content_nodes))

    def test_locked_artifact_contains_rendered_html(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)

        artifact = self.controller.lock_artifact(self.project.id, "html")

        self.assertIn("<!doctype html>", artifact.html)
        self.assertIn("<article", artifact.html)

    def test_lock_artifact_uses_injected_html_provider(self):
        html_provider = FakeHtmlProvider()
        controller = Controller(
            EventStore(Path(self.temp.name) / "ark"),
            DeterministicProvider(),
            html_provider,
        )
        project = controller.create_project("HTML 新工具", "创业者")
        result = controller.analyze_topic(project.id)
        controller.accept_proposal(project.id, result.proposal.id)

        artifact = controller.lock_artifact(project.id, "html")

        self.assertIn("ark html", artifact.html)
        self.assertEqual(len(html_provider.calls), 1)
        self.assertTrue(all(node.kind != "script" for node in html_provider.calls[0][1]))

    def test_locked_html_excludes_script_nodes(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        script = self.controller.generate_script(self.project.id)
        self.controller.accept_proposal(self.project.id, script.id)

        artifact = self.controller.lock_artifact(self.project.id, "html")

        self.assertNotIn("script</small>", artifact.html)
        self.assertNotIn("逐字稿：", artifact.html)
        self.assertNotIn("这一页先呈现", artifact.html)


if __name__ == "__main__":
    unittest.main()
