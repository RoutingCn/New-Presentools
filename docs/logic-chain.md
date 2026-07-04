# HTML 演示系统操作逻辑链条

版本：草案 v2  
用途：作为产品讨论和下一轮开发依据  
核心修正：本文不按功能模块写，而按“用户动作 -> 触发条件 -> 界面响应 -> 状态变化 -> 数据/API -> 增删改 -> 失败处理”写。

## 0. 总原则

系统不是一组功能按钮，而是一条持续生产链。任何一步都必须回答：

- 用户现在能做什么？
- 为什么现在能做？
- 用户操作后会触发什么？
- 界面哪里变化？
- 哪个状态变化？
- 产生、修改或删除了哪个对象？
- 是否需要用户批准？
- 是否影响全量内容版、逐字稿、HTML 或锁定版？
- 失败后如何回退？

没有这些回答，就不是链条，只是功能堆叠。

## 1. 核心对象与增删改规则

### 1.1 Project 项目

项目是所有内容和过程的容器。

字段：

- id
- title
- audience
- goal
- entry_type：topic 或 manuscript
- current_stage
- selected_research_sources
- active_proposal_id
- active_artifact_id

可执行操作：

| 操作 | 触发 | 结果 |
|---|---|---|
| 新增 | 用户创建项目 | 创建 Project，进入 input_contract |
| 修改 | 用户修改项目标题、受众、目标 | 创建 project.updated 事件，必要时生成影响提示 |
| 删除 | 用户删除项目 | 标记 project.deleted，不物理删除历史 |
| 查看 | 打开项目 | 读取当前投影状态 |

项目删除必须是软删除，因为过程记忆、锁定版和审查链不能直接丢失。

### 1.2 ContentNode 内容对象

内容对象是系统编辑和生成的最小稳定单位。

字段：

- id
- kind：section、claim、concept、relationship、evidence、example、counterclaim、transition、script、visual
- title
- body
- parent_id
- order
- source_ids
- status：draft、pending、approved、deprecated
- line_start / line_end
- created_by
- updated_from_proposal_id

可执行操作：

| 操作 | 触发 | 结果 |
|---|---|---|
| 新增 | 批准结构提案、批准资料提案、手动添加对象 | 新增节点 |
| 修改 | 批准修订提案、用户手动编辑草稿 | 更新节点版本 |
| 删除 | 批准删除提案 | 节点标记 deprecated |
| 拆分 | 用户要求拆成多个对象 | 生成拆分提案 |
| 合并 | 用户要求合并相邻对象 | 生成合并提案 |
| 移动 | 用户拖动大纲或调整顺序 | 生成 reorder 事件或提案 |

重要规则：

- 已批准对象不能被 Agent 静默覆盖。
- 删除不做物理删除，先 deprecated。
- 修改必须能追溯到 proposal。
- 每个对象要能被右侧意见工具定位。

### 1.3 Proposal 提案

提案是任何实质修改的入口。

字段：

- id
- title
- type：analysis、structure、revision、script、research_insert、visual、html_build、delete、reorder
- rationale
- affected_ids
- changes
- requested_agents
- status：pending、accepted、rejected、deferred、superseded
- created_from：user_comment、agent_run、research_result、manual_action

可执行操作：

| 操作 | 触发 | 结果 |
|---|---|---|
| 新增 | Agent 输出、用户意见、资料加入、手动修改 | pending |
| 批准 | 用户点击批准 | 写入目标对象，status=accepted |
| 退回 | 用户点击退回 | status=rejected，不写入 |
| 暂存 | 用户点击暂存 | status=deferred |
| 继续修改 | 用户对提案继续提意见 | 创建新 proposal，旧 proposal=superseded |
| 局部批准 | 用户只批准部分变更 | 拆成 accepted 部分和 pending 部分 |

当前 MVP 缺：deferred、superseded、局部批准、diff。

### 1.4 ResearchSource / Evidence 资料对象

