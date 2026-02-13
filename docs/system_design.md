# Project Manager Skill v3.0 - System Design Document (SDD)

## 1. 架构设计 (Architecture Design)

本系统采用 **模块化 CLI 架构 (Modular CLI Architecture)**，以 Python 为核心语言，通过 `argparse` 分发指令，底层通过 `subprocess` 调用 GitHub CLI (`gh`) 与远程仓库交互。

### 1.1 系统架构图 (Architecture Diagram)

```mermaid
graph TD
    User[用户 / 聊天界面] -->|指令| Entry[main.py (CLI入口)]
    
    subgraph 核心逻辑层 (Core Logic)
        Entry --> PhaseMgr[阶段管理器 (PhaseManager)]
        Entry --> ResourceMgr[资源管理器 (ResourceManager)]
        Entry --> SyncMgr[同步管理器 (SyncManager)]
        Entry --> IntelEngine[智能引擎 (IntelligenceEngine)]
    end
    
    subgraph 连接器层 (Connectors)
        PhaseMgr --> GitHubConn[GitHub连接器 (GitHubConnector)]
        SyncMgr --> GitHubConn
        GitHubConn -->|执行| GH_CLI[GitHub命令行工具 (gh)]
    end
    
    subgraph 数据与配置层 (Data & Config)
        ResourceMgr --> TeamConf[data/team.json (团队配置)]
        IntelEngine --> SysConf[data/config.json (系统配置)]
        SyncMgr --> LocalMD[本地Markdown文件]
    end
    
    subgraph 外部服务层 (External Services)
        GH_CLI -->|API调用| GitHub[GitHub API服务]
        IntelEngine -->|API调用| LLM[OpenAI / LLM API服务]
    end
    
    subgraph 输出层 (Output)
        Entry --> ReportGen[报表生成器 (ReportGenerator)]
        ReportGen --> MarkdownReport[Markdown状态报告]
    end
```

### 1.2 目录结构 (Directory Structure)

```
skills/project-manager/
├── src/
│   ├── main.py              # 统一入口 (CLI Dispatcher)
│   ├── core/                # 核心业务逻辑
│   │   ├── phase.py         # 阶段流转与门禁控制
│   │   ├── resource.py      # 资源管理与技能匹配
│   │   ├── sync.py          # 双向状态同步
│   │   └── intelligence.py  # 混合动力 AI 引擎
│   ├── connectors/          # 外部接口适配
│   │   └── github.py        # GitHub API 封装 (含重试机制)
│   ├── reports/             # 报表生成
│   │   └── report.py        # Markdown/Mermaid 生成器
│   └── utils/               # 通用工具
├── data/                    # 配置文件
│   ├── config.json          # 系统配置 (LLM Key, Mode)
│   └── team.json            # 团队资源配置 (Skills, Roles)
└── scripts/
    └── project_control.py   # 软链接至 src/main.py
```

---

## 2. 功能模块设计 (Functional Modules)

### 2.1 智能立项模块 (Scaffold & Intelligence)
*   **功能**: 将自然语言需求转化为结构化的任务清单。
*   **逻辑**:
    1.  **输入**: 原始需求文本 (如 "Build a Secure Login API")。
    2.  **分析**: `IntelligenceEngine` 识别领域 (API, Security, UI)。
        *   **Heuristic Mode**: 关键词匹配 -> 模板填充。
        *   **LLM Mode**: 调用 OpenAI 接口 -> 生成 JSON 任务列表。
    3.  **输出**: Markdown 格式的需求文档，包含初步标签和预判负责人。

### 2.2 资源调度模块 (Resource Management)
*   **功能**: 基于技能匹配自动指派任务。
*   **逻辑**:
    1.  **加载**: 读取 `data/team.json`。
    2.  **匹配**: `find_best_assignee(tags)`。
        *   计算每个成员的 `Skill Score` (技能关键词命中数)。
    3.  **决策**: 返回得分最高的成员 ID；若无匹配，执行随机/轮询兜底。

### 2.3 阶段流转模块 (Phase Control)
*   **功能**: 管理项目生命周期 (Requirement -> Design -> Dev -> Test)。
*   **逻辑**:
    1.  **Gate Check**: 检查当前阶段所有任务是否 Closed。
    2.  **Traceability**: 读取上一阶段 Closed 任务作为 Parent。
    3.  **Transition**: 批量创建下一阶段任务，并写入 `Derived from #ID` 到 Body 中，建立追溯链。

