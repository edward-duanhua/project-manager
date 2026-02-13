#!/usr/bin/env python3
import json
import logging
import os
import argparse
import sys
import os
import subprocess

# Add the parent directory of 'src' to sys.path so that 'src' can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import custom modules
from src.connectors.github import GitHubConnector
from src.core.resource import ResourceManager
from src.core.phase import PhaseManager
from src.core.sync import SyncManager
from src.reports.report import ReportGenerator
from src.core.intelligence import IntelligenceEngine

# Setup Logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Project Control Center 2.0")
    subparsers = parser.add_subparsers(dest="command")

    # Command: Init (Create Repo + Config)
    init_parser = subparsers.add_parser("init", help="Initialize a new project")
    init_parser.add_argument("--repo", required=True, help="GitHub repository name (owner/repo)")
    init_parser.add_argument("--desc", required=False, help="Project description")

    # Command: Scaffold (Generate Requirements)
    scaffold_parser = subparsers.add_parser("scaffold", help="Generate requirements using AI/Template")
    scaffold_parser.add_argument("--req", required=True, help="Raw requirement description")
    scaffold_parser.add_argument("--out", required=True, help="Output markdown file path")

    # Command: Import (Markdown -> GitHub Issues)
    import_parser = subparsers.add_parser("import", help="Import tasks from local file to GitHub")
    import_parser.add_argument("--file", required=True, help="Local markdown file")
    import_parser.add_argument("--repo", required=True, help="Target repository")

    # Command: Launch Phase (Transition Gate)
    launch_parser = subparsers.add_parser("launch", help="Transition to next phase")
    launch_parser.add_argument("--repo", required=True, help="Repository name")
    launch_parser.add_argument("--from", dest="from_phase", required=True, choices=["requirement", "design", "dev"])
    launch_parser.add_argument("--to", dest="to_phase", required=True, choices=["design", "dev", "test"])

    # Command: Sync (Bi-directional)
    sync_parser = subparsers.add_parser("sync", help="Sync local file status with GitHub")
    sync_parser.add_argument("--repo", required=True, help="Repository name")
    sync_parser.add_argument("--file", required=True, help="Local markdown file")

    # Command: Status (Generate Report)
    status_parser = subparsers.add_parser("status", help="Generate project status report")
    status_parser.add_argument("--repo", required=True, help="Repository name")
    status_parser.add_argument("--out", required=False, default="REPORT.md", help="Output report file")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # Initialize Components
    connector = GitHubConnector(logger=logger)
    resource_mgr = ResourceManager(logger=logger)
    intelligence = IntelligenceEngine(logger=logger)

    # Dispatch Commands
    if args.command == "init":
        # Init Logic
        logger.info(f"Initializing project: {args.repo}...")
        try:
            # 1. Create Repo (if not exists)
            # Check if repo exists first? Or just try create.
            cmd = ["gh", "repo", "create", args.repo, "--private", "--add-readme"]
            if args.desc:
                cmd.extend(["--description", args.desc])
            
            subprocess.run(cmd, check=False) # Don't fail if exists
            
            # 2. Create Labels
            labels = [
                {"name": "type:requirement", "color": "0E8A16", "desc": "Project Requirement"},
                {"name": "type:design", "color": "1D76DB", "desc": "Technical Design"},
                {"name": "type:dev", "color": "F9D0C4", "desc": "Development Task"},
                {"name": "type:test", "color": "C2E0C6", "desc": "Testing Task"}
            ]
            for label in labels:
                subprocess.run(["gh", "label", "create", label["name"], "--repo", args.repo, "--color", label["color"], "--description", label["desc"]], check=False)
                
            logger.info(f"Project initialized: https://github.com/{args.repo}")
        except Exception as e:
            logger.error(f"Init failed: {e}")

    elif args.command == "scaffold":
        # AI-powered Scaffold
        logger.info(f"Generating intelligent scaffold for: {args.req}")
        
        # Call Intelligence Engine
        suggestions = intelligence.analyze_requirement(args.req)
        
        content = f"# Requirements for: {args.req}\n\n"
        if not suggestions:
            content += "- [ ] Define Core Requirement (AI could not infer details)\n"
        else:
            for task in suggestions:
                # Basic context mapping
                task_title = task['title']
                labels = ",".join(task['labels'])
                
                # Assignee prediction
                assignees = resource_mgr.find_best_assignee(task['labels'])
                assignee_str = f" @{assignees[0]}" if assignees else ""
                
                content += f"- [ ] {task_title} ({labels}){assignee_str}\n"
                
        # Add manual override section
        content += "\n## Manual Additions\n- [ ] \n"
        
        with open(args.out, "w") as f:
            f.write(content)
        logger.info(f"Scaffold saved to {args.out} with {len(suggestions)} AI-generated tasks.")

    elif args.command == "import":
        # Import Logic
        logger.info(f"Importing from {args.file} to {args.repo}...")
        
        with open(args.file, "r") as f:
            lines = f.readlines()
        
        import re
        # Pattern: - [ ] Title (tags) @assignee #issue_id
        # Group 1: [ x]
        # Group 2: Title (including possible (tags))
        # Group 3: @assignee (optional)
        # Group 4: #issue_id (optional, ignore for import creation)
        pattern = re.compile(r'- \[([ x])\] (.*?)(?: @([\w-]+))?(?: #(\d+))?$')

        for line in lines:
            line_stripped = line.strip()
            if not line_stripped.startswith("- ["): continue
            
            match = pattern.search(line_stripped)
            if match:
                is_checked = match.group(1).strip() == 'x'
                title_raw = match.group(2).strip()
                manual_assignee = match.group(3)
                existing_id = match.group(4)
                
                if existing_id:
                    logger.info(f"Skipping existing issue #{existing_id}: {title_raw}")
                    continue
                
                # Assignee Logic: Manual Override > Auto Skill Match
                assignees = []
                if manual_assignee:
                    assignees = [manual_assignee]
                else:
                    # Improved tag parsing from parens
                    # Handle multiple groups: "Design UI (Mobile) (type:design)"
                    import re
                    tags = [title_raw] # Default fallback if no parens
                    
                    # Extract all (...) content
                    matches = re.findall(r'\(([^)]+)\)', title_raw)
                    if matches:
                        tags = []
                        for match in matches:
                            # Split by comma for multiple tags in one paren: (type:dev, domain:api)
                            parts = [t.strip() for t in match.split(',')]
                            tags.extend(parts)
                    
                    assignees = resource_mgr.find_best_assignee(tags)
                
                # Create Issue
                logger.info(f"Creating: {title_raw}")
                # Clean labels: if tags found, use them as GitHub labels too? Yes ideally.
                # For now, stick to type:requirement as base
                final_labels = ["type:requirement"]
                
                connector.create_issue(args.repo, title_raw, "Imported Task", labels=final_labels, assignees=assignees)
                logger.info(f"Imported: {title_raw} -> Assigned to {assignees}")

    elif args.command == "launch":
        phase_mgr = PhaseManager(connector, resource_mgr, args.repo)
        
        # 1. Check Gate: Returns list of CLOSED tasks from previous phase
        closed_parent_tasks = phase_mgr.check_gate(args.from_phase, args.to_phase)
        
        if not closed_parent_tasks:
            logger.error(f"Gate failed or no tasks found in phase '{args.from_phase}'. Cannot transition.")
            return

        logger.info(f"Gate Passed. Found {len(closed_parent_tasks)} parent tasks.")
        
        # 2. Generate Next Phase Tasks (Linked)
        next_tasks = []
        for parent in closed_parent_tasks:
            new_title = f"{args.to_phase.title()} for #{parent['number']}: {parent['title']}"
            new_task = {
                "title": new_title,
                "body": f"Transitioned from Phase: {args.from_phase}",
                "labels": [f"type:{args.to_phase}"],
                "parent_id": parent['number']
            }
            next_tasks.append(new_task)
            
        # 3. Execute Creation
        logger.info(f"Creating {len(next_tasks)} linked tasks for phase '{args.to_phase}'...")
        count = phase_mgr.execute_transition(next_tasks)
        logger.info(f"Transition Complete. {count} tasks created.")

    elif args.command == "sync":
        sync_mgr = SyncManager(connector, resource_mgr, args.repo)
        sync_mgr.sync(args.file)

    elif args.command == "status":
        report_gen = ReportGenerator(connector, resource_mgr, args.repo)
        report_gen.generate(args.out)

if __name__ == "__main__":
    main()