资料必须是对象，不能只是搜索结果文本。

字段：

- id
- query
- source_type：web、local_directory
- title
- url_or_path
- excerpt
- retrieved_at
- credibility
- citation_status
- attached_node_ids

可执行操作：

| 操作 | 触发 | 结果 |
|---|---|---|
| 新增 | 搜索或导入资料 | 创建资料对象 |
| 修改 | 修正摘要、可信度、绑定对象 | 更新资料对象 |
| 删除 | 用户移除资料 | 标记 removed |
| 绑定 | 用户把资料绑定到内容对象 | 创建 evidence.attached |
| 入文 | 用户要求加入正文 | 创建 research_insert proposal |

当前 MVP 缺：资料对象、真实搜索、指定目录检索、绑定关系。

### 1.5 ScriptArtifact 逐字稿成果

逐字稿必须独立，不应混入内容结构和 HTML。

字段：

- id
- source_node_ids
- text
- format：txt、md、speaker_notes
- status：draft、approved

可执行操作：

| 操作 | 触发 | 结果 |
|---|---|---|
| 新增 | 生成逐字稿并批准 | 创建 ScriptArtifact |
| 修改 | 对逐字稿提意见 | 创建 script_revision proposal |
| 删除 | 用户删除某个逐字稿版本 | 标记 removed |
| 下载 | 用户点击下载 | 返回 txt/md 文件 |

当前 MVP 部分实现：script 节点和下载入口。建议改成独立 Artifact。

### 1.6 HtmlArtifact HTML 成果

HTML 是展示成果，不是内容母本。

字段：

- id
- source_content_version
- source_node_ids
- provider
- provider_model
- api_profile
- html
- status：preview、locked、failed
- error

可执行操作：

| 操作 | 触发 | 结果 |
|---|---|---|
| 新增预览 | 用户点击生成 HTML | 调用 HTML API，创建 preview |
| 替换预览 API | 用户选择或配置 API | 更新 api_profile 后重新生成 |
| 锁定 | 用户批准预览 | 创建 locked artifact |
| 删除预览 | 用户放弃预览 | 标记 removed |
| 创建后继版 | 锁定版需要修改 | 新建 successor preview |

当前 MVP：生成即锁定，缺少 preview 和 API 替换操作。

## 2. 主状态机

状态必须服务操作，不只是显示进度。

| 状态 | 用户可做动作 | 进入条件 | 退出条件 |
|---|---|---|---|
| input_contract | 创建/修改项目输入 | 无项目或项目未完成输入 | 点击创建/保存 |
| source_analysis_pending | 等待分析 | 项目已创建 | 分析完成或失败 |
| proposal_review | 审查提案 | 有 pending proposal | 批准、退回、暂存、继续修改 |
| content_workspace | 浏览/修改全量内容版 | 有 approved content nodes | 生成逐字稿、生成 HTML、继续修订 |
| research_workspace | 搜索/绑定资料 | 用户打开资料工具 | 资料入库或生成提案 |
| script_workspace | 生成/修改/下载逐字稿 | 有 approved content nodes | 逐字稿批准或退回 |
| html_workspace | 配置 API、生成预览、锁定 | 有 approved content nodes | HTML 预览成功、失败、锁定 |
| locked_workspace | 查看锁定版/创建后继版 | 有 locked artifact | 创建新候选版或返回内容母本 |

任意状态都可进入 revision_loop：

- 用户提交意见。
- 用户退回提案。
- 用户修改资料。
- HTML 生成失败。
- 锁定版需要更新。

## 3. 界面总布局链

界面应配合状态，而不是固定显示所有按钮。

### 3.1 顶部状态栏

始终显示：

- 项目名称。
- 当前状态。
- 当前模型/HTML API。
- 保存状态。
- 当前主动作按钮。
- 当前风险提示。

例：

