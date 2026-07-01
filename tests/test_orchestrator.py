import tempfile
import unittest
from pathlib import Path

from app.agents import DeterministicProvider
from app.orchestrator import Controller
from app.store import EventStore


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
        self.assertEqual(len(result.proposal.changes), 5)

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


if __name__ == "__main__":
    unittest.main()
