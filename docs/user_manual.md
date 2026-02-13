# Project Manager Skill v3.0 - User Manual (用户手册)

## 1. 简介 (Introduction)

Project Manager Skill v3.0 是一款基于 CLI (命令行) 和 AI (人工智能) 的智能研发项目管理助手。它通过自动化脚本、双向同步和智能化策略，帮助研发团队实现从立项到交付的全流程管理。

本手册将指导您完成环境配置、项目初始化，并通过一个完整的 NLI (自然语言指令) 演示剧本，展示如何使用该技能高效管理项目。

---

## 2. 环境准备 (Prerequisites)

在开始之前，请确保您的环境满足以下要求：

*   **Operating System**: Linux / macOS (推荐) / Windows (WSL)
*   **Python**: Python 3.8+
*   **GitHub CLI (`gh`)**: 必须安装并已登录 (`gh auth login`)
*   **Git**: 已安装

### 2.1 安装依赖 (Install Dependencies)

无需额外的 `pip install`，本项目仅依赖 Python 标准库。只需确保 `gh` CLI 可用。

```bash
gh --version
# gh version 2.40.0 (2023-10-24)
```

---

## 3. 配置初始化 (Configuration)

### 3.1 团队配置 (`team.json`)

在 `skills/project-manager/data/team.json` 中配置您的团队成员及其技能标签。这将用于智能任务指派。

```json
{
  "members": [
    {
      "id": "your-github-username",
      "role": "PM",
      "skills": ["manage", "review", "python", "api"],
      "status": "active"
    },
    {
      "id": "dev-01",
      "role": "Backend",
      "skills": ["java", "spring", "mysql"],
      "status": "active"
    }
  ]
}
```

### 3.2 智能引擎配置 (`config.json`)

在 `skills/project-manager/data/config.json` 中选择 AI 模式。

*   **Heuristic Mode (默认)**: 免费，基于规则匹配。
*   **LLM Mode (高级)**: 需要 OpenAI API Key。

```json
{
  "intelligence": {
    "mode": "heuristic", // 或 "llm"
    "provider": "openai",
    "model": "gpt-4",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

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
*   GitHub 仓库创建成功。
*   标准标签体系 (`type:requirement`, `type:design`, `type:dev`, `type:test`) 自动创建。

### 4.2 Phase 2: 需求规划 (Planning / Scaffold)

**User (NLI)**: "老K，这系统需要支持客户录入、销售漏斗管理、报表导出，并且要把 API 安全性放在首位。"

**Agent Action**:
```bash
python3 skills/project-manager/scripts/project_control.py scaffold --req "CRM with Customer Entry, Sales Funnel, Report Export, and High Security API" --out requirements.md
```
**Result**:
*   生成 `requirements.md`，内容包含：
    *   `- [ ] Design Secure API Authentication (OAuth2) (type:design,domain:security)`
    *   `- [ ] Implement Customer CRUD API (type:dev,domain:api)`
    *   `- [ ] Create Sales Funnel Dashboard (type:dev,domain:ui)`
*   AI 自动补充了隐性需求 (如 "Setup CI/CD Pipeline")。

### 4.3 Phase 3: 需求导入与指派 (Import & Assign)

**User (NLI)**: "老K，把这份需求导入到 GitHub 上，分给合适的弟兄们。"

**Agent Action**:
```bash
python3 skills/project-manager/scripts/project_control.py import --file requirements.md --repo my-org/crm-system
```
**Result**:
*   系统解析 Markdown。
*   **智能指派**: "API" 相关任务分给 `dev-01` (Backend)，"UI" 相关分给 `dev-02` (Frontend)。
*   GitHub Issues 创建成功。

### 4.4 Phase 4: 需求冻结与设计启动 (Freeze & Launch)

*(经过一周的评审，需求已确认)*

**User (NLI)**: "老K，需求都确认了，把它们冻结，然后启动设计阶段。"

**Agent Action**:
1.  **Freeze**: (Manual or Script) 关闭所有 `type:requirement` Issues。
2.  **Launch**:
    ```bash
    python3 skills/project-manager/scripts/project_control.py launch --repo my-org/crm-system --from requirement --to design
    ```

**Result**:
*   **Gate Check**: 系统检查确认所有需求 Issue 已 Closed。
*   **Traceability**: 自动创建下一阶段 `type:design` 任务，并在 Body 中写入 `> Derived from #IssueID`。
*   **Notification**: "Transition Complete. 15 design tasks created."

### 4.5 Phase 5: 方案设计与开发启动 (Design Freeze & Dev Launch)

*(设计团队完成了所有的技术方案设计)*

**User (NLI)**: "老K，设计方案都评审过了，没问题。把它们关了，开始写代码！"

**Agent Action**:
1.  **Freeze**: 关闭所有 `type:design` Issues。
2.  **Launch**:
    ```bash
    python3 skills/project-manager/scripts/project_control.py launch --repo my-org/crm-system --from design --to dev
    ```

**Result**:
*   **Gate Check**: 确认所有设计任务已 Closed。
*   **Traceability**: 自动创建 `type:dev` 任务 (如 "Implement Customer CRUD")，关联至对应的 Design 父任务。
*   **Assignment**: 自动指派给 Backend/Frontend 开发者。

### 4.6 Phase 6: 开发交付与测试启动 (Dev Handover & Test Launch)

*(开发完成，代码已合入主分支，CI 构建通过)*

**User (NLI)**: "老K，代码都撸完了，准备提测。"

**Agent Action**:
1.  **Freeze**: 关闭所有 `type:dev` Issues。
2.  **Launch**:
    ```bash
    python3 skills/project-manager/scripts/project_control.py launch --repo my-org/crm-system --from dev --to test
    ```

**Result**:
*   **Gate Check**:
    *   检查所有 Dev 任务是否 Closed。
    *   **CI Check**: 自动调用 GitHub Actions API，检查最近一次构建是否成功。若失败，拒绝转测。
*   **Traceability**: 自动创建 `type:test` 任务 (如 "Test Customer CRUD")。

### 4.7 Phase 7: 状态跟踪与同步 (Tracking & Sync)

*(开发过程中，团队成员在 GitHub 上更新了状态)*

**User (NLI)**: "老K，同步一下最新的进度，顺便出个周报。"

**Agent Action**:
1.  **Sync**:
    ```bash
    python3 skills/project-manager/scripts/project_control.py sync --repo my-org/crm-system --file requirements.md
    ```
    *(本地 `requirements.md` 中的 `[ ]` 自动变为 `[x]`)*

2.  **Report**:
    ```bash
    python3 skills/project-manager/scripts/project_control.py status --repo my-org/crm-system --out WEEKLY_REPORT.md
    ```

**Result**:
*   生成 `WEEKLY_REPORT.md`，包含：
    *   **燃尽图 (Burndown Chart)**
    *   **全链路追溯矩阵 (Traceability Matrix)**
    *   **风险预警 (Risk Radar)**: "⚠️ Task #23 is Overdue!"

---

## 5. 常见问题 (FAQ)

**Q: 如果 GitHub API 连不上怎么办？**
A: `GitHubConnector` 内置了重试机制 (Retries=3)。如果彻底断网，请检查网络连接或 VPN 设置。

**Q: 如何修改团队成员？**
A: 直接编辑 `skills/project-manager/data/team.json`，无需重启。

**Q: 支持自定义标签吗？**
A: 支持。在 `scaffold` 生成的 Markdown 中手动修改标签即可 (如 `type:research`)，系统会原样导入。