| 状态 | 主按钮 | 风险提示 |
|---|---|---|
| input_contract | 创建并分析 | 输入不足不会启动 Agent |
| proposal_review | 批准写入 / 退回 / 暂存 | 批准后才改全量版 |
| content_workspace | 生成逐字稿 / 生成 HTML | HTML 不读取逐字稿 |
| html_workspace | 重新生成 / 锁定 | 生成失败不影响内容 |

### 3.2 左侧流程与对象树

左侧不是装饰进度条，应包含：

- 阶段导航。
- 对象树。
- 对象状态。
- 段号和行号。
- 有评论/有资料缺口/被锁定版使用的标记。

用户动作：

- 点击阶段：切换主工作台。
- 点击对象：中间定位对象，右侧意见目标变成该对象。
- 折叠章节：只影响显示，不影响状态。
- 拖动对象：触发 reorder proposal 或直接 reorder draft。

### 3.3 中间主工作台

中间每次只服务一个主要动作。

工作台：

- 契约工作台。
- 输入解析工作台。
- 提案审查工作台。
- 全量内容工作台。
- 资料工作台。
- 逐字稿工作台。
- HTML 工作台。
- 锁定版工作台。

### 3.4 右侧永久工具

右侧不是“留言板”，而是辅助动作入口。

Tab：

- 意见：对当前对象或项目整体发起修订。
- 资料：搜索、导入、绑定、生成资料提案。
- 版本：查看全量版、逐字稿、HTML、锁定版关系。
- 记忆：查看 memory.md。
- Agent：查看调度和失败原因。

## 4. 最小闭环：按操作动作重写

下面才是真正的 MVP 操作链。

### 4.1 动作 A：创建项目

触发条件：

- 用户在 input_contract 状态。
- 至少填写主题或导入稿件。
- 填写受众。

界面：

- 中间显示契约表单。
- 顶部主按钮：创建并分析。
- 右侧意见、资料工具可显示但不可提交修订。

用户动作：

1. 输入主题/稿件。
2. 输入受众。
3. 输入表达目标。
4. 点击创建并分析。

系统动作：

1. 创建 Project。
2. 写入 project.created 事件。
3. 状态变为 source_analysis_pending。
4. UI 显示分析进度。
5. 调用总控 Agent。

失败：

- 缺主题/稿件：表单内提示。
- 缺受众：表单内提示。
- 模型不可用：状态变为 source_analysis_failed，允许重试或保存草稿。

增删改：

- 新增 Project。
- 允许修改 Project 契约。
- 不允许删除已创建历史，只允许软删除项目。

### 4.2 动作 B：总控启动分析

触发条件：

- Project 已创建。
- current_stage=source_analysis_pending。
- 没有 active pending proposal，或用户选择重新分析。

界面：

- 中间显示 Agent 调度过程。
- 左侧阶段高亮“输入理解/深度分析”。
- 右侧 Agent 记录显示每个 Agent 状态。

系统动作：

1. 总控生成任务。
2. 调用内容 Agent。
3. 调用资料 Agent。
4. 调用视觉 Agent。
5. 调用创意 Agent。
6. 检查输出质量。
7. 合并为 proposal。
8. 状态进入 proposal_review。

失败：

- 某 Agent 失败：显示失败 Agent、失败原因、重试按钮。
- 输出重复：触发去重或要求模型重写。
- 输出空泛：总控拒绝进入提案，要求重跑。

增删改：

- 新增 agent.completed 或 agent.failed 事件。
- 新增 Proposal。
- 不修改 ContentNode。

### 4.3 动作 C：审查提案

触发条件：

- active_proposal.status=pending。

界面：

- 中间显示提案审查工作台。
- 提案必须显示：
  - 修改理由。
  - 影响对象。
  - 新增/修改/删除内容。
  - 调用过的 Agent。
  - 质量检查。
  - 风险。
- 底部按钮：批准、退回、暂存、继续讨论。

用户动作与结果：

