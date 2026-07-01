# 叙构 MVP

Agent 原生 HTML 演示系统的第一条可运行纵向闭环。

## 当前能力

- 从主题和受众创建项目契约。
- 总控 Agent 调度内容、资料、视觉、创意四个专业 Agent。
- 所有 Agent 使用结构化交付协议，保留质量检查与不确定性。
- 总控生成待审修改提案，批准后才写入全量内容版。
- 事件以 JSONL 追加保存，可重新投影项目状态。
- 自动生成项目 `memory.md` 视图。
- 创建不可覆盖的锁定成果。
- 三栏工作台提供大纲、内容、意见、资料入口和记忆视图。

当前使用确定性的本地 Provider，用于验证调度、审批与版本保护。它不会伪造互联网检索结果；真实模型与双源检索通过现有 Provider 接口接入。

## 运行

```powershell
& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m app.server --port 4173
```

打开 `http://127.0.0.1:4173`。

## 测试

```powershell
& 'C:\Users\Lenovo\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe' -m unittest discover -s tests -v
```
