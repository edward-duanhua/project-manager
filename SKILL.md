---
name: project-manager
description: Intelligent Project Management Expert v2.0. Features modular architecture, resource calendar (skill-based assignment), bi-directional sync, and automated phase gating.
---

# Project Manager Skill (v2.0)

Professional R&D Project Management Suite.

## Core Features

1.  **Smart Init**: One-command project setup (Repo + Labels).
2.  **Resource Calendar**: Auto-assigns tasks based on member skills (`data/team.json`).
3.  **Phase Control**: Strict gating for `Requirement -> Design -> Dev -> Test`.
4.  **Deep Sync**: Bi-directional synchronization between local Markdown and GitHub Issues.
5.  **Risk Radar**: Automated detection of overdue, overloaded, and unassigned tasks.

## Commands

### 1. Initialize Project
```bash
python3 skills/project-manager/scripts/project_control.py init --repo owner/repo --desc "My Project"
```

### 2. Scaffold Requirements
Generate a requirement list from a natural language description.
```bash
python3 skills/project-manager/scripts/project_control.py scaffold --req "Build a CRM system with Python API" --out requirements.md
```

### 3. Import & Assign
Import requirements to GitHub. **Auto-assigns** based on skills (e.g., "API" -> Backend Dev).
```bash
python3 skills/project-manager/scripts/project_control.py import --file requirements.md --repo owner/repo
```

### 4. Status Report
Generate a comprehensive status report (Progress, Risks, Gantt).
```bash
python3 skills/project-manager/scripts/project_control.py status --repo owner/repo --out REPORT.md
```

### 5. Sync Status
Sync local file checkmarks `[x]` with GitHub Issue status.
```bash
python3 skills/project-manager/scripts/project_control.py sync --repo owner/repo --file requirements.md
```

### 6. Phase Transition
Move project to the next phase (e.g., Requirement -> Design).
```bash
python3 skills/project-manager/scripts/project_control.py launch --repo owner/repo --from requirement --to design
```

## Configuration

- **Team Config**: `skills/project-manager/data/team.json`
    - Define members, roles, and skills here.
- **Architecture**:
    - `src/core/`: Business logic (Phase, Resource, Sync).
    - `src/connectors/`: External APIs (GitHub).
    - `src/reports/`: Visualization.