| 用户动作 | 系统结果 |
|---|---|
| 批准 | 写入目标对象，proposal=accepted，进入 content_workspace |
| 退回 | proposal=rejected，不写入，回到上一工作台 |
| 暂存 | proposal=deferred，不写入，保留在待办 |
| 继续讨论 | 创建 comment，触发 revision_loop |
| 局部批准 | 拆分 proposal，批准部分写入，未批准部分保留 |

当前 MVP 缺：

- 暂存。
- 继续讨论挂在提案上。
- 局部批准。
- diff。

### 4.4 动作 D：写入全量内容版

触发条件：

- 用户批准 proposal。

系统动作：

1. 读取 proposal.changes。
2. 对每个 change 执行新增、修改、删除或排序。
3. 创建 content.added/content.updated/content.deprecated/content.reordered 事件。
4. proposal.status=accepted。
5. 更新全量内容版投影。
6. current_stage=content_workspace。

界面：

- 左侧对象树更新。
- 中间显示全量内容版。
- 右侧意见目标默认为项目整体。
- 顶部显示“全量内容版已更新”。

增删改要求：

- 新增：创建新 ContentNode。
- 修改：保留旧版本引用。
- 删除：只 deprecated，不物理删除。
- 排序：记录 order 变更。

失败：

- 写入冲突：提示有更新版本，要求用户选择合并或重审。

### 4.5 动作 E：选择内容对象

触发条件：

- 全量内容版存在。

界面：

- 用户可在左侧对象树或中间正文点击对象。
- 选中后：
  - 对象高亮。
  - 显示段号/行号。
  - 右侧意见目标切换到该对象。
  - 右侧资料绑定目标切换到该对象。

可操作：

- 提意见。
- 搜资料。
- 修改标题。
- 删除对象。
- 拆分对象。
- 合并对象。
- 移动对象。

每个操作都应产生 proposal，除非对象还处于 draft。

### 4.6 动作 F：提交意见

触发条件：

- 有 Project。
- 目标为项目整体或某个 ContentNode。
- 输入意见不为空。

界面：

- 右侧意见工具显示：
  - 当前目标。
  - 目标正文摘录。
  - 意见输入框。
  - 预计动作类型选择：补充、删除、重写、调整结构、补资料、改视觉、改 HTML、改逐字稿。
- 提交按钮文案应是“生成修订提案”，不是“加入讨论”。

系统动作：

1. 创建 comment.added 事件。
2. 总控判断意见类型。
3. 判断影响范围。
4. 必要时调用对应 Agent。
5. 创建 revision proposal。
6. 状态进入 proposal_review。

增删改：

- 意见本身新增为 Comment。
- 不直接修改 ContentNode。
- 批准 proposal 后才修改。

失败：

- 意见太模糊：总控生成澄清问题，不进入提案。
- 影响锁定版：提示“会影响某锁定版，需要生成后继候选版”。

### 4.7 动作 G：删除内容对象

触发条件：

- 用户选中一个 ContentNode。
- 对象不是锁定版唯一引用，或系统能创建后继版。

界面：

- 删除按钮出现在对象操作菜单。
- 点击后弹出删除提案预览：
  - 删除对象。
  - 影响下游逐字稿。
  - 影响 HTML。
  - 是否影响锁定版。

系统动作：

1. 创建 delete proposal。
2. 用户批准后节点 status=deprecated。
3. 重新计算大纲和后续对象。
4. 标记相关逐字稿/HTML 过期。

失败：

- 如果对象被锁定版使用，不允许直接删除锁定版内容，只能创建候选后继版。

### 4.8 动作 H：修改内容对象

触发条件：

- 用户选中对象。
- 用户提交改写、补充、压缩、展开等意见。

界面：

- 显示原文。
- 显示新文。
- 显示 diff。
- 显示影响对象。
- 显示批准/退回/继续修改。

系统动作：

1. 生成 revision proposal。
2. 批准后创建 content.updated。
3. 原对象保留旧版本引用。
4. 下游逐字稿/HTML 标记 may_be_stale。

