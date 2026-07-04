# Agent-Native HTML Presentation MVP Design

## 1. Product Definition

The product is an AI-native content production and presentation system. It uses HTML as the only presentation format and an agent system as the production brain. It is not a PowerPoint clone and not a chat interface wrapped around a document editor.

The system has two starting points:

1. Import an existing manuscript and convert it into structured content, a speaking script, and an HTML presentation.
2. Start from a topic and proceed through deep analysis, research, structure, writing, visual production, and HTML publication.

The primary product value is preserving relationships among claims, evidence, sections, scripts, visuals, and presentation paths while allowing users to revise any part without silently damaging approved work.

## 2. MVP Goals

The MVP must provide a complete path from source material or topic to a usable HTML presentation. It must also prove the following differentiators:

- A controller agent coordinates specialized agents instead of one model producing everything.
- Every content object can receive comments and modification proposals at any stage.
- Public internet sources and a user-selected local research directory can be searched together.
- The project maintains both an evolving full-content edition and protected locked editions.
- The full process is retained as append-only history and summarized into a readable `memory.md`.
- Approved work cannot be overwritten by agents without explicit user approval.

Out of scope for the MVP: real-time multi-user collaboration, complex organization permissions, billing, an agent marketplace, and a general-purpose visual design platform.

## 3. User Experience

### 3.1 Workspace

The desktop workspace uses three stable regions separated by visible fixed dividers:

- Left: collapsible production stages and numbered outline.
- Center: the active analysis, writing, structure, or HTML production surface.
- Right: a persistent utility panel with tabs for comments, research, and revision history.

The interface is restrained, dense, and professional. It avoids decorative AI motifs, excessive cards, gradients, and promotional language.

### 3.2 Selection and References

Users can select objects with the mouse or keyboard, including multi-selection. Every selectable content object has a stable object ID plus section, paragraph, and line references. The outline supports folding so users can work at document, section, paragraph, or line level.

Comments never directly mutate approved content. A comment becomes a proposal containing its target, rationale, affected objects, diff, and requested agents. The user can accept, reject, revise, or defer the proposal.

### 3.3 Research

The research tool is available throughout the workflow. It searches:

- The public internet.
- A user-selected local directory.

Results retain source identity, excerpt, location, retrieval time, credibility assessment, and citation status. A result can be attached to a claim, added to the evidence library, or inserted as a cited content proposal.

## 4. Agent System

### 4.1 Controller Agent

The controller agent owns task decomposition, scheduling, dependencies, quality gates, memory, versions, and user approvals. It does not silently rewrite approved content. It must expose what it plans to do, which agents it will call, and what existing artifacts may be affected.

### 4.2 Content Agent

The content agent operates at the standard of a mature editor. It is responsible for argument structure, narrative sequence, language, transitions, summaries, and speaking scripts. It must check thesis clarity, logical continuity, audience fit, tone, and internal consistency.

### 4.3 Research Agent

The research agent combines investigative research and data analysis. It searches, evaluates sources, cross-checks important facts, processes data, distinguishes fact from inference, identifies counter-evidence, and records citation-ready excerpts. It must report evidence gaps rather than manufacturing certainty.

### 4.4 Visual Agent

The visual agent combines art direction and frontend engineering. It designs information hierarchy and interaction, implements HTML/CSS/JavaScript, and verifies responsive layouts, overflow, overlap, navigation, and runtime behavior. It must not merely divide prose into web slides.

### 4.5 Creative Agent

The creative agent combines the strategic perspective of a creative director with the sensitivity of a younger experimental creative. It provides both a grounded direction and a more challenging direction. Novelty must support the communication objective and remain executable.

## 5. Agent Delivery Contract

Every agent response must be structured and include:

- Task performed and rationale.
- Inputs, sources, and prerequisite decisions used.
- New content objects or proposed changes produced.
- Downstream objects and artifacts that may be affected.
- Uncertainty, risks, conflicts, and unresolved questions.
- Self-review against the agent's quality criteria.
- Recommended next action.

The controller rejects incomplete deliveries and may return them for revision. A task is not complete merely because an agent produced text.

## 6. Production Workflow

