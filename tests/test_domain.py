import tempfile
import unittest
from pathlib import Path

from app.domain import LockedArtifactError
from app.store import EventStore


class EventStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.store = EventStore(Path(self.temp.name))

    def tearDown(self):
        self.temp.cleanup()

    def test_replay_builds_project_without_mutating_events(self):
        project = self.store.create_project("制造业增长", "企业决策者")

        events = self.store.events(project.id)

        self.assertEqual([event.kind for event in events], ["project.created"])
        self.assertEqual(self.store.project(project.id).title, "制造业增长")
        self.assertEqual(events, self.store.events(project.id))

    def test_locked_artifact_is_immutable(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        node = self.store.add_content_node(
            project.id,
            kind="claim",
            title="核心判断",
            body="创新驱动将成为下一阶段的核心变量。",
        )
        artifact = self.store.lock_artifact(project.id, "董事会版", [node.id])

        with self.assertRaises(LockedArtifactError):
            self.store.replace_locked_artifact(project.id, artifact.id, [node.id])

    def test_accepting_proposal_creates_nodes_and_preserves_proposal(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        proposal = self.store.create_proposal(
            project.id,
            title="采用分析结构",
            rationale="形成可审阅的初始框架",
            changes=[
                {
                    "kind": "claim",
                    "title": "核心判断",
                    "body": "增长逻辑正在从规模扩张转向质量跃迁。",
                }
            ],
            affected_ids=[],
        )

        accepted = self.store.accept_proposal(project.id, proposal.id)
        state = self.store.project(project.id)

        self.assertEqual(accepted.status, "accepted")
        self.assertEqual(len(state.content_nodes), 1)
        self.assertEqual(state.proposals[0].status, "accepted")


if __name__ == "__main__":
    unittest.main()