### 4.9 动作 I：调整结构顺序

触发条件：

- 用户拖动对象。
- 或提交“把这部分提前/合并/拆开”的意见。

界面：

- 左侧对象树支持拖动。
- 结构调整需要显示新旧顺序。

系统动作：

1. 如果只是 draft，可直接 reorder。
2. 如果是 approved，生成 reorder proposal。
3. 批准后写入 content.reordered。

### 4.10 动作 J：资料搜索

触发条件：

- 用户打开右侧资料工具。
- 输入查询。
- 选择互联网、指定资料目录或两者。

界面：

- 搜索框。
- 来源勾选。
- 结果列表。
- 每条结果显示：来源、摘要、可信度、操作按钮。

系统动作：

1. 创建 research.query。
2. 资料 Agent 搜索。
3. 创建 ResearchSource 对象。
4. 返回结果列表。

用户可操作：

| 操作 | 结果 |
|---|---|
| 保存资料 | 加入资料库 |
| 绑定当前对象 | evidence.attached |
| 加入正文 | 创建 research_insert proposal |
| 删除结果 | 标记 removed |

失败：

- 网络不可用：提示失败，可搜索本地目录。
- 指定目录不可读：提示路径问题。
- 资料可信度低：允许保存，但不能自动入正文。

当前 MVP 缺：整个资料链条。

### 4.11 动作 K：生成逐字稿

触发条件：

- 有 approved 内容结构。
- 没有未审完的结构 proposal。

界面：

- 中间切到逐字稿工作台。
- 显示输入范围：哪些内容对象会生成逐字稿。
- 按钮：生成逐字稿。

系统动作：

1. 内容 Agent 读取 approved ContentNode。
2. 生成 script proposal。
3. 状态进入 proposal_review。
4. 批准后创建 ScriptArtifact。

界面结果：

- 显示逐字稿预览。
- 提供下载按钮。
- 逐字稿不出现在全量内容正文混排中。
- HTML 默认不读取逐字稿。

可增删改：

- 重新生成逐字稿。
- 修改某段逐字稿。
- 删除某个逐字稿版本。
- 下载 txt/md。

失败：

- 没有内容结构：禁用按钮并说明原因。
- 逐字稿与结构不匹配：标红缺失对象。

### 4.12 动作 L：配置/替换 HTML 生成 API

这是当前必须补上的链条。不能把“用哪个 API”藏在环境变量里，让界面完全不知道。

触发条件：

- 用户进入 HTML 工作台。
- 或系统检测到 html_provider 不可用。
- 或用户明确要求切换 HTML 美学范式。

界面：

- HTML 工作台显示“HTML 生成引擎”区域。
- 显示当前引擎：
  - provider：Aesthetic Markdown / Local template
  - paradigm：Swiss Modern / Editorial Classic / Dark Tech / Neo Brutalist
  - 是否本地生成
- 操作按钮：
  - 更换范式
  - 测试输出
  - 保存配置
  - 重新生成 HTML

系统动作：

1. 用户选择生成引擎和美学范式。
2. 前端把 provider 和 paradigm 发送到后端。
3. 后端切换本地 HTML provider。
4. 调用 `/api/html-provider/test` 生成测试 HTML。
5. 成功后更新 provider_info。
6. HTML 生成调用新的 provider。

建议 API：

| 端点 | 用途 |
|---|---|
| GET /api/html-provider | 读取当前 HTML 生成引擎摘要 |
| POST /api/html-provider | 更新 provider、paradigm |
| POST /api/html-provider/test | 测试输出 |
| POST /api/projects/{id}/html/preview | 生成 HTML 预览 |
| POST /api/projects/{id}/html/{preview_id}/lock | 锁定预览 |

安全规则：

- HTML 生成不再依赖远程 API key。
- 内容模型 key 不能进入浏览器响应。
- 内容模型 key 不能进入事件。
- 内容模型 key 不能进入 memory.md。
- 内容模型 key 不能提交到 git。

