import tempfile
import unittest
from pathlib import Path

from app.agents import AgentDelivery, DeterministicProvider
from app.orchestrator import Controller
from app.store import ConflictError, EventStore


class FakeHtmlProvider:
    def __init__(self):
        self.calls = []

    def render(self, state, nodes):
        self.calls.append((state, tuple(nodes)))
        return "<!doctype html><html><body><main>custom html</main></body></html>"


class DuplicateProvider:
    def run(self, role, contract, context):
        if role == "script":
            return AgentDelivery(
                agent="script",
                summary="duplicate script test",
                outputs=(
                    {"kind": "script", "title": "Same Title", "body": "Same body"},
                    {"kind": "script", "title": "Same Title", "body": "Different body"},
                ),
                affected_ids=(),
                uncertainties=("none",),
                quality_checks=("checked",),
                next_action="next",
            )
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
        self.assertGreaterEqual(len(result.proposal.changes), 3)

    def test_topic_analysis_contains_professional_content_layers(self):
        result = self.controller.analyze_topic(self.project.id)
        changes = result.proposal.changes
        kinds = {change["kind"] for change in changes}

        self.assertIn("concept", kinds)
        self.assertIn("relationship", kinds)
        self.assertIn("example", kinds)
        self.assertTrue(all(len(change["body"]) >= 50 for change in changes))

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
        self.assertIn("内容版本：", memory)

    def test_analysis_writes_one_event_per_agent(self):
        self.controller.analyze_topic(self.project.id)

        kinds = [event.kind for event in self.controller.events(self.project.id)]

        self.assertEqual(kinds.count("agent.completed"), 4)
        self.assertIn("proposal.created", kinds)

    def test_generates_script_proposal_via_provider(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)

        proposal = self.controller.generate_script(self.project.id)

        self.assertEqual(proposal.status, "pending")
        self.assertTrue(proposal.affected_ids)
        self.assertTrue(all(change["kind"] == "script" for change in proposal.changes))
        self.assertGreaterEqual(len(proposal.changes), 5)
        body = proposal.changes[0]["body"]
        self.assertTrue(len(body) > 50)

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
        self.assertIn("<section", artifact.html)
        self.assertIn('data-paradigm="swiss"', artifact.html)

    def test_lock_artifact_uses_injected_html_provider(self):
        html_provider = FakeHtmlProvider()
        controller = Controller(
            EventStore(Path(self.temp.name) / "custom-html"),
            DeterministicProvider(),
            html_provider,
        )
        project = controller.create_project("HTML 新工具", "创业者")
        result = controller.analyze_topic(project.id)
        controller.accept_proposal(project.id, result.proposal.id)

        artifact = controller.lock_artifact(project.id, "html")

        self.assertIn("custom html", artifact.html)
        self.assertEqual(len(html_provider.calls), 1)
        self.assertTrue(all(node.kind != "script" for node in html_provider.calls[0][1]))

    def test_locked_html_excludes_script_nodes(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        script = self.controller.generate_script(self.project.id)
        self.controller.accept_proposal(self.project.id, script.id)

        artifact = self.controller.lock_artifact(self.project.id, "html")

        self.assertNotIn("script</small>", artifact.html)

    def test_revise_node_includes_version_before(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        node = self.controller.store.project(self.project.id).content_nodes[0]
        self.assertEqual(node.version, 1)

        proposal = self.controller.revise_node(
            self.project.id,
            node.id,
            "修订标题",
            "修订后的正文内容，包含了更多的细节和表达。",
        )

        self.assertEqual(proposal.changes[0]["operation"], "update")
        self.assertEqual(proposal.changes[0]["version_before"], 1)
        self.assertIn("before", proposal.changes[0])

    def test_node_version_increments_after_revision_accept(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        node = self.controller.store.project(self.project.id).content_nodes[0]
        old_version = node.version

        revision = self.controller.revise_node(
            self.project.id,
            node.id,
            "修订标题",
            "修订后的正文内容，包含了更多的细节和表达。",
        )
        self.controller.accept_proposal(self.project.id, revision.id)

        updated_state = self.controller.store.project(self.project.id)
        updated = [n for n in updated_state.content_nodes if n.id == node.id][0]
        self.assertEqual(updated.version, old_version + 1)

    def test_html_preview_is_not_locked(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)

        preview = self.controller.preview_html(self.project.id, "测试预览")

        self.assertFalse(preview.locked)
        self.assertGreater(len(preview.html), 0)

    def test_html_preview_can_be_locked(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        preview = self.controller.preview_html(self.project.id, "测试预览")

        locked = self.controller.lock_html_preview(self.project.id, preview.id)

        self.assertTrue(locked.locked)
        self.assertEqual(locked.html, preview.html)

    def test_preview_to_lock_state_transition(self):
        result = self.controller.analyze_topic(self.project.id)
        self.controller.accept_proposal(self.project.id, result.proposal.id)
        preview = self.controller.preview_html(self.project.id)

        state_after_preview = self.controller.store.project(self.project.id)
        self.assertNotEqual(state_after_preview.stage, "locked")

        self.controller.lock_html_preview(self.project.id, preview.id)
        state_after_lock = self.controller.store.project(self.project.id)
        self.assertEqual(state_after_lock.stage, "locked")


if __name__ == "__main__":
    unittest.main()
