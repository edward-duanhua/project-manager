# 全流程项目管理示例剧本

这是一个基于 **自然语言指令 (NLI)** 的全流程演示剧本。展示了 `project-manager` 技能如何覆盖软件工程从立项到交付的全生命周期。

**剧本背景**：
*   **项目**：开发一个企业级“员工考勤系统”。
*   **角色**：项目发起人（User） vs 智能项目经理（Agent）。
*   **交互方式**：用户只下达自然语言指令，Agent 负责调用底层工具链。

---

## 🎬 第一阶段：立项与初始化 (Project Initiation)
**场景**：项目刚启动，你需要准备基础设施。

> **User**: "帮我新建一个 GitHub 私有仓库，名字叫 `staff-attendance`，用来做公司的考勤系统。"

**🤖 Agent**:
*   **思考**: 识别意图 `init_repo`。
*   **行动**: `python3 project_control.py init --name staff-attendance --desc "企业员工考勤系统" --private --org my-company`
*   **反馈**: "✅ 仓库 `my-company/staff-attendance` 已初始化完成，主分支已建立。URL: https://github.com/my-company/staff-attendance"

---

## 🎬 第二阶段：需求分析 (Requirements Analysis)
**场景**：你需要快速梳理需求文档，并转化为待办任务。

> **User**: "这个系统主要功能是：员工打卡（支持GPS和WiFi）、请假审批流、还有管理员的考勤报表导出。帮我生成一份需求清单。"

**🤖 Agent**:
*   **思考**: 识别意图 `scaffold_requirements`。
*   **行动**: `python3 project_control.py scaffold --out requirements.md --req "员工打卡(GPS/WiFi), 请假审批流, 管理员报表导出"`
*   **反馈**: "已生成 `requirements.md`，包含 5 个核心功能点。是否需要补充？"

> **User**: "没问题，直接导入到 GitHub 吧，先把‘请假审批’指派给 @backend-lead。"

**🤖 Agent**:
*   **思考**: 识别意图 `import_requirements` + 文件编辑。
*   **行动**:
    1.  `edit requirements.md` (修改指派人)。
    2.  `python3 project_control.py import --file requirements.md --repo my-company/staff-attendance`
*   **反馈**: "🚀 需求导入成功！已创建 Issue #1 ~ #5。文档已更新并关联了 Issue ID。"

---

## 🎬 第三阶段：方案设计 (System Design)
**场景**：需求明确后，不能马上写代码，需要先做技术设计。

> **User**: "需求都已经确认了，让大家开始做**技术方案设计**吧。"

**🤖 Agent**:
*   **思考**: 识别意图 `launch_phase` (Req -> Design)。
*   **行动**: `python3 project_control.py launch --repo ... --from-phase requirement --to-phase design`
*   **系统逻辑**: 检查需求 Issue 状态 -> 批量创建设计任务（如“设计方案：GPS打卡算法”）。
*   **反馈**: "✅ 设计阶段已启动。根据现有的 5 个需求，生成了 5 个对应的‘方案设计’任务，并已通知相关负责人开始撰写架构文档。"

---

## 🎬 第四阶段：开发实施 (Development Implementation)
**场景**：设计评审通过，正式进入编码阶段。

> **User**: "设计方案评审通过了，**启动开发**！"

**🤖 Agent**:
*   **思考**: 识别意图 `launch_phase` (Design -> Dev)。
*   **行动**: `python3 project_control.py launch --repo ... --from-phase design --to-phase dev`
*   **系统逻辑**: 验证所有设计任务已 Close -> 批量创建开发任务（如“开发实现：GPS打卡接口”）。
*   **反馈**: "🚀 开发阶段正式启动！已创建编码任务。请大家关注 GitHub Project 看板。"

---

## 🎬 第五阶段：日常监控与干预 (Monitoring & Control)
**场景**：开发过程中，你需要了解进度并处理突发状况。

> **User**: "汇报一下这周的**开发进度**，有没有什么风险？"

**🤖 Agent**:
*   **思考**: 识别意图 `status` + `risk`。
*   **行动**:
    1.  `python3 project_control.py status ...`
    2.  `python3 project_control.py risk ...`
*   **反馈**:
    *   "📊 **开发进度 40%**。‘打卡接口’已完成，‘报表导出’正在进行中。"
    *   "⚠️ **风险预警**：‘请假审批流’关联的 PR 已经 3 天没有提交代码了（僵尸 PR），且负责人 @backend-lead 当前有 5 个并发任务，可能负载过高。"

> **User**: "确实有点慢。帮我催一下 @backend-lead，让他先把审批流搞定，报表可以放一放。"

**🤖 Agent**:
*   **思考**: 识别意图 `remind_issue`。
*   **行动**: `python3 project_control.py remind --repo ... --id <审批流IssueID> --msg "优先处理此任务，报表可延后。 @backend-lead"`
*   **反馈**: "✅ 已发送催办提醒。"

---

## 🎬 第六阶段：会议闭环 (Meeting & Action)
**场景**：针对开发中的问题开了一个短会，产生了新的待办。

> **User**: "刚开会决定增加一个‘补卡申请’的功能，下周五前完成，交给 @new-guy。"

**🤖 Agent**:
*   **思考**: 识别意图 `process_meeting_notes` (或者直接作为新需求处理)。
*   **行动**:
    1.  `write temp_note.md` (内容: `- [ ] 增加补卡申请功能 @new-guy due:下周五`)
    2.  `python3 project_control.py meeting --file temp_note.md ...`
*   **反馈**: "📝 已识别并创建 Action Item：‘补卡申请’ (Issue #15)，截止日期已设置为 2026-02-20。"

---

## 🎬 第七阶段：测试与验收 (Testing & Delivery)
**场景**：开发任务全部完成，进入测试。

> **User**: "开发任务都 Close 了，**启动测试**吧。"

**🤖 Agent**:
*   **思考**: 识别意图 `launch_phase` (Dev -> Test)。
*   **行动**: `python3 project_control.py launch --repo ... --from-phase dev --to-phase test`
*   **系统逻辑**: 门禁检查（开发任务 100% 完成） -> 批量创建测试任务（如“编写测试用例：打卡功能”）。
*   **反馈**: "✅ 开发阶段任务已全部清零。🚀 测试阶段启动，已自动生成了对应功能的测试用例任务，请 QA 团队介入。"