当前实现问题：

- HTML 最后一步已切为本地美学 Markdown 引擎。
- 前端需要继续增强范式选择和预览状态。
- 生成 HTML 直接走 lock_artifact，没有 preview。
- 不再需要远程 HTML API。
- 已有“测试输出”动作，后续需要增加视觉检查结果。

下一步开发必须把 HTML 美学范式选择和视觉检查链前置到 HTML 工作台。

### 4.13 动作 M：生成 HTML 预览

触发条件：

- 有 approved 内容结构。
- HTML API 已配置并测试成功。
- 没有 active pending proposal，或用户确认用当前版本生成。

界面：

- HTML 工作台显示：
  - 使用哪些内容对象。
  - 不包含逐字稿。
  - 当前 API。
  - 当前模型。
  - 生成按钮。

系统动作：

1. 读取 approved ContentNode，排除 script。
2. 调用 HtmlProvider。
3. 创建 HtmlArtifact status=preview。
4. 返回 HTML 预览 URL 或 blob。
5. 中间显示预览。
6. 按钮变为：锁定、重新生成、更换 API、退回视觉方案。

失败：

- API 401：提示 key 错误，进入 HTML API 配置。
- API 超时：允许重试或换 API。
- 返回片段：系统包装为完整 HTML，并提示“已自动修复格式”。
- 无法打开：保留失败 artifact，显示错误，不影响内容。

### 4.14 动作 N：锁定 HTML

触发条件：

- 有 HTML preview。
- 用户确认内容、视觉、导航可用。

界面：

- 按钮：锁定为正式版。
- 提示：锁定后不能直接覆盖。

系统动作：

1. 创建 locked HtmlArtifact。
2. 记录 source_content_version。
3. 记录 source_node_ids。
4. 记录 provider/model。
5. current_stage=locked_workspace。

后续修改：

- 修改全量内容版不会自动改锁定版。
- 系统提示锁定版可能过期。
- 用户可创建后继候选版。

### 4.15 动作 O：修改锁定版

触发条件：

- 用户在 locked_workspace 提出修改。

界面：

- 不显示“直接保存”。
- 显示“创建后继候选版”。

系统动作：

1. 创建 successor proposal。
2. 修改全量内容版或 HTML preview。
3. 生成新的 preview。
4. 用户锁定后成为新 locked artifact。
5. 原 locked artifact 保留。

## 5. 从主题开始完整链

这是第一条 MVP 主链。

1. 创建项目。
2. 自动进入分析。
3. Agent 完成输入理解。
4. 生成分析/结构提案。
5. 用户审查。
6. 批准后写入全量内容版。
7. 用户选择对象。
8. 用户提交意见。
9. 总控生成修订提案。
10. 用户批准或退回。
11. 用户搜索资料。
12. 资料入库或生成资料提案。
13. 用户生成逐字稿。
14. 审查并批准逐字稿。
15. 用户进入 HTML 工作台。
16. 配置或确认 HTML API。
17. 测试 API。
18. 生成 HTML 预览。
19. 预览通过后锁定。
20. memory.md 记录全过程。

每一步都必须有界面状态和失败分支。

## 6. 从文章开始完整链

文章入口不是简单复用主题入口。它多了“原文解析”链。

1. 用户导入文章。
2. 系统创建 Project entry_type=manuscript。
3. 中间显示原文对照工作台。
4. 系统自动编号段落和行号。
5. 内容 Agent 解析结构。
6. 资料 Agent 标记事实和引用。
7. 总控生成“原稿转展示结构”提案。
8. 用户审查：
   - 保留哪些部分。
   - 删除哪些部分。
   - 哪些改成展示章节。
   - 哪些改成逐字稿。
9. 批准后写入 ContentNode。
10. 后续进入与主题入口相同的 content_workspace。

文章入口必须支持：