1. **Task contract:** define topic, audience, objective, duration, tone, success criteria, and exclusions.
2. **Deep analysis:** creative exploration, problem decomposition, assumptions, opposing views, evidence gaps, and conclusion strength.
3. **Research:** dual-source retrieval, source ranking, cross-validation, data processing, and citation capture.
4. **Structure:** reconcile agent outputs, expose conflicts, and create a user-approved structure version.
5. **Content production:** write the full content, speaking script, summaries, and transitions; perform editorial and factual review.
6. **Visual production:** design and implement the HTML presentation based on content relationships and audience paths.
7. **Acceptance and publication:** verify logic, facts, citations, visual quality, interaction, responsive behavior, and presentation navigation, then create a locked edition.

The manuscript entry begins with content parsing and then joins this workflow. The topic entry begins with the task contract and deep analysis.

## 7. Data Model

- `Project`: objective, audience, constraints, selected research directory, active stage, and policy settings.
- `ContentNode`: section, paragraph, claim, counterclaim, assumption, evidence, transition, script, or visual module.
- `Source`: web or local source, excerpt, location, metadata, credibility, and citation state.
- `Proposal`: target objects, rationale, requested changes, impact analysis, diff, and approval state.
- `Artifact`: full-content edition, locked edition, HTML build, script, summary, and their version relationships.
- `Event`: append-only agent dispatch, retrieval, discussion, approval, rejection, rollback, lock, and publication record.

Stable object IDs are independent from display order. Paragraph and line numbers are generated references and update predictably when content is edited.

## 8. Memory and Process History

Structured state and an append-only event log are the source of truth. `memory.md` is a human- and agent-readable projection, not the only storage mechanism.

The generated `memory.md` contains:

- Project contract and current stage.
- Important user decisions and locked constraints.
- Agent findings and accepted conclusions.
- Rejected directions with brief rationale.
- Evidence gaps and unresolved questions.
- Artifact versions, locks, and branches.
- Current recommended next steps.

All discussions, searches, proposals, approvals, and agent deliveries remain in process history. Compaction may summarize repetitive events but must retain links to original records.

## 9. Full-Content and Locked Editions

Each project maintains two kinds of output:

### 9.1 Full-Content Edition

The full-content edition is the evolving master. It includes complete analysis, alternatives, evidence, data, scripts, visual instructions, and unused material. Agents may propose and, with appropriate approval, apply changes to this edition.

### 9.2 Locked Edition

A locked edition is an immutable snapshot for a specific presentation. It fixes structure, wording, citations, visual implementation, and code. Agents cannot overwrite it. Changes create a candidate successor with a visible diff.

A locked edition can branch into audience- or occasion-specific versions, such as a 20-minute board edition, customer edition, or public edition. Branches share stable references to the full-content edition but remain independently locked.

When the full-content edition changes, the system calculates which locked-edition objects may be stale. Synchronization is always an explicit proposal and can be accepted item by item or in a reviewed batch.

## 10. Quality Gates

- **Content:** clear thesis, complete hierarchy, no logical gaps, mature language, suitable rhythm, and audience fit.
- **Research:** traceable sources, cross-validation for material facts, consistent data definitions, and separation of fact from inference.
- **Visual:** clear hierarchy, responsive behavior, no overflow or overlap, working interaction, maintainable code, and tested navigation.
- **Creative:** relevant differentiation, executable ideas, and both grounded and breakthrough options.
- **Controller:** conflict detection, impact analysis, correct approval gates, protection of locked artifacts, and refusal to advance low-quality work.

## 11. Failure Handling

- An agent timeout or failure can be retried without restarting the workflow.
- Weak or missing evidence is shown as an evidence gap, not hidden.
- HTML build failures do not corrupt content artifacts.
- Batch changes require a preview and impact list.
- Interrupted tasks resume from persisted events and structured state.
- Local directory access is explicit, scoped, and revocable.
- Every accepted change can be traced to its proposal and reverted by creating a new version.

## 12. Testing and Acceptance

Automated tests cover controller scheduling, agent delivery validation, proposal application, artifact locking, branching, rollback, citation traceability, local-directory access, and memory projection.

End-to-end browser tests cover both entry paths, object selection, paragraph and line references, outline folding, comments, dual-source research, proposal review, full-content updates, locked-edition protection, HTML preview, and responsive presentation behavior.

The MVP is accepted when a user can start from either a manuscript or a topic, produce researched and reviewed content, generate a working HTML presentation, lock it, continue improving the full-content edition, and inspect the complete reasoning and change history without any agent silently overwriting the locked result.
