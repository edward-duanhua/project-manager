#!/usr/bin/env python3
import sys
import argparse
import json
import subprocess
import datetime
import random
import os
import re
import shutil

# Color codes for output
GREEN = '\033[92m'
YELLOW = '\033[93m'
RED = '\033[91m'
RESET = '\033[0m'

HISTORY_FILE = "skills/project-manager/data/history.json"
CONFIG_FILE = "skills/project-manager/data/config.json"

def log(message, level="INFO"):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if level == "INFO":
        print(f"[{timestamp}] {GREEN}INFO{RESET}: {message}")
    elif level == "WARNING":
        print(f"[{timestamp}] {YELLOW}WARNING{RESET}: {message}")
    elif level == "ERROR":
        print(f"[{timestamp}] {RED}ERROR{RESET}: {message}")

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            log("配置文件无效，使用默认设置。", "WARNING")
    
    # Defaults
    return {
        "sources": {
            "requirements": {"type": "github", "labels": ["type:requirement"]},
            "design": {"type": "github", "labels": ["type:design"]},
            "development": {"type": "github", "labels": ["type:dev"]}
        },
        "status_mapping": {
            "todo": ["status:todo", "triage"],
            "in_progress": ["status:wip", "in-progress", "working"],
            "review": ["status:review", "pr-open"],
            "done": ["status:done", "closed"]
        },
        "thresholds": {
            "overdue_grace_period_days": 0,
            "max_active_tasks_per_person": 3
        },
        "export": {
            "path": "reports"
        }
    }

CONFIG = load_config()

def normalize_status(issue_state, issue_labels):
    if issue_state == 'closed':
        return 'done'
    mapping = CONFIG.get('status_mapping', {})
    for status_key, keywords in mapping.items():
        for label in issue_labels:
            if label.lower() in keywords:
                return status_key
    return 'todo'

def fetch_local_file_tasks(path):
    if not os.path.exists(path):
        return []
    tasks = []
    try:
        with open(path, 'r') as f:
            content = f.read()
            lines = content.splitlines()
        for idx, line in enumerate(lines):
            match = re.search(r'- \[(x| )\] (.+)', line)
            if match:
                is_closed = match.group(1) == 'x'
                status = 'done' if is_closed else 'todo'
                title = match.group(2).strip()
                tasks.append({
                    "id": f"L{idx+1}",
                    "title": title,
                    "state": "closed" if is_closed else "open",
                    "status_detailed": status,
                    "assignee": "Local",
                    "due_date": None,
                    "labels": ["local"],
                    "source": "local"
                })
    except:
        pass
    return tasks

def update_local_file(path, tasks_to_update):
    if not os.path.exists(path): return
    try:
        with open(path, 'r') as f:
            lines = f.readlines()
        modified = False
        for task_id, new_status in tasks_to_update.items():
            try:
                line_idx = int(task_id[1:]) - 1
                if 0 <= line_idx < len(lines):
                    line = lines[line_idx]
                    if new_status == 'done':
                        new_line = re.sub(r'- \[ \]', '- [x]', line)
                    else:
                        new_line = re.sub(r'- \[x\]', '- [ ]', line)
                    if new_line != line:
                        lines[line_idx] = new_line
                        modified = True
            except: pass
        if modified:
            with open(path, 'w') as f:
                f.writelines(lines)
            log(f"已更新本地文件: {path}")
    except Exception as e:
        log(f"更新本地文件失败: {e}", "ERROR")

