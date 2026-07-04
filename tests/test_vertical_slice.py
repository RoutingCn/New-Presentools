import tempfile
import unittest
from pathlib import Path

from app.agents import DeterministicProvider
from app.orchestrator import Controller
from app.store import EventStore


class VerticalSliceTest(unittest.TestCase):
    def test_topic_to_locked_artifact_preserves_complete_history(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = Controller(
                EventStore(Path(directory)),
                DeterministicProvider(),
            )
            project = controller.create_project("制造业增长", "企业决策者")
            analysis = controller.analyze_topic(project.id)
            controller.accept_proposal(project.id, analysis.proposal.id)
            preview = controller.preview_html(project.id, "HTML 预览")
            controller.lock_html_preview(project.id, preview.id)

            events = controller.events(project.id)
            memory = controller.memory_markdown(project.id)

            self.assertEqual(controller.store.project(project.id).stage, "locked")
            self.assertGreaterEqual(len(events), 6)
            self.assertIn("内容版本：", memory)
            self.assertEqual(controller.store.project(project.id).stage, "locked")

    def test_analysis_script_preview_lock_chain(self):
        with tempfile.TemporaryDirectory() as directory:
            controller = Controller(
                EventStore(Path(directory)),
                DeterministicProvider(),
            )
            project = controller.create_project("AI 与企业增长", "创业者")
            analysis = controller.analyze_topic(project.id)
            controller.accept_proposal(project.id, analysis.proposal.id)

            script = controller.generate_script(project.id)
            controller.accept_proposal(project.id, script.id)

            preview = controller.preview_html(project.id, "董事会版")
            self.assertFalse(preview.locked)

            locked = controller.lock_html_preview(project.id, preview.id)
            self.assertTrue(locked.locked)

            state = controller.store.project(project.id)
            self.assertEqual(state.stage, "locked")
            self.assertGreater(len(state.content_nodes), 0)
            self.assertTrue(any(node.kind == "script" for node in state.content_nodes))


if __name__ == "__main__":
    unittest.main()
