#!/usr/bin/env python3
import json
import logging
import os
import argparse
import sys
import os
import subprocess
import dotenv

# Load env
dotenv.load_dotenv()

# Add the parent directory of 'src' to sys.path so that 'src' can be imported
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.dirname(current_dir)
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

# Import custom modules
from src.connectors.github import GitHubConnector
from src.connectors.gitcode import GitCodeConnector
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

def load_config(path):
    if os.path.exists(path):
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Failed to load config: {e}")
            return {}
    return {}

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
    config_path = os.path.join(parent_dir, "data", "config.json")
    config = load_config(config_path)

    provider = config.get("source_control", {}).get("provider", "github")
    
    if provider == "gitcode":
        connector = GitCodeConnector(logger=logger)
        logger.info("Using GitCode Connector")
    else:
        # Optimized: Read token env name from config
        token_env = config.get("source_control", {}).get("github_token_env", "GITHUB_TOKEN")
        connector = GitHubConnector(logger=logger, token_env=token_env)

    # Use team_config from config
    team_config_raw = config.get("team_config", "data/team.json")
    
    if team_config_raw.startswith("/"):
        team_config_path = team_config_raw
    else:
        # If config is "skills/project-manager/data/team.json", we need to be careful
        # parent_dir is /home/rancle/.openclaw/workspace/skills/project-manager
        
        # Check if it starts with the skill prefix
        prefix = "skills/project-manager/"
        if team_config_raw.startswith(prefix):
             # Strip prefix to get relative path from skill root
             clean_rel = team_config_raw[len(prefix):]
             team_config_path = os.path.join(parent_dir, clean_rel)
        else:
             team_config_path = os.path.join(parent_dir, team_config_raw)

    resource_mgr = ResourceManager(config_path=team_config_path, logger=logger)
    intelligence = IntelligenceEngine(logger=logger)

    # Helper to get configured labels
    def get_phase_labels(phase_name):
        # Map phase name to config key
        key_map = {'requirement': 'requirements', 'design': 'design', 'dev': 'development', 'test': 'test'}
        key = key_map.get(phase_name, phase_name)
        return config.get("sources", {}).get(key, {}).get("labels", [])

    # Dispatch Commands
    if args.command == "init":
        # Init Logic
        logger.info(f"Initializing project: {args.repo}...")
        try:
            # 1. Create Repo (if not exists)
            if provider == "gitcode":
                # Use connector for GitCode
                try:
                    connector.create_repo(args.repo, description=args.desc)
                    logger.info(f"Project initialized on GitCode: {args.repo}")
                except Exception as e:
                    logger.warning(f"Repo creation skipped/failed (might exist): {e}")
            else:
                # GitHub logic (subprocess GH)
                cmd = ["gh", "repo", "create", args.repo, "--private", "--add-readme"]
                if args.desc:
                    cmd.extend(["--description", args.desc])
                subprocess.run(cmd, check=False) # Don't fail if exists
                logger.info(f"Project initialized on GitHub: {args.repo}")
            
            # 2. Create Labels from Config
            sources = config.get("sources", {})
            labels_to_create = []
            
            # Define default colors if not in config (config structure is simple list now)
            # We will iterate through sources and add standard colors
            colors = {
                "requirements": "0E8A16", 
                "design": "1D76DB", 
                "development": "F9D0C4", 
                "test": "C2E0C6"
            }
            
            for key, data in sources.items():
                phase_labels = data.get("labels", [])
                for label_name in phase_labels:
                    labels_to_create.append({
                        "name": label_name, 
                        "color": colors.get(key, "CCCCCC"),
                        "desc": f"{key.title()} Phase Task"
                    })

            for label in labels_to_create:
                if provider == "gitcode":
                    connector.create_label(args.repo, label["name"], label["color"], description=label["desc"])
                else:
                    subprocess.run(["gh", "label", "create", label["name"], "--repo", args.repo, "--color", label["color"], "--description", label["desc"]], check=False)
                
            logger.info("Project init complete.")
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
                
                # Check for detailed body and other fields
                body = task.get("body", "")
                estimation = task.get("estimation", "")
                
                # Assignee prediction
                assignees = resource_mgr.find_best_assignee(task['labels'])
                assignee_str = f" @{assignees[0]}" if assignees else ""
                
                # Enhanced Markdown Format
                content += f"## {task_title}\n"
                content += f"- **Tags**: {labels}\n"
                content += f"- **Assignee**: {assignee_str}\n"
                if estimation:
                    content += f"- **Estimation**: {estimation} SP\n"
                
                if body:
                    content += f"\n{body}\n"
                else:
                    content += "- [ ] Implement task\n"
                
                content += "\n---\n"
                
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
        pattern = re.compile(r'- \[([ x])\] (.*?)(?: @([\w-]+))?(?: #(\d+))?$')

        # Get default requirement labels from config
        req_labels = get_phase_labels('requirement')
        if not req_labels:
            req_labels = ["type:requirement"] # Fallback

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
                
                # Assignee Logic
                assignees = []
                if manual_assignee:
                    assignees = [manual_assignee]
                else:
                    # Parse tags from title like (type:dev, domain:api)
                    tags = [title_raw] 
                    matches = re.findall(r'\(([^)]+)\)', title_raw)
                    if matches:
                        tags = []
                        for match in matches:
                            parts = [t.strip() for t in match.split(',')]
                            tags.extend(parts)
                    assignees = resource_mgr.find_best_assignee(tags)
                
                # Create Issue
                logger.info(f"Creating: {title_raw}")
                # Use configured labels
                connector.create_issue(args.repo, title_raw, "Imported Task", labels=req_labels, assignees=assignees)
                logger.info(f"Imported: {title_raw} -> Assigned to {assignees}")

    elif args.command == "launch":
        # Pass config to PhaseManager
        phase_mgr = PhaseManager(connector, resource_mgr, args.repo, config)
        
        # 1. Check Gate
        closed_parent_tasks = phase_mgr.check_gate(args.from_phase, args.to_phase)
        
        if not closed_parent_tasks:
            logger.error(f"Gate failed or no tasks found in phase '{args.from_phase}'. Cannot transition.")
            return

        logger.info(f"Gate Passed. Found {len(closed_parent_tasks)} parent tasks.")
        
        # 2. Generate Next Phase Tasks
        next_phase_labels = get_phase_labels(args.to_phase)
        
        next_tasks = []
        for parent in closed_parent_tasks:
            new_title = f"{args.to_phase.title()} for #{parent['number']}: {parent['title']}"
            new_task = {
                "title": new_title,
                "body": f"Transitioned from Phase: {args.from_phase}",
                "labels": next_phase_labels,
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
        report_gen = ReportGenerator(connector, resource_mgr, args.repo, config)
        
        # Determine output path: CLI args > Config > Default
        out_path = args.out
        if out_path == "REPORT.md": # Default value
            export_dir = config.get("export", {}).get("path", ".")
            if export_dir and export_dir != ".":
                os.makedirs(export_dir, exist_ok=True)
                out_path = os.path.join(export_dir, "REPORT.md")
        
        report_gen.generate(out_path)

if __name__ == "__main__":
    main()