- 原文保留。
- 原文和 ContentNode 映射。
- 段号/行号引用。
- 用户按段落提出意见。
- 删除/合并/拆分原文段落。

## 7. 当前 MVP 与目标链差距

| 链条 | 当前状态 | 缺口 |
|---|---|---|
| 创建项目 | 已有 | goal 没进入 Project 模型 |
| 分析 | 已有 | 状态太粗，失败显示不足 |
| 提案审查 | 部分有 | 无暂存、diff、局部批准、继续讨论链 |
| 写入全量版 | 部分有 | 只有新增，没有修改/删除/排序 |
| 选择对象 | 部分有 | 无对象状态、无版本、无资料绑定 |
| 提交意见 | 部分有 | 无类型判断 UI，无影响分析 |
| 删除对象 | 无 | 需要 delete proposal |
| 修改对象 | 部分有 | 当前 revision 更像新增，不是真 diff 修改 |
| 资料搜索 | 占位 | 需要完整 ResearchSource 链 |
| 逐字稿 | 部分有 | 应独立 Artifact，不应混为 ContentNode |
| HTML API 替换 | 后端环境变量有 | 缺界面配置、测试连接、动态替换 |
| HTML 预览 | 无 | 当前生成即锁定 |
| 锁定版 | 部分有 | 缺后继版、过期提示、版本绑定 |

## 8. 下一轮最小开发闭环

不能再按“功能模块”推进。下一轮应该按这条操作闭环做：

1. 用户创建项目。
2. 系统生成结构提案。
3. 用户批准。
4. 中间进入全量内容工作台。
5. 用户选中一个对象。
6. 用户执行“修改对象”。
7. 系统生成带 diff 的 revision proposal。
8. 用户批准，原对象更新。
9. 用户执行“删除对象”。
10. 系统生成 delete proposal。
11. 用户退回，内容不变。
12. 用户进入 HTML 工作台。
13. 用户查看当前 HTML API。
14. 用户替换 HTML API 配置。
15. 用户测试连接。
16. 用户生成 HTML 预览。
17. 用户锁定。

这才是最小闭环，因为它覆盖：

- 新增。
- 修改。
- 删除。
- 退回。
- 状态显示。
- 界面配合。
- API 替换。
- HTML 预览。
- 锁定。

## 9. 立即应改的开发任务

优先级从高到低。

### P0：HTML API 替换链

必须实现：

- HTML 工作台。
- 当前 API 摘要。
- 更换 API 表单。
- 测试连接。
- 生成 HTML preview。
- preview 再锁定。

### P0：Proposal 增删改

必须实现：

- content.updated。
- content.deprecated。
- content.reordered。
- revision proposal 带 old/new。
- delete proposal。
- accept/reject/defer。

### P0：状态与界面对应

必须实现：

- current_stage 不再只有 5 个粗状态。
- 每个状态有主工作台。
- 顶部显示当前可执行动作。
- 禁用按钮必须显示原因。

### P1：对象级工作台

必须实现：

- 对象树。
- 对象状态。
- 段号行号。
- 对象操作菜单：修改、删除、拆分、合并、移动、加资料。

### P1：资料对象链

必须实现：

- 资料搜索接口抽象。
- 本地目录检索。
- 资料对象。
- 绑定对象。
- 入文提案。

### P2：文章入口

必须实现：

- 导入文本。
- 段落编号。
- 原文解析。
- 原文对照。
- 转结构提案。

## 10. 判断标准

下一版不以“按钮能点”为完成标准，而以这些问题是否能回答为完成标准：

- 现在用户处在哪个动作链？
- 当前动作为什么可用或不可用？
- 点击后会新增、修改还是删除什么？
- 是否会影响已批准内容？
- 是否会影响逐字稿？
- 是否会影响 HTML？
- 是否会影响锁定版？
- 失败后能否回退？
- 能否替换 HTML 生成 API 并测试？
- 生成 HTML 前能否预览？

如果不能回答，就是链条没建好。