### 2.4 双向同步模块 (Sync)
*   **功能**: 保持 Local File 与 Remote Issue 状态一致。
*   **逻辑**:
    *   **Remote Closed -> Local Check**: 更新 Markdown `[ ]` 为 `[x]`。
    *   **Local Check -> Remote Close**: 调用 `gh issue close`。
    *   **Idempotency**: 基于 Issue ID (`#123`) 进行精确匹配，防止重复操作。

---

## 3. 端到端数据流设计 (End-to-End Data Flow)

### 3.1 阶段流转全景 (Lifecycle Data Flow)

本系统实现了 **从需求到交付 (Requirement-to-Delivery)** 的全流程闭环管理。数据在不同阶段之间通过 **Issue Linking (Issue 关联)** 进行传递。

**Phase 1: 需求阶段 (Requirement Phase)**
1.  **Input**: 用户自然语言需求 (`scaffold --req "Build CRM"`)。
2.  **Process**: `IntelligenceEngine` 生成结构化 Markdown。
3.  **Storage**: 本地 `requirements.md`。
4.  **Transition**: `import` 命令读取 MD，调用 GitHub API 创建 Issue (Label: `type:requirement`)。
5.  **Output**: GitHub Issue #1 (Status: Open)。

**Phase 2: 设计阶段 (Design Phase)**
1.  **Trigger**: 用户确认需求冻结，执行 `launch --from requirement --to design`。
2.  **Gate Check**: `PhaseManager` 扫描所有 `type:requirement` Issue，确保状态为 `Closed`。
3.  **Process**:
    *   读取 Requirement Issue #1 (Title, Body)。
    *   生成 Design Task 对象: `{"title": "Design for #1", "parent_id": 1}`。
    *   `IntelligenceEngine` 补充设计检查项 (Checklist)。
4.  **Action**: 创建 Design Issue #2 (Label: `type:design`)。
5.  **Traceability**: 在 Issue #2 Body 中写入 `> Derived from #1`，建立追溯链。

**Phase 3: 开发阶段 (Development Phase)**
1.  **Trigger**: 设计评审通过，执行 `launch --from design --to dev`。
2.  **Gate Check**: 确保所有 Design Issue 已 Closed。
3.  **Process**:
    *   读取 Design Issue #2。
    *   生成 Dev Task 对象: `{"title": "Implement #2", "parent_id": 2}`。
    *   `ResourceManager` 根据技能标签自动指派开发者。
4.  **Action**: 创建 Dev Issue #3 (Label: `type:dev`)，关联至 #2。

**Phase 4: 测试阶段 (Test Phase)**
1.  **Trigger**: 开发完成，执行 `launch --from dev --to test`。
2.  **Gate Check**:
    *   确保所有 Dev Issue 已 Closed。
    *   **CI Check**: 调用 GitHub Actions API，检查最近一次构建是否 Success。若失败，拦截流转。
3.  **Process**: 生成 Test Case Issue #4 (Label: `type:test`)，关联至 #3。

---

## 4. 关键技术详解 (Key Technologies Deep Dive)

### 4.1 混合动力 AI 引擎 (Hybrid Intelligence Engine)
*   **架构模式**: 策略模式 (Strategy Pattern)。
*   **实现机制**:
    *   **LLM Strategy**: 通过 `urllib` 封装 OpenAI 兼容接口调用。构建 Prompt 模板，要求模型返回标准 JSON 格式的任务列表。支持 `retry` 机制处理 API 超时。
    *   **Heuristic Strategy (Fallback)**: 基于关键词加权算法。预定义领域词库 (Domain Dictionary)，如 `{"api": ["rest", "endpoint"], "security": ["auth", "jwt"]}`。命中关键词后，从本地 JSON 模板库中提取对应任务。
*   **优势**: 解决了纯规则引擎的僵化问题，同时通过本地降级方案保证了系统的鲁棒性 (Robustness)。

### 4.2 全链路追溯系统 (Traceability System)
*   **核心思想**: 不依赖外部数据库，将 GitHub Issue 本身作为元数据存储介质。
*   **数据结构**: 在 Issue Body 中嵌入结构化元数据块 (Metadata Block)。
    ```markdown
    ## Technical Detail
    ...
    > **Traceability**: Derived from #123
    > **Phase**: Design
    ```
*   **解析算法**: `ReportGenerator` 使用正则表达式 `r"Derived from #(\d+)"` 提取父子关系，构建 **有向无环图 (DAG)**，最终生成追溯矩阵报表。

