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
- HTML 预览 → 审阅 → 锁定的完整两阶段流程。
- 三栏工作台提供大纲、内容、意见、资料入口和记忆视图。
- 内容版本追踪与乐观锁冲突检测。

当前使用确定性的本地 Provider，用于验证调度、审批与版本保护。它不会伪造互联网检索结果；真实模型与双源检索通过现有 Provider 接口接入。

## 运行

```bash
python -m app.server --port 4173
```

打开 `http://127.0.0.1:4173`。

要求 Python 3.12+，零第三方依赖。

## 测试

```bash
python -m unittest discover -s tests -v
```

## DeepSeek 配置

未设置 `DEEPSEEK_API_KEY` 时，系统使用本地模拟 Provider，适合测试完整界面、审批和版本流程。

需要测试真实模型时，在当前终端会话中设置环境变量：

**Windows (PowerShell):**
```powershell
$env:DEEPSEEK_API_KEY = Read-Host "DeepSeek API key"
$env:DEEPSEEK_MODEL = "deepseek-v4-flash"
python -m app.server --port 4173
```

**macOS / Linux:**
```bash
export DEEPSEEK_API_KEY="your-key-here"
export DEEPSEEK_MODEL="deepseek-v4-flash"
python -m app.server --port 4173
```

可选配置见 `.env.example`。应用不会自动读取 `.env`，密钥只从启动进程的环境变量获取。`/api/health` 只返回 Provider 和模型名称，不返回密钥。

## 项目结构

```
app/
  domain.py        —— 域模型：项目状态、内容节点、提案、成果、事件
  store.py         —— 追加式 JSONL 事件存储、状态重放、乐观锁
  agents.py        —— Agent 交付协议与确定性本地 Provider
  orchestrator.py  —— 总控调度、质量检查、提案管理、记忆投影
  server.py        —— HTTP API 与静态文件服务
  html_provider.py —— HTML 生成 Provider 接口
  aesthetic_html.py —— 四种美学范式的 Markdown → HTML 引擎
  deepseek.py      —— DeepSeek API Provider 实现
  provider_config.py —— 环境变量配置解析
web/
  index.html       —— 三栏工作台界面
  styles.css       —— 响应式布局与视觉系统
  app.js           —— 前端状态管理与 API 交互
  provider-status.js —— 顶部 Provider 状态指示器
tests/             —— 完整测试套件（11 个测试文件）
docs/              —— 产品设计文档与操作链定义
```
