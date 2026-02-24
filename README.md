# Project Manager Skill v3.1 - User Manual (用户手册)

## 1. 简介 (Introduction)

Project Manager Skill v3.1 是一款基于 CLI (命令行) 和 AI (人工智能) 的智能研发项目管理助手。它通过自动化脚本、双向同步和智能化策略，帮助研发团队实现从立项到交付的全流程管理。

**v3.1 新特性：**
*   **多平台支持**：全面支持 **GitHub** 和 **GitCode** (v5 API)。
*   **增强的兼容性**：针对 GitCode API 路径特性进行了深度优化。
*   **安全增强**：支持 `.env` 环境变量文件，避免 Token 硬编码。

本手册将指导您完成环境配置、项目初始化，并通过一个完整的 NLI (自然语言指令) 演示剧本，展示如何使用该技能高效管理项目。

---

## 2. 环境准备 (Prerequisites)

在开始之前，请确保您的环境满足以下要求：

*   **Operating System**: Linux / macOS (推荐) / Windows (WSL)
*   **Python**: Python 3.8+
*   **Provider CLI/Token**:
    *   **GitHub**: 安装 `gh` CLI 并登录 (`gh auth login`)，或设置 `GITHUB_TOKEN` 环境变量。
    *   **GitCode**: 设置 `GITCODE_TOKEN` 环境变量。
*   **Dependencies**: 推荐安装 `python-dotenv`。
    ```bash
    pip install python-dotenv requests
    ```

### 2.1 环境变量配置 (.env)

复制模板并配置您的 Token：

```bash
cp skills/project-manager/.env.example skills/project-manager/.env
# 编辑 .env 文件，填入您的真实 Token
```

---

## 3. 配置初始化 (Configuration)

### 3.1 平台选择 (`config.json`)

在 `skills/project-manager/data/config.json` 中配置首选的代码托管平台。

```json
{
  "source_control": {
    "provider": "gitcode", // 或 "github"
    "gitcode_token_env": "GITCODE_TOKEN",
    "github_token_env": "GITHUB_TOKEN"
  }
}
```

### 3.2 团队配置 (`team.json`)

在 `skills/project-manager/data/team.json` 中配置您的团队成员及其技能标签。这将用于智能任务指派。

```json
{
  "members": [
    {
      "id": "your-username",
      "role": "PM",
      "skills": ["manage", "review", "python", "api"],
      "status": "active"
    }
  ]
}
```

### 3.3 智能引擎配置

支持 **Heuristic Mode (规则)** 和 **LLM Mode (AI)**。配置 `intelligence` 字段以启用 AI 辅助需求拆解。

---

## 4. 全流程演示剧本 (End-to-End Demo Script)

本剧本模拟了一个 **“企业级CRM系统开发”** 项目的全生命周期。

**假设场景**: 您是项目经理 (PM)，我是您的智能助手 (Agent)。

### 4.1 Phase 1: 项目立项 (Initiation)

**User (NLI)**: "老K，帮我初始化一个新的私有仓库 `my-org/crm-system`，用于客户关系管理系统。"

**Agent Action**:
```bash
python3 skills/project-manager/scripts/project_control.py init --repo my-org/crm-system --desc "Enterprise CRM System"
```
**Result**:
*   仓库创建成功（支持 GitHub 或 GitCode）。
*   标准标签体系 (`type:requirement`, `type:design`, `type:dev`, `type:test`) 自动创建。

### 4.2 Phase 2: 需求规划 (Planning / Scaffold)

**User (NLI)**: "老K，这系统需要支持客户录入、销售漏斗管理、报表导出，并且要把 API 安全性放在首位。"

**Agent Action**:
```bash
python3 skills/project-manager/scripts/project_control.py scaffold --req "CRM with Customer Entry, Sales Funnel, Report Export, and High Security API" --out requirements.md
```
**Result**:
*   生成 `requirements.md`，包含 AI 拆解的任务、估算和验收标准。
*   AI 自动识别安全需求，生成 `Design Secure API Authentication` 等任务。

### 4.3 Phase 3: 需求导入与指派 (Import & Assign)

**User (NLI)**: "老K，把这份需求导入到仓库上，分给合适的弟兄们。"

**Agent Action**:
```bash
python3 skills/project-manager/scripts/project_control.py import --file requirements.md --repo my-org/crm-system
```
**Result**:
*   系统解析 Markdown。
*   **智能指派**: "API" 相关任务分给 Backend 开发，"UI" 相关分给 Frontend。
*   Issues 创建成功 (自动适配 GitCode v5 `/repos/:owner/:repo/issues` 路径)。

### 4.4 Phase 4: 需求冻结与设计启动 (Freeze & Launch)

*(需求确认后，流转至设计阶段)*

**Agent Action**:
```bash
python3 skills/project-manager/scripts/project_control.py launch --repo my-org/crm-system --from requirement --to design
```

**Result**:
*   **Traceability**: 自动创建下一阶段 `type:design` 任务，并在 Body 中写入 `> Derived from #IssueID`，建立追溯链。

### 4.5 Phase 5: 状态跟踪与同步 (Tracking & Sync)

**User (NLI)**: "老K，同步一下最新的进度，顺便出个周报。"

**Agent Action**:
1.  **Sync**: `project_control.py sync` (双向同步状态)
2.  **Report**:
    ```bash
    python3 skills/project-manager/scripts/project_control.py status --repo my-org/crm-system --out WEEKLY_REPORT.md
    ```

**Result**:
*   生成 `WEEKLY_REPORT.md`，包含进度统计、燃尽图数据和风险预警。

---

## 5. 常见问题 (FAQ)

**Q: GitCode 报错 404 Not Found?**
A: 请确保使用 `owner/repo` 格式的路径。v3.1 已修复了 API 路径问题，优先使用 `/repos/` 接口以获得更好兼容性。

**Q: 如何在没有 pip 的环境运行？**
A: 核心逻辑仅依赖标准库和 `requests`（通常系统自带）。`python-dotenv` 是可选的，如果缺失，脚本会尝试降级运行或报错提示。

**Q: 支持自定义标签吗？**
A: 支持。在 `scaffold` 生成的 Markdown 中手动修改标签即可 (如 `type:research`)，系统会原样导入。