### 4.3 智能资源调度算法 (Smart Resource Scheduling)
*   **算法逻辑**: 加权匹配算法 (Weighted Matching)。
    1.  **标签提取**: 从任务标题中提取标签 (如 `domain:api`, `type:test`)。
    2.  **技能评分**: 遍历 `team.json`，计算每个成员技能集与任务标签的 **Jaccard 相似度** 或简单重叠数。
    3.  **负载均衡**: 在得分相同的情况下，优先选择当前 `active_tasks` 数量最少的成员 (需实时查询 GitHub 状态)。
    4.  **兜底策略**: 若无匹配，采用随机轮询 (Round-Robin) 避免任务积压。

### 4.4 幂等性与并发控制 (Idempotency & Concurrency)
*   **幂等性设计**: 在 `import` 和 `sync` 操作中，通过 Issue ID (`#123`) 或 Title Hash 进行去重检查。重复执行命令不会导致重复创建 Issue。
*   **API 限流处理**: 封装 `GitHubConnector`，内置指数退避 (Exponential Backoff) 算法，处理 GitHub API 的 `429 Too Many Requests` 和 `50x` 错误。

---

## 5. 定时任务与自动化巡检 (Cron & Automated Inspection)

为了确保项目状态的实时性和风险的及时发现，本系统支持通过系统级定时任务 (Cron) 或 CI/CD Pipeline 触发自动化巡检。

### 5.1 巡检策略 (Inspection Strategy)

| 任务类型 | 频率 (Frequency) | 触发命令 (Command) | 检查内容 (Checklist) |
| :--- | :--- | :--- | :--- |
| **每日风险扫描** (Daily Scan) | 每天 09:00 AM | `status --repo {repo} --out daily_risk.md` | 1. **Overdue**: 检查已逾期任务。<br>2. **Overload**: 检查单人任务数 > 5。<br>3. **Unassigned**: 检查无负责人任务。 |
| **双向同步检查** (Sync Check) | 每小时 (Hourly) | `sync --repo {repo} --file {doc}` | 1. **Remote -> Local**: 拉取 Closed 状态。<br>2. **Local -> Remote**: 推送 Local `[x]` 状态。<br>3. **Conflict**: 记录冲突日志。 |
| **周报生成** (Weekly Report) | 每周五 17:00 PM | `status --repo {repo} --out weekly_report.md` | 1. **Progress**: 本周完成任务数 / 总任务数。<br>2. **Burndown**: 燃尽图趋势。<br>3. **Traceability**: 全链路追溯矩阵。 |

### 5.2 自动化部署建议 (Deployment Suggestion)

建议在服务器或 CI/CD 环境中配置 Crontab：

```bash
# Crontab Example
0 9 * * 1-5 python3 skills/project-manager/scripts/project_control.py status --repo my-org/crm --out reports/daily_$(date +\%F).md
0 * * * * python3 skills/project-manager/scripts/project_control.py sync --repo my-org/crm --file requirements.md
0 17 * * 5 python3 skills/project-manager/scripts/project_control.py status --repo my-org/crm --out reports/weekly_$(date +\%W).md
```

---

## 6. 接口与指令集 (Interface & Commands)

| Command | Arguments | Description |
| :--- | :--- | :--- |
| `init` | `--repo`, `--desc` | 初始化仓库，创建标准 Label 体系。 |
| `scaffold` | `--req`, `--out` | 智能生成需求文档 (Markdown)。 |
| `import` | `--file`, `--repo` | 将本地文档导入为 GitHub Issues。 |
| `launch` | `--repo`, `--from`, `--to` | 执行阶段流转 (含 Gate Check 和 Traceability)。 |
| `sync` | `--repo`, `--file` | 双向同步任务状态。 |
| `status` | `--repo`, `--out` | 生成包含燃尽图、追溯矩阵的 Markdown 报表。 |

---

## 6. 数据结构 (Data Structures)

### 6.1 Team Configuration (`team.json`)
```json
{
  "members": [
    {
      "id": "github_username",
      "role": "Backend",
      "skills": ["python", "api", "aws"],
      "status": "active" // active, busy, leave
    }
  ]
}
```

### 6.2 System Configuration (`config.json`)
```json
{
  "intelligence": {
    "mode": "llm", // or "heuristic"
    "provider": "openai",
    "model": "gpt-4",
    "api_key_env": "OPENAI_API_KEY"
  }
}
```

### 6.3 Task Metadata (In-Memory / GitHub Issue)
```python
{
    "title": "Design API Specification",
    "body": "Detailed description...\n\n> **Traceability**: Derived from #123",
    "labels": ["type:design", "domain:api"],
    "assignees": ["dev-01"],
    "state": "open",
    "parent_id": 123 // Parsed from body
}
```
