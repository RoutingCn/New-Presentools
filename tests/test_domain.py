import tempfile
import unittest
from pathlib import Path

from app.domain import ConflictError, ContentNode, LockedArtifactError
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

    def test_rejecting_proposal_does_not_create_nodes(self):
        project = self.store.create_project("Topic", "Audience")
        proposal = self.store.create_proposal(
            project.id,
            title="Draft",
            rationale="Needs review",
            changes=[{"kind": "claim", "title": "Claim", "body": "Body"}],
            affected_ids=[],
        )

        rejected = self.store.reject_proposal(project.id, proposal.id)
        state = self.store.project(project.id)

        self.assertEqual(rejected.status, "rejected")
        self.assertEqual(state.proposals[0].status, "rejected")
        self.assertEqual(state.content_nodes, [])

    def test_content_version_increments_on_accept(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        self.assertEqual(self.store.project(project.id).content_version, 0)

        proposal = self.store.create_proposal(
            project.id,
            title="Initial structure",
            rationale="First analysis",
            changes=[
                {"kind": "claim", "title": "核心判断", "body": "增长逻辑转变。"}
            ],
            affected_ids=[],
        )
        self.store.accept_proposal(project.id, proposal.id)
        state = self.store.project(project.id)
        self.assertGreater(state.content_version, 0)

    def test_optimistic_lock_rejects_stale_write(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        state_v0 = self.store.project(project.id)
        self.assertEqual(state_v0.content_version, 0)

        first = self.store.create_proposal(
            project.id,
            title="First change",
            rationale="First",
            changes=[
                {"kind": "claim", "title": "First", "body": "First body."}
            ],
            affected_ids=[],
        )
        self.store.accept_proposal(project.id, first.id)

        second = self.store.create_proposal(
            project.id,
            title="Stale change",
            rationale="Based on old version",
            changes=[
                {"kind": "claim", "title": "Second", "body": "Second body."}
            ],
            affected_ids=[],
        )
        with self.assertRaises(ConflictError):
            self.store.accept_proposal(project.id, second.id, expected_version=0)

    def test_node_version_updates_on_accept(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        proposal = self.store.create_proposal(
            project.id,
            title="Initial",
            rationale="First",
            changes=[
                {"kind": "claim", "title": "核心判断", "body": "增长逻辑转变。"}
            ],
            affected_ids=[],
        )
        self.store.accept_proposal(project.id, proposal.id)
        state = self.store.project(project.id)
        node = state.content_nodes[0]
        self.assertEqual(node.version, 1)

        revision = self.store.create_proposal(
            project.id,
            title="Update",
            rationale="Modify",
            changes=[
                {
                    "operation": "update",
                    "node_id": node.id,
                    "kind": node.kind,
                    "title": "核心判断（修订）",
                    "body": "修订后的内容。",
                    "source_ids": list(node.source_ids),
                    "version_before": node.version,
                }
            ],
            affected_ids=[node.id],
        )
        self.store.accept_proposal(project.id, revision.id)
        updated_state = self.store.project(project.id)
        updated_node = updated_state.content_nodes[0]
        self.assertEqual(updated_node.version, 2)
        self.assertEqual(updated_node.title, "核心判断（修订）")

    def test_optimistic_lock_rejects_stale_node_write(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        proposal = self.store.create_proposal(
            project.id,
            title="Initial",
            rationale="First",
            changes=[
                {"kind": "claim", "title": "核心判断", "body": "增长逻辑转变。"}
            ],
            affected_ids=[],
        )
        self.store.accept_proposal(project.id, proposal.id)
        node = self.store.project(project.id).content_nodes[0]
        self.assertEqual(node.version, 1)

        self.store.accept_proposal(
            project.id,
            self.store.create_proposal(
                project.id,
                title="First update",
                rationale="First edit",
                changes=[
                    {
                        "operation": "update",
                        "node_id": node.id,
                        "kind": node.kind,
                        "title": "修订版一",
                        "body": "第一次修订。",
                        "source_ids": list(node.source_ids),
                        "version_before": node.version,
                    }
                ],
                affected_ids=[node.id],
            ).id,
        )

        revision = self.store.create_proposal(
            project.id,
            title="Stale update",
            rationale="Based on old version",
            changes=[
                {
                    "operation": "update",
                    "node_id": node.id,
                    "kind": node.kind,
                    "title": "过期修订",
                    "body": "基于旧版本。",
                    "source_ids": list(node.source_ids),
                    "version_before": 1,
                }
            ],
            affected_ids=[node.id],
        )
        with self.assertRaises(ConflictError):
            self.store.accept_proposal(project.id, revision.id)

    def test_compact_events_counts_correctly(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        self.store.add_content_node(project.id, kind="claim", title="A", body="a")
        self.store.add_content_node(project.id, kind="evidence", title="B", body="b")

        counts = self.store.compact_events(project.id)
        self.assertGreaterEqual(counts["total"], 3)
        self.assertNotIn("_compaction_recommended", counts)

    def test_iter_events_is_lazy(self):
        project = self.store.create_project("制造业增长", "企业决策者")
        events = list(self.store.iter_events(project.id))
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0].kind, "project.created")


if __name__ == "__main__":
    unittest.main()