def fetch_github_tasks(repo, labels=None):
    try:
        # P1 Fix: explicitly ask for state=all to handle phase transitions correctly
        cmd = ["gh", "issue", "list", "--repo", repo, "--state", "all", "--json", "number,title,state,assignees,createdAt,milestone,labels", "--limit", "50"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        issues = json.loads(result.stdout)
        normalized = []
        for i in issues:
            assignee = i['assignees'][0]['login'] if i['assignees'] else "Unassigned"
            i_labels = [l['name'] for l in i.get('labels', [])]
            
            milestone = i.get('milestone')
            due_date = None
            if milestone and milestone.get('dueOn'):
                due_date = milestone.get('dueOn').split('T')[0]
                
            if labels and not any(l in i_labels for l in labels):
                continue
            
            detailed_status = normalize_status(i['state'].lower(), i_labels)
            normalized.append({
                "id": i['number'],
                "title": i['title'],
                "state": i['state'].lower(),
                "status_detailed": detailed_status,
                "assignee": assignee,
                "due_date": due_date,
                "labels": i_labels,
                "source": "github"
            })
        return normalized
    except:
        return []

def get_all_tasks(repo):
    all_tasks = []
    sources = CONFIG.get('sources', {})
    for phase, config in sources.items():
        if config.get('type') == 'github':
            tasks = fetch_github_tasks(repo, labels=config.get('labels', []))
        elif config.get('type') == 'local_file':
            tasks = fetch_local_file_tasks(config.get('path'))
        else:
            tasks = []
        for t in tasks:
            t['phase'] = phase
            all_tasks.append(t)
    if not all_tasks: 
        all_tasks = fetch_github_tasks(repo)
        for t in all_tasks:
            t['phase'] = 'general'
    return all_tasks

def check_dependencies(tasks):
    phases = {}
    for t in tasks:
        p = t.get('phase', 'general')
        if p not in phases: phases[p] = {'total': 0, 'done': 0}
        phases[p]['total'] += 1
        if t['status_detailed'] == 'done':
            phases[p]['done'] += 1
    phase_status = {p: (d['done'] == d['total'] and d['total'] > 0) for p, d in phases.items()}
    gate_rules = CONFIG.get('gate_rules', {
        'design': 'requirements',
        'development': 'design',
        'test': 'development'
    })
    blocked_tasks = {}
    for t in tasks:
        current_phase = t.get('phase', '').lower()
        dependency_phase = gate_rules.get(current_phase)
        if dependency_phase:
            is_dep_complete = phase_status.get(dependency_phase, False)
            if not is_dep_complete and t['status_detailed'] != 'done':
                blocked_tasks[str(t['id'])] = True
    return blocked_tasks

def sync_tasks(repo):
    log("🔄 开始深度双向同步任务状态 (Deep Sync)...")
    local_tasks = []
    sources = CONFIG.get('sources', {})
    local_source_path = None
    
    # 1. 识别本地源文件
    for _, config in sources.items():
        if config.get('type') == 'local_file':
            local_source_path = config.get('path')
            local_tasks.extend(fetch_local_file_tasks(local_source_path))
            
    if not local_source_path or not os.path.exists(local_source_path):
        log("未配置本地任务文件或文件不存在，跳过同步。", "WARNING")
        return

    # 2. 获取远程任务
    github_tasks = fetch_github_tasks(repo) 
    
    gh_map = {str(t['id']): t for t in github_tasks} # Key by Issue Number
    # 尝试通过标题匹配 (辅助)
    gh_title_map = {t['title']: t for t in github_tasks}
    
    # 3. 读取本地文件原始内容用于回写
    with open(local_source_path, 'r') as f:
        lines = f.readlines()
        
    updated_lines = lines.copy()
    changes_count = 0

    # 正则用于匹配本地行: - [x] Title #123
    # Group 1: x or space
    # Group 2: Title
    # Group 3: Issue ID (Optional)
    pattern = re.compile(r'- \[([ x])\] (.*?)(?: #(\d+))?$')

    # A. 遍历本地行，同步状态 (GitHub -> Local & Local -> GitHub)
    for idx, line in enumerate(lines):
        match = pattern.search(line.strip())
        if match:
            is_checked = match.group(1) == 'x'
            title = match.group(2).strip()
            issue_id = match.group(3)
            
            current_gh_task = None
            if issue_id and issue_id in gh_map:
                current_gh_task = gh_map[issue_id]
            elif title in gh_title_map:
                current_gh_task = gh_title_map[title]
            
            if current_gh_task:
                gh_is_closed = current_gh_task['state'] == 'closed'
                gh_number = current_gh_task['id']
                
                # 策略: 以最近变更或"完成"状态为准 (这里采用合并策略: 只要一方完成即视为完成)
                # 或者更严格: 如果状态不一致，根据配置决定谁是 Source of Truth。
                # 默认策略: GitHub 是权威，但如果本地勾选了，则尝试关闭 GitHub Issue。
                
                new_line = line
                
                # Case 1: GitHub 已关闭，本地未勾选 -> 更新本地
                if gh_is_closed and not is_checked:
                    log(f"同步: GitHub #{gh_number} 已完成 -> 更新本地勾选")
                    new_line = line.replace('- [ ]', '- [x]', 1)
                    changes_count += 1
                    
                # Case 2: 本地已勾选，GitHub 未关闭 -> 关闭 GitHub Issue
                elif is_checked and not gh_is_closed:
                    log(f"同步: 本地已完成 -> 关闭 GitHub Issue #{gh_number}")
                    subprocess.run(["gh", "issue", "close", str(gh_number), "--repo", repo], check=False, capture_output=True)
                    changes_count += 1
                
                # Case 3: 如果行内没有 ID，补上 ID
                if not issue_id:
                    # 只有当行尾没有 ID 时才添加
                    if not re.search(r'#\d+$', new_line.strip()):
                        new_line = new_line.rstrip() + f" #{gh_number}\n"
                        changes_count += 1
                
                updated_lines[idx] = new_line

    if changes_count > 0:
        with open(local_source_path, 'w') as f:
            f.writelines(updated_lines)
        log(f"✅ 双向同步完成，更新了 {changes_count} 处状态。")
    else:
        log("✅ 状态已是最新，无需同步。")


def save_history(repo, issues):
    today = datetime.date.today().strftime("%Y-%m-%d")
    history = {}
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except: pass
    total = len(issues)
    closed = len([i for i in issues if i['state'] == 'closed'])
    if repo not in history:
        history[repo] = []
    if not history[repo] or history[repo][-1]['date'] != today:
        history[repo].append({"date": today, "total": total, "closed": closed})
        history[repo] = history[repo][-30:]
        os.makedirs(os.path.dirname(HISTORY_FILE), exist_ok=True)
        with open(HISTORY_FILE, "w") as f:
            json.dump(history, f, indent=2)

def analyze_trends(repo):
    if not os.path.exists(HISTORY_FILE):
        return ""
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
        snapshots = history.get(repo, [])
        if len(snapshots) < 2:
            return ""
        diff = snapshots[-1]['closed'] - snapshots[-2]['closed']
        icon = "📈" if diff > 0 else ("📉" if diff < 0 else "➖")
        return f"\n### 📈 趋势分析\n- **完成任务:** {snapshots[-2]['closed']} -> {snapshots[-1]['closed']} ({icon} {diff:+})\n"
    except:
        return ""

def plan_project(repo, requirement_text):
    print(f"\n🧠 **正在进行智能项目规划 (AI Planner)...**")
    print(f"原始需求: {requirement_text}")
    
    # 使用简单的启发式规则增强任务生成 (以此作为基础，后续可对接真实LLM API)
    tasks = []
    
    # 1. 基础阶段
    tasks.append({"title": "[Req] 需求分析与规格说明书", "label": "type:requirement", "phase": "requirements", "days": 3})
    
    # 2. 根据关键词动态添加设计任务
    if any(k in requirement_text.lower() for k in ['ui', '界面', '前端', 'app', 'web']):
        tasks.append({"title": "[Design] UI/UX 原型设计", "label": "type:design", "phase": "design", "days": 4})
        tasks.append({"title": "[Dev] 前端页面开发", "label": "type:dev", "phase": "development", "days": 5})
        
    if any(k in requirement_text.lower() for k in ['api', '接口', '后端', '数据', '服务']):
        tasks.append({"title": "[Design] 数据库模型设计", "label": "type:design", "phase": "design", "days": 2})
        tasks.append({"title": "[Design] API 接口定义", "label": "type:design", "phase": "design", "days": 2})
        tasks.append({"title": "[Dev] 后端核心逻辑开发", "label": "type:dev", "phase": "development", "days": 7})

    # 3. 默认开发任务 (如果没匹配到特定关键词)
    if not any(t['phase'] == 'development' for t in tasks):
        tasks.append({"title": "[Dev] 功能模块开发", "label": "type:dev", "phase": "development", "days": 5})

    # 4. 测试与部署
    tasks.append({"title": "[Test] 单元测试与集成测试", "label": "type:test", "phase": "test", "days": 3})
    tasks.append({"title": "[Deploy] 环境部署与上线", "label": "type:ops", "phase": "deploy", "days": 1})
    
    # 5. 安全加固 (总是建议)
    tasks.append({"title": "[Sec] 安全审计与漏洞扫描", "label": "type:security", "phase": "security", "days": 2})

    
    while True:
        print(f"\n📋 **当前建议的项目拆解方案:**")
        current_date = datetime.date.today()
        for idx, task in enumerate(tasks):
            due_date = current_date + datetime.timedelta(days=task['days'])
            task['due_date'] = due_date.strftime("%Y-%m-%d")
            current_date = due_date
            print(f"{idx + 1}. [{task['phase']}] {task['title']} (预计: {task['days']}天)")

        print(f"\n------------------------------------------------")
        print(f"交互选项: ")
        print(f"  [a] 添加任务  [d] 删除任务  [m] 修改任务工时")
        print(f"  [y] 确认并在 GitHub 创建 Issue")
        print(f"  [q] 取消")
        
        choice = input("\n请输入指令: ").strip().lower()
        
        if choice == 'y':
            break
        elif choice == 'q':
            print("已取消操作。")
            return
        elif choice == 'a':
            title = input("请输入新任务标题: ")
            phase = input("请输入阶段 (requirements/design/dev/test): ")
            try:
                days = int(input("请输入预计工时(天): "))
                tasks.append({"title": title, "label": f"type:{phase}", "phase": phase, "days": days})
            except ValueError:
                print("工时输入无效。")
        elif choice == 'd':
            try:
                idx = int(input("请输入要删除的任务序号: ")) - 1
                if 0 <= idx < len(tasks):
                    removed = tasks.pop(idx)
                    print(f"已删除: {removed['title']}")
                else:
                    print("无效序号。")
            except ValueError:
                print("输入无效。")
        elif choice == 'm':
            try:
                idx = int(input("请输入任务序号: ")) - 1
                if 0 <= idx < len(tasks):
                    days = int(input(f"请输入 '{tasks[idx]['title']}' 的新工时(天): "))
                    tasks[idx]['days'] = days
                else:
                    print("无效序号。")
            except ValueError:
                print("输入无效。")
        else:
            print("未知指令。")

    print(f"\n🚀 开始创建 {len(tasks)} 个 GitHub Issues...")
    for task in tasks:
        try:
            cmd = ["gh", "issue", "create", "--repo", repo, "--title", task['title'], 
                   "--body", f"交互式规划任务。\n源需求: {requirement_text}\n预计工时: {task['days']}天\n截止日期: {task['due_date']}", 
                   "--label", task['label']]
            # 添加 assignee 为当前用户 (可选)
            # cmd.extend(["--assignee", "@me"]) 
            
            subprocess.run(cmd, check=True, capture_output=True)
            log(f"成功创建任务: {task['title']}")
        except subprocess.CalledProcessError as e:
            log(f"创建失败: {task['title']}", "ERROR")
            # print(e.stderr)
        except Exception as e:
            log(f"系统错误: {e}", "ERROR")

def remind_issue(repo, issue_id, message):
    try:
        # 优化：增强正则匹配，支持前后中文标点或空格
        # 匹配模式：@后跟GitHub用户名(支持连字符)，忽略紧随其后的标点符号
        assignee_match = re.search(r'@([a-zA-Z0-9-]+)(?:\s|$|[，。！？\.,!?])', message)
        
        if assignee_match:
            assignee = assignee_match.group(1)
            log(f"识别到负责人: {assignee}，正在尝试指派...")
            
            # 尝试指派
            assign_cmd = ["gh", "issue", "edit", str(issue_id), "--repo", repo, "--add-assignee", assignee]
            assign_res = subprocess.run(assign_cmd, check=False, capture_output=True, text=True)
            
            if assign_res.returncode == 0:
                log(f"✅ 已成功指派给 {assignee}")
            else:
                # 明确输出错误信息
                err_msg = assign_res.stderr.strip()
                log(f"⚠️ 指派失败: {err_msg}", "ERROR")
                print(f"{YELLOW}提示: 请确认 '{assignee}' 是该仓库的 Collaborator。{RESET}")

        # 发送评论
        subprocess.run(["gh", "issue", "comment", str(issue_id), "--repo", repo, "--body", message], check=True, capture_output=True)
        log(f"成功向 Issue #{issue_id} 发送提醒。")
        
    except subprocess.CalledProcessError as e:
        log(f"GitHub CLI 调用失败: {e}", "ERROR")
    except Exception as e:
        log(f"无法发送提醒: {str(e)}", "ERROR")

def process_meeting_notes(repo, content):
    log("正在解析会议纪要...")
    task_pattern = re.compile(r'- \[ \] (?:@(\w+)\s)?(.+)')
    actions = []
    lines = content.split('\n')
    for line in lines:
        match = task_pattern.search(line)
        if match:
            assignee = match.group(1)
            title = match.group(2).strip()
            due_date = None
            due_match = re.search(r'due:(\d{4}-\d{2}-\d{2})', title)
            if due_match:
                due_date = due_match.group(1)
                title = title.replace(due_match.group(0), "").strip()
            actions.append({"title": title, "assignee": assignee, "due_date": due_date})
    if not actions: 
        log("未发现待办事项", "WARNING")
        return
    print(f"\n📋 **识别到 {len(actions)} 个待办事项:**")
    for task in actions:
        print(f"- {task['title']} [@{task['assignee'] or '未分配'}]")
    confirm = input("\n是否创建 GitHub Issues? (y/n): ")
    if confirm.lower() != 'y': return
    for task in actions:
        try:
            cmd = ["gh", "issue", "create", "--repo", repo, "--title", task['title'], "--body", f"From Meeting Notes.", "--label", "type:action"]
            if task['assignee']: cmd.extend(["--assignee", task['assignee']])
            subprocess.run(cmd, check=True, capture_output=True)
            log(f"成功创建任务: {task['title']}")
        except: log(f"创建失败", "WARNING")

def analyze_risk(tasks):
    risks = []
    today = datetime.date.today()
    grace_period = CONFIG['thresholds'].get('overdue_grace_period_days', 0)
    for t in tasks:
        if t['state'] == 'open' and t.get('due_date'):
            try:
                due_date = datetime.datetime.strptime(t['due_date'], "%Y-%m-%d").date()
                if due_date < today:
                    days_over = (today - due_date).days
                    risks.append(f"⚠️ 任务超时: {t['title']} (逾期 {days_over} 天) @{t['assignee']}")
                elif (due_date - today).days <= 2:
                    risks.append(f"⏰ 即将到期: {t['title']} (剩余 {(due_date - today).days} 天) @{t['assignee']}")
            except: pass
    
    # Check workload
    assignee_counts = {}
    for t in tasks:
        if t['state'] == 'open':
            assignee = t.get('assignee', 'Unassigned')
            assignee_counts[assignee] = assignee_counts.get(assignee, 0) + 1
            
    max_tasks = CONFIG['thresholds'].get('max_active_tasks_per_person', 3)
    for assignee, count in assignee_counts.items():
        if count > max_tasks and assignee != 'Unassigned':
            risks.append(f"🔥 资源过载: {assignee} 当前有 {count} 个活跃任务 (阈值: {max_tasks})")
    
    # Check for Unassigned tasks in active phases
    if assignee_counts.get('Unassigned', 0) > 0:
        risks.append(f"⚠️ 发现 {assignee_counts['Unassigned']} 个未分配任务 (Unassigned)，请尽快指派负责人。")
            
    return risks

def analyze_trends_chart(repo):
    if not os.path.exists(HISTORY_FILE):
        return ""
    try:
        with open(HISTORY_FILE, "r") as f:
            history = json.load(f)
        snapshots = history.get(repo, [])
        if len(snapshots) < 2:
            return ""
            
        # Mermaid XY Chart for Burndown (using closed count is not exactly burndown, but works for progress)
        # Better: Open tasks over time
        chart = "\n### 📉 燃尽图 (Burndown Chart)\n```mermaid\nxychart-beta\n    title \"待处理任务趋势 (Open Tasks)\"\n    x-axis [ "
        
        dates = []
        open_counts = []
        
        for snap in snapshots[-10:]: # Last 10 snapshots
            d = snap['date']
            total = snap['total']
            closed = snap['closed']
            open_task = total - closed
            dates.append(f"\"{d[5:]}\"") # MM-DD
            open_counts.append(str(open_task))
            
        chart += ", ".join(dates) + " ]\n"
        chart += "    y-axis \"Open Tasks\" 0 --> " + str(max([int(x) for x in open_counts]) + 2) + "\n"
        chart += "    line [" + ", ".join(open_counts) + "]\n```\n"
        
        return chart
    except Exception as e:
        return f"<!-- Chart gen failed: {e} -->"

def fetch_pull_requests(repo):
    try:
        cmd = ["gh", "pr", "list", "--repo", repo, "--json", "number,title,updatedAt,statusCheckRollup,author", "--limit", "20"]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        prs = json.loads(result.stdout)
        pr_data = []
        for pr in prs:
            try:
                updated = datetime.datetime.strptime(pr['updatedAt'], "%Y-%m-%dT%H:%M:%SZ").date()
            except ValueError:
                # Fallback for different timestamp formats if needed
                updated = datetime.date.today()
            
            days_inactive = (datetime.date.today() - updated).days
            is_stale = days_inactive > 3
            
            # Safely handle statusCheckRollup which can be None or missing keys
            ci_status = 'unknown'
            if pr.get('statusCheckRollup'):
                # statusCheckRollup can be a list or a dict depending on API version/state
                if isinstance(pr['statusCheckRollup'], list) and len(pr['statusCheckRollup']) > 0:
                     ci_status = pr['statusCheckRollup'][0].get('state', 'unknown') 
                elif isinstance(pr['statusCheckRollup'], dict):
                     ci_status = pr['statusCheckRollup'].get('state', 'unknown')

            pr_data.append({
                "number": pr['number'], 
                "title": pr['title'], 
                "author": pr['author']['login'] if pr.get('author') else "Ghost", 
                "days_inactive": days_inactive, 
                "is_stale": is_stale, 
                "ci_status": ci_status
            })
        return pr_data
    except Exception as e: 
        log(f"获取 PR 失败: {e}", "WARNING")
        return []

def analyze_pr_health(prs):
    if not prs: return ""
    report = "## 3. 代码质量与 PR 监控\n"
    stale_prs = [pr for pr in prs if pr['is_stale']]
    failed_prs = [pr for pr in prs if pr['ci_status'] == 'FAILURE']
    if stale_prs:
        report += f"- ⚠️ **僵尸 PR 预警:** 发现 {len(stale_prs)} 个 PR 超过 3 天未更新。\n"
        for pr in stale_prs: report += f"  - #{pr['number']} {pr['title']} (@{pr['author']}, {pr['days_inactive']}天无动静)\n"
    if failed_prs:
        report += f"- 🚨 **CI 构建失败:** 发现 {len(failed_prs)} 个 PR 构建未通过。\n"
        for pr in failed_prs: report += f"  - #{pr['number']} {pr['title']} (CI: FAILURE)\n"
    if not stale_prs and not failed_prs:
        report += f"- ✅ 所有 {len(prs)} 个活跃 PR 状态健康。\n"
    return report + "\n"

def generate_mermaid_gantt(tasks, blocked_tasks={}):
    mermaid_code = "gantt\n    title 项目进度计划\n    dateFormat YYYY-MM-DD\n    section 任务概览\n"
    today = datetime.date.today()
    grace_period = CONFIG['thresholds'].get('overdue_grace_period_days', 0)
    for task in tasks[:15]:
        status = "active"
        if task['status_detailed'] == 'done': status = "done"
        elif task['status_detailed'] == 'review': status = "crit"
        if task['state'] == 'open' and task.get('due_date'):
            try:
                due_date = datetime.datetime.strptime(task['due_date'], "%Y-%m-%d").date()
                if (due_date + datetime.timedelta(days=grace_period)) < today: status = "crit"
            except: pass
        start = (today - datetime.timedelta(days=2)).strftime("%Y-%m-%d")
        end = task.get('due_date') or (today + datetime.timedelta(days=5)).strftime("%Y-%m-%d")
        title = f"[BLOCKED] {task['title']}" if str(task['id']) in blocked_tasks else task['title']
        mermaid_code += f"    {title.replace(':','')} : {status}, {start}, {end}\n"
    return mermaid_code

def generate_phase_report(issues, blocked_tasks={}):
    report = "### 📑 阶段状态总览 (Phase Status)\n"
    phases = {}
    for i in issues:
        p = i.get('phase', 'general')
        if p not in phases: phases[p] = []
        phases[p].append(i)
    for phase_name, tasks in phases.items():
        done = len([t for t in tasks if t['state'] == 'closed'])
        pct = int((done / len(tasks)) * 100)
        report += f"- **{phase_name.capitalize()}:** {pct}% ({done}/{len(tasks)})\n"
        for t in tasks:
             icon = '✅' if t['status_detailed'] == 'done' else ('⛔' if str(t['id']) in blocked_tasks else '⏳')
             report += f"  - {icon} {t['title']}\n"
    return report + "\n"

def generate_markdown_table(issues, blocked_tasks={}):
    table = "| ID | 阶段 | 状态 | 标题 | 负责人 | 截止日期 |\n|---|---|---|---|---|---|\n"
    for t in issues:
        status = "✅ 已完成" if t['status_detailed'] == 'done' else ("⛔ 阻塞" if str(t['id']) in blocked_tasks else "⏳ 进行中")
        table += f"| {t['id']} | {t.get('phase','')} | {status} | {t['title']} | {t['assignee']} | {t.get('due_date','') or ''} |\n"
    return table

def export_report(repo, content):
    export_path = CONFIG['export'].get('path', 'reports')
    os.makedirs(export_path, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    safe_repo = repo.replace('/', '_')
    filename = f"{export_path}/Report_{safe_repo}_{timestamp}.md"
    zip_filename = f"{export_path}/Package_{safe_repo}_{timestamp}.zip"
    try:
        with open(filename, "w") as f: f.write(content)
        subprocess.run(["zip", "-j", zip_filename, filename, HISTORY_FILE], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        log(f"导出包已创建: {zip_filename}")
        print(f"\n📦 **导出就绪:** `{zip_filename}`")
    except: log("导出失败", "ERROR")

def ensure_github_cli():
    """Check if GitHub CLI is installed and authenticated. Guide user if not."""
    # 1. Check if gh is installed
    if not shutil.which("gh"):
        print(f"{YELLOW}⚠️  检测到未安装 GitHub CLI (gh)。{RESET}")
        print("为了使用此功能，请安装 gh CLI。")
        print("安装指南: https://cli.github.com/manual/installation")
        
        # Simple attempt to install if on a known environment (optional, risky to automate fully)
        if shutil.which("apt-get"):
             print(f"尝试自动安装 (需要 sudo 权限)...")
             try:
                 subprocess.run(["sudo", "apt-get", "update"], check=True)
                 subprocess.run(["sudo", "apt-get", "install", "-y", "gh"], check=True)
                 print(f"{GREEN}✅ GitHub CLI 安装成功！{RESET}")
             except Exception as e:
                 print(f"{RED}❌ 自动安装失败: {e}{RESET}")
                 print("请手动运行: sudo apt-get install gh")
                 return False
        elif shutil.which("brew"):
             print("请运行: brew install gh")
             return False
        else:
             return False

    # 2. Check auth status
    try:
        result = subprocess.run(["gh", "auth", "status"], capture_output=True, text=True)
        if result.returncode != 0:
            print(f"{YELLOW}⚠️  GitHub CLI 未登录。{RESET}")
            print(f"请运行以下命令进行授权:\n  {GREEN}gh auth login{RESET}")
            
            choice = input("是否立即运行登录向导? (y/n): ").strip().lower()
            if choice == 'y':
                try:
                    # Interactive login requires pty usually, but we try standard inherit
                    subprocess.run(["gh", "auth", "login"], check=False)
                except Exception:
                    pass
                # Check again
                if subprocess.run(["gh", "auth", "status"], capture_output=True).returncode == 0:
                    print(f"{GREEN}✅ 登录成功！{RESET}")
                    return True
                else:
                    print(f"{RED}❌ 登录未完成或失败。{RESET}")
                    return False
            return False
    except FileNotFoundError:
        return False
        
    return True

def save_config(config):
    os.makedirs(os.path.dirname(CONFIG_FILE), exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)

def configure_interactive():
    print(f"\n🔧 **项目管理助手配置向导**")
    config = load_config()
    
    # 1. 配置 SMTP (可选)
    print("\n--- 邮件通知设置 (SMTP) ---")
    current_smtp = config.get('smtp', {})
    if current_smtp.get('server'):
        print(f"当前 SMTP 服务器: {current_smtp.get('server')}")
    
    if input("是否配置 SMTP 邮件服务? (y/n): ").strip().lower() == 'y':
        smtp = {}
        smtp['server'] = input("SMTP 服务器 (例如 smtp.gmail.com): ").strip() or current_smtp.get('server', '')
        smtp['port'] = input("SMTP 端口 (默认 587): ").strip() or current_smtp.get('port', 587)
        smtp['user'] = input("SMTP 用户名: ").strip() or current_smtp.get('user', '')
        smtp['password'] = input("SMTP 密码 (留空则不修改): ").strip()
        if not smtp['password']:
             smtp['password'] = current_smtp.get('password', '')
        
        config['smtp'] = smtp
        save_config(config)
        print("✅ SMTP 配置已保存。")

    # 2. 配置阈值
    print("\n--- 风险阈值设置 ---")
    thresholds = config.get('thresholds', {})
    current_grace = thresholds.get('overdue_grace_period_days', 0)
    print(f"当前逾期宽限期: {current_grace} 天")
    
    new_grace = input(f"设置新的逾期宽限期 (默认 {current_grace}): ").strip()
    if new_grace:
        thresholds['overdue_grace_period_days'] = int(new_grace)
        config['thresholds'] = thresholds
        save_config(config)
        print("✅ 阈值配置已保存。")
        
    print("\n🎉 配置完成！")

def scaffold_requirements(output_path, raw_requirement):
    """
    基于原始需求生成结构化 Markdown 清单 (Scaffold).
    支持交互式增删改，并保存到本地文件.
    """
    print(f"\n🧠 **正在基于原始需求生成需求清单 (AI Scaffold)...**")
    print(f"原始需求: {raw_requirement}")
    
    # 模拟 LLM 生成的初步清单 (实际场景应调用 LLM API)
    print(f"\n[系统] 正在分析需求并拆解功能点...")
    
    tasks = [
        {"title": "用户注册与登录 (手机号/微信)", "assignee": ""},
        {"title": "首页 Dashboard 展示关键数据", "assignee": ""},
        {"title": "核心业务流程: 订单创建与管理", "assignee": "@pm-lead"},
        {"title": "支付接口对接 (支付宝/微信)", "assignee": ""},
        {"title": "后台管理系统: 用户权限配置", "assignee": "@admin"},
        {"title": "系统日志与监控告警", "assignee": "@ops"}
    ]
    
    if "商城" in raw_requirement or "shop" in raw_requirement.lower():
        tasks.insert(2, {"title": "商品列表与详情页展示", "assignee": ""})
        tasks.insert(3, {"title": "购物车与结算流程", "assignee": ""})

    while True:
        print(f"\n📋 **当前生成的需求清单:**")
        for idx, task in enumerate(tasks):
            assignee_str = f" {task['assignee']}" if task['assignee'] else " [未指派]"
            print(f"{idx + 1}. {task['title']}{assignee_str}")

        print(f"\n------------------------------------------------")
        print(f"交互选项: ")
        print(f"  [a] 添加需求  [d] 删除需求  [m] 修改标题")
        print(f"  [s] 设置负责人 (@user)")
        print(f"  [y] 确认并保存到文件")
        print(f"  [q] 取消")
        
        choice = input("\n请输入指令: ").strip().lower()
        
        if choice == 'y':
            break
        elif choice == 'q':
            print("已取消操作。")
            return
        elif choice == 'a':
            title = input("请输入新需求标题: ")
            assignee = input("请输入负责人 (可选, @user): ").strip()
            tasks.append({"title": title, "assignee": assignee})
        elif choice == 'd':
            try:
                idx = int(input("请输入要删除的序号: ")) - 1
                if 0 <= idx < len(tasks):
                    removed = tasks.pop(idx)
                    print(f"已删除: {removed['title']}")
                else:
                    print("无效序号。")
            except ValueError:
                print("输入无效。")
        elif choice == 'm':
            try:
                idx = int(input("请输入序号: ")) - 1
                if 0 <= idx < len(tasks):
                    new_title = input(f"原标题: {tasks[idx]['title']}\n新标题: ")
                    if new_title: tasks[idx]['title'] = new_title
                else:
                    print("无效序号。")
            except ValueError:
                print("输入无效。")
        elif choice == 's':
            try:
                idx = int(input("请输入序号: ")) - 1
                if 0 <= idx < len(tasks):
                    new_assignee = input(f"为 '{tasks[idx]['title']}' 设置负责人 (例如 @dev01): ")
                    tasks[idx]['assignee'] = new_assignee
                else:
                    print("无效序号。")
            except ValueError:
                print("输入无效。")
        else:
            print("未知指令。")

    # 保存文件
    try:
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        with open(output_path, "w") as f:
            f.write(f"# 项目需求清单\n\n> 生成时间: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n> 原始需求: {raw_requirement}\n\n## 功能列表\n\n")
            for task in tasks:
                assignee_part = f" {task['assignee']}" if task['assignee'] else ""
                f.write(f"- [ ] {task['title']}{assignee_part}\n")
        print(f"\n✅ 需求清单已保存至: {output_path}")
        print(f"下一步建议: 运行 `python3 project_control.py import --file {output_path} --repo <your/repo>` 将需求导入 GitHub。")
    except Exception as e:
        log(f"保存文件失败: {e}", "ERROR")

def import_requirements(file_path, repo):
    """
    从本地 Markdown 清单导入需求到 GitHub Issues.
    1. 解析 MD 文件
    2. 交互式补充未指派的责任人
    3. 批量创建 Issue
    4. 回写 Issue ID 到 MD 文件
    """
    if not os.path.exists(file_path):
        log(f"文件不存在: {file_path}", "ERROR")
        return

    print(f"\n📥 **开始导入需求清单: {file_path}**")
    
    with open(file_path, "r") as f:
        lines = f.readlines()
    
    tasks = []
    task_indices = []
    
    # 解析 Markdown
    # 匹配: - [ ] 需求标题 @assignee (可选) #IssueID (可选)
    # Group 1: [x] or [ ]
    # Group 2: Title
    # Group 3: @Assignee (Optional)
    # Group 4: #IssueID (Optional - ignore for creation)
    pattern = re.compile(r'- \[([ x])\] (.*?)(?: (@[\w-]+))?(?: #(\d+))?$')
    
    for idx, line in enumerate(lines):
        match = pattern.search(line.strip())
        if match:
            is_checked = match.group(1) == 'x'
            title = match.group(2).strip()
            assignee = match.group(3).strip() if match.group(3) else None
            issue_id = match.group(4)
            
            # 如果已有 Issue ID，跳过创建（但记录索引以便后续可能的更新，这里暂略）
            if issue_id:
                print(f"  [跳过] 已关联 Issue #{issue_id}: {title}")
                continue
                
            tasks.append({
                "line_idx": idx,
                "title": title,
                "assignee": assignee,
                "is_checked": is_checked
            })
            task_indices.append(idx)

    if not tasks:
        print("未发现新的待导入需求。")
        return

    print(f"\n发现 {len(tasks)} 个新需求待导入。")
    
    # 交互式指派责任人
    print("\n--- 🕵️ 责任人指派检查 ---")
    default_assignee = None
    
    for task in tasks:
        if not task['assignee']:
            print(f"\n需求: \"{task['title']}\" 未指派责任人。")
            choice = input(f"请输入 GitHub ID (直接回车跳过, 输入 'me' 指派给自己): ").strip()
            
            if choice == 'me':
                # 尝试获取当前用户 (需要 gh auth status 解析，这里简化)
                # 实际: subprocess.run(["gh", "api", "user", "--jq", ".login"], ...)
                # 这里暂且假设用户知道自己的 ID，或者直接用 @me (gh cli 支持 --assignee @me)
                task['assignee'] = "@me"
            elif choice:
                task['assignee'] = f"@{choice}" if not choice.startswith('@') else choice
            else:
                task['assignee'] = None # 保持未指派

    # 确认创建
    print(f"\n准备在 {repo} 创建 {len(tasks)} 个 Issue...")
    if input("确认执行? (y/n): ").lower() != 'y':
        print("已取消。")
        return

    # 批量创建并回写
    new_lines = lines.copy()
    created_count = 0
    
    for task in tasks:
        try:
            # 构造 gh 命令
            cmd = ["gh", "issue", "create", "--repo", repo, "--title", task['title'], 
                   "--body", f"Imported from {os.path.basename(file_path)}", 
                   "--label", "type:requirement"]
            
            if task['assignee']:
                assignee_val = task['assignee'].replace('@', '')
                cmd.extend(["--assignee", assignee_val])
            
            # 执行创建
            print(f"正在创建: {task['title']}...", end="", flush=True)
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            
            # 提取 Issue URL/ID
            # gh 输出通常是 URL: https://github.com/user/repo/issues/123
            issue_url = result.stdout.strip()
            issue_number = issue_url.split('/')[-1]
            
            print(f" ✅ #{issue_number}")
            
            # 回写 Markdown: 在行尾追加 #ID
            original_line = new_lines[task['line_idx']].rstrip()
            # 如果之前没有责任人但现在指派了，也补上
            if task['assignee'] and task['assignee'] not in original_line:
                original_line += f" {task['assignee']}"
            
            new_lines[task['line_idx']] = f"{original_line} #{issue_number}\n"
            created_count += 1
            
        except subprocess.CalledProcessError as e:
            print(f" ❌ 失败: {e.stderr.strip()}")
        except Exception as e:
            print(f" ❌ 错误: {e}")

    # 保存回写后的 Markdown
    if created_count > 0:
        with open(file_path, "w") as f:
            f.writelines(new_lines)
        print(f"\n✅ 已成功导入 {created_count} 个需求，并回写至 {file_path}")
    else:
        print("\n⚠️ 未能导入任何需求。")

def launch_phase(repo, from_phase, to_phase):
    """
    项目阶段流转控制 (Phase Launch).
    检查上一阶段任务是否全部完成，若通过门禁，则批量创建下一阶段任务.
    """
    print(f"\n🚀 **正在启动阶段流转: {from_phase} -> {to_phase}**")
    
    # 1. 检查上一阶段状态
    print(f"[系统] 正在检查 '{from_phase}' 阶段任务状态...")
    # 注意：fetch_github_tasks 默认逻辑是 labels 匹配，这里需要确保 fetch_github_tasks 函数支持 label 过滤
    # 之前实现中 fetch_github_tasks 接受 labels 参数
    
    # 修正 labels 参数传递，config 中定义的是 requirements 对应 labels=["type:requirement"]
    label_map = {
        'requirement': ['type:requirement'],
        'design': ['type:design'],
        'dev': ['type:dev']
    }
    
    target_labels = label_map.get(from_phase, [f"type:{from_phase}"])
    tasks = fetch_github_tasks(repo, labels=target_labels)
    
    if not tasks:
        print(f"{YELLOW}⚠️  未找到 '{from_phase}' 阶段的任何任务。无法流转。{RESET}")
        return

    open_tasks = [t for t in tasks if t['state'] == 'open']
    total = len(tasks)
    done = total - len(open_tasks)
    
    print(f"进度: {done}/{total} ({(done/total)*100:.0f}%)")
    
    if open_tasks:
        print(f"{RED}❌ 阶段门禁未通过！以下任务尚未完成:{RESET}")
        for t in open_tasks:
            assignee = t.get('assignee', 'Unassigned')
            print(f"  - #{t['id']} {t['title']} (@{assignee})")
        
        choice = input("\n是否强制流转 (不推荐)? (yes/no): ").lower()
        if choice != 'yes':
            print("已取消流转。请先完成上述任务。")
            return
    else:
        # P1: 增加质量门禁 (CI Status Check)
        # 仅当上一阶段是 dev 时检查 (即 dev -> test)
        if from_phase == 'dev':
            print(f"[系统] 正在检查代码构建状态 (CI Gate)...")
            ci = fetch_ci_status(repo)
            if ci and ci['conclusion'] != 'success':
                print(f"{RED}❌ 质量门禁未通过！主线构建状态为: {ci['icon']} {ci['conclusion']}{RESET}")
                print(f"Workflow: {ci['name']} ({ci['url']})")
                
                choice = input("\n是否强制流转 (极不推荐)? (yes/no): ").lower()
                if choice != 'yes':
                    print("已取消流转。请先修复构建错误。")
                    return
                print(f"{YELLOW}⚠️  警告: 已强制跳过质量门禁！{RESET}")
            elif ci:
                print(f"{GREEN}✅ 质量门禁通过！主线构建成功。{RESET}")
            else:
                print(f"{YELLOW}⚠️  未检测到 CI 状态，跳过质量检查。{RESET}")

        print(f"{GREEN}✅ 阶段门禁通过！所有前置任务已完成。{RESET}")

    # 2. 生成下一阶段任务
    print(f"\n[系统] 准备生成 '{to_phase}' 阶段任务...")
    new_tasks = []
    
    for origin_task in tasks:
        # 这里仅根据上一阶段任务生成下一阶段任务
        # 实际场景可能是一对多，这里作为演示使用一对一映射，并引用原 Issue
        
        # 更加智能的生成逻辑
        if to_phase == 'design':
            new_tasks.append({
                "title": f"设计方案: {origin_task['title']}",
                "body": f"针对需求 #{origin_task['id']} 进行技术方案设计。\n输出物: 架构图、接口文档。\nRef: #{origin_task['id']}",
                "label": "type:design"
            })
        elif to_phase == 'dev':
            new_tasks.append({
                "title": f"开发实现: {origin_task['title']}",
                "body": f"依据设计文档实现功能。\n关联上游任务: #{origin_task['id']}",
                "label": "type:dev"
            })
        elif to_phase == 'test':
            new_tasks.append({
                "title": f"测试用例: {origin_task['title']}",
                "body": f"编写并执行测试用例。\n关联功能: #{origin_task['id']}",
                "label": "type:test"
            })

    print(f"即将创建 {len(new_tasks)} 个 '{to_phase}' 任务:")
    for t in new_tasks[:5]:
        print(f"  - {t['title']}")
    if len(new_tasks) > 5:
        print(f"  ... 以及其他 {len(new_tasks)-5} 个")
        
    if input("\n确认执行批量创建? (y/n): ").lower() != 'y':
        print("已取消。")
        return

    # 3. 执行创建
    success_count = 0
    for t in new_tasks:
        try:
            cmd = ["gh", "issue", "create", "--repo", repo, "--title", t['title'], 
                   "--body", t['body'], "--label", t['label']]
            # 自动指派给原任务负责人 (可选策略，这里暂不指派，留给 daily standup 指派)
            # cmd.extend(["--assignee", origin_task['assignee']])
            
            subprocess.run(cmd, check=True, capture_output=True)
            print(f"✅ Created: {t['title']}")
            success_count += 1
        except Exception as e:
            print(f"❌ Failed: {t['title']}")

    print(f"\n🎉 阶段流转完成！共创建 {success_count} 个任务。")

def fetch_ci_status(repo):
    """
    获取最近的 CI 构建状态 (P1: 质量集成).
    """
    try:
        cmd = ["gh", "run", "list", "--repo", repo, "--limit", "1", "--json", "status,conclusion,headBranch,name,url"]
        result = subprocess.run(cmd, capture_output=True, text=True)
        runs = json.loads(result.stdout)
        if not runs: return None
        run = runs[0]
        icon = "✅" if run['conclusion'] == 'success' else "❌" if run['conclusion'] == 'failure' else "⏳"
        return {"name": run['name'], "branch": run['headBranch'], "status": run['status'], "conclusion": run['conclusion'], "url": run['url'], "icon": icon}
    except: return None

def generate_retrospective(repo, output_file="RETROSPECTIVE.md"):
    """
    生成项目总结报告 (P2: 知识沉淀).
    统计 Issue 完成情况、耗时分布、活跃贡献者，并生成 Markdown 报告.
    """
    print(f"\\n📚 **正在生成项目总结报告: {repo}**")
    
    tasks = fetch_github_tasks(repo) # 获取所有 Issue，包括 closed
    if not tasks:
        print("未找到任务数据。")
        return

    # 1. 基础统计
    total = len(tasks)
    closed = len([t for t in tasks if t['state'] == 'closed'])
    open_count = total - closed
    
    # 2. 贡献者统计
    contributors = {}
    for t in tasks:
        assignee = t.get('assignee', 'Unassigned')
        contributors[assignee] = contributors.get(assignee, 0) + 1
    
    # 生成 Markdown 内容
    content = []
    content.append(f"# 📝 项目复盘报告: {repo}")
    content.append(f"> 生成日期: {datetime.date.today()}\\n")
    
    content.append("## 1. 核心概览")
    content.append(f"- **总任务数**: {total}")
    content.append(f"- **已完成**: {closed} ({(closed/total)*100:.1f}%)")
    content.append(f"- **遗留任务**: {open_count}")
    
    content.append("\\n## 2. 贡献光荣榜")
    content.append("| 贡献者 | 任务数 | 占比 |")
    content.append("|---|---|---|")
    sorted_contributors = sorted(contributors.items(), key=lambda x: x[1], reverse=True)
    for user, count in sorted_contributors:
        pct = (count / total) * 100
        bar = "█" * int(pct / 10)
        content.append(f"| {user} | {count} | {pct:.1f}% {bar} |")
        
    content.append("\\n## 3. 任务分布 (Mermaid)")
    content.append("```mermaid")
    content.append("pie title 任务状态分布")
    content.append(f'    "已完成" : {closed}')
    content.append(f'    "待处理" : {open_count}')
    content.append("```")
    
    content.append("\\n## 4. 遗留风险项")
    risks = analyze_risk(tasks)
    if risks:
        for r in risks:
            content.append(f"- {r}")
    else:
        content.append("🎉 无明显风险项。")
    
    # P1: Integration - CI Status
    ci = fetch_ci_status(repo)
    if ci:
         content.insert(6, f"- **最近构建状态**: {ci['icon']} {ci['conclusion']} ({ci['name']})")

    # 写入文件
    try:
        with open(output_file, "w") as f:
            f.write("\\n".join(content))
        print(f"✅ 报告已保存至: {output_file}")
    except Exception as e:
        print(f"❌ 保存失败: {e}")

def init_repo(name, description, is_private=True, org=None):
    """
    初始化 GitHub 仓库.
    调用 gh repo create 创建远程仓库，并输出 clone 地址.
    """
    print(f"\n🌱 **正在初始化项目仓库: {name}**")
    
    # 构造 gh 命令
    # gh repo create <name> --description "<desc>" --<public/private> --add-readme
    
    full_name = f"{org}/{name}" if org else name
    visibility = "--private" if is_private else "--public"
    
    cmd = ["gh", "repo", "create", full_name, 
           "--description", description,
           visibility,
           "--add-readme"] # 默认添加 README 以初始化 main 分支
    
    print(f"执行命令: {' '.join(cmd)}")
    
    try:
        # 交互式确认
        if input(f"确认创建仓库 '{full_name}' ({'Private' if is_private else 'Public'})? (y/n): ").lower() != 'y':
            print("已取消。")
            return

        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        
        # 解析输出 (gh 通常输出仓库 URL)
        repo_url = result.stdout.strip()
        # 如果 output 为空或不是 url，尝试构造
        if "github.com" not in repo_url:
             # 有时 gh create 输出不仅仅是 URL，或者在 stderr 中
             # 尝试获取当前用户
             user_res = subprocess.run(["gh", "api", "user", "--jq", ".login"], capture_output=True, text=True)
             user = user_res.stdout.strip()
             repo_url = f"https://github.com/{org or user}/{name}"

        print(f"\n✅ 仓库创建成功!")
        print(f"🔗 URL: {repo_url}")
        print(f"💻 Clone: git clone {repo_url}.git")
        
        # 引导下一步
        print(f"\n下一步建议:")
        print(f"1. 生成需求: python3 project_control.py scaffold --out requirements.md --req '...description...'")
        print(f"2. 导入需求: python3 project_control.py import --file requirements.md --repo {org or '<user>'}/{name}")
        
    except subprocess.CalledProcessError as e:
        print(f"{RED}❌ 创建失败: {e.stderr.strip()}{RESET}")
    except Exception as e:
        print(f"{RED}❌ 系统错误: {e}{RESET}")

def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")
    
    # Existing commands
    sp = subparsers.add_parser("status")
    sp.add_argument("--repo", required=True)
    sp.add_argument("--export", action='store_true')
    
    rp = subparsers.add_parser("risk")
    rp.add_argument("--repo", required=True)
    
    rmp = subparsers.add_parser("remind")
    rmp.add_argument("--repo", required=True)
    rmp.add_argument("--id", required=True, type=int)
    rmp.add_argument("--msg", required=True)
    
    pp = subparsers.add_parser("plan")
    pp.add_argument("--repo", required=True)
    pp.add_argument("--req", required=True)
    
    cp = subparsers.add_parser("config", help="Run interactive configuration wizard")
    
    # New commands
    scp = subparsers.add_parser("scaffold", help="Generate requirements list from raw input")
    scp.add_argument("--out", required=True, help="Output markdown file path")
    scp.add_argument("--req", required=True, help="Raw requirement text")

    imp = subparsers.add_parser("import", help="Import requirements from markdown to GitHub")
    imp.add_argument("--file", required=True, help="Input markdown file path")
    imp.add_argument("--repo", required=True, help="Target GitHub repository")
    
    lp = subparsers.add_parser("launch", help="Launch next phase tasks")
    lp.add_argument("--repo", required=True, help="Target GitHub repository")
    lp.add_argument("--from-phase", required=True, choices=['requirement', 'design', 'dev'], help="Source phase")
    lp.add_argument("--to-phase", required=True, choices=['design', 'dev', 'test'], help="Target phase")
    
    # Meeting command
    mp = subparsers.add_parser("meeting", help="Process meeting notes into Action Items")
    mp.add_argument("--repo", required=True, help="Target GitHub repository")
    mp.add_argument("--file", required=True, help="Meeting notes file path")

    # Init command
    ip = subparsers.add_parser("init", help="Initialize a new GitHub repository")
    ip.add_argument("--name", required=True, help="Repository name")
    ip.add_argument("--desc", required=True, help="Repository description")
    ip.add_argument("--org", help="Organization name (optional)")
    ip.add_argument("--public", action='store_true', help="Make repository public (default: private)")

    # Archive command (P2)
    arc = subparsers.add_parser("archive", help="Generate project retrospective report")
    arc.add_argument("--repo", required=True, help="Target GitHub repository")
    arc.add_argument("--out", default="RETROSPECTIVE.md", help="Output filename")

    args = parser.parse_args()
    
    if not args.command: parser.print_help(); sys.exit(1)

    if args.command == "config":
        configure_interactive()
        sys.exit(0)
        
    if args.command == "scaffold":
        scaffold_requirements(args.out, args.req)
        sys.exit(0)

    # Pre-flight check for GitHub dependency
    if not ensure_github_cli():
        sys.exit(1)

    if args.command == "launch":
        launch_phase(args.repo, args.from_phase, args.to_phase)
    elif args.command == "import":
        import_requirements(args.file, args.repo)
    elif args.command == "init":
        init_repo(args.name, args.desc, not args.public, args.org)
    elif args.command == "meeting":
        if not os.path.exists(args.file):
            print(f"{RED}错误: 文件不存在 {args.file}{RESET}")
            sys.exit(1)
        with open(args.file, 'r') as f:
            content = f.read()
        process_meeting_notes(args.repo, content)
    elif args.command == "archive":
        generate_retrospective(args.repo, args.out)
    elif args.command == "status":
        tasks = get_all_tasks(args.repo)
        save_history(args.repo, tasks)
        prs = fetch_pull_requests(args.repo)
        ci_status = fetch_ci_status(args.repo) # P1 Integration
        blocked_tasks = check_dependencies(tasks)
        buffer = []
        def p(x): print(x); buffer.append(str(x))
        p(f"\n# 📊 项目跟踪表: {args.repo}\n日期: {datetime.date.today()}\n")
        
        # P1: CI Status Display
        if ci_status:
            p(f"### 🚦 构建状态: {ci_status['icon']} {ci_status['conclusion'].upper()} ({ci_status['branch']})")
        
        p(f"## 1. 核心指标\n- **进度:** {int((len([t for t in tasks if t['state']=='closed'])/len(tasks))*100) if tasks else 0}%\n- **任务:** {len(tasks)}\n- **PR:** {len(prs)}\n")
        
        # Burndown Chart
        burndown = analyze_trends_chart(args.repo)
        if burndown: p(burndown)

        risks = analyze_risk(tasks)
        p(f"## 2. 风险预警\n")
        if blocked_tasks: p(f"- ⛔ 流程阻塞: {len(blocked_tasks)} 个任务被拦截。")
        for r in risks: p(f"- {r}")
        pr_report = analyze_pr_health(prs)
        if pr_report: p(pr_report)
        p(generate_phase_report(tasks, blocked_tasks))
        p("### 📋 任务明细表\n" + generate_markdown_table(tasks, blocked_tasks))
        p("\n### 📅 进度时间线\n```mermaid\n" + generate_mermaid_gantt(tasks, blocked_tasks) + "```\n")
        if args.export: export_report(args.repo, "\n".join(buffer))
    elif args.command == "plan": plan_project(args.repo, args.req)
    elif args.command == "remind": remind_issue(args.repo, args.id, args.msg)
    elif args.command == "risk":
        tasks = get_all_tasks(args.repo)
        for r in analyze_risk(tasks): print(r)

if __name__ == "__main__":
    main()
