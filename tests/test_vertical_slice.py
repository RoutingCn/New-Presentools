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
            artifact = controller.lock_artifact(project.id, "正式版")

            events = controller.events(project.id)
            memory = controller.memory_markdown(project.id)

            self.assertTrue(artifact.locked)
            self.assertEqual(len(events), 8)
            self.assertIn("过程事件：8 条", memory)
            self.assertIn(artifact.id, memory)
            self.assertEqual(controller.store.project(project.id).stage, "locked")


if __name__ == "__main__":
    unittest.main()
