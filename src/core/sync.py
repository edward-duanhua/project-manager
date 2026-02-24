#!/usr/bin/env python3
import json
import logging
import os
import datetime
import subprocess
import re

class SyncManager:
    """
    Synchronizes tasks between local files and remote GitHub issues.
    """
    def __init__(self, connector, resource_mgr, repo_name):
        self.connector = connector
        self.resource_mgr = resource_mgr
        self.repo = repo_name
        self.logger = logging.getLogger(__name__)

    def sync(self, local_path):
        """
        Syncs local file status with remote GitHub status.
        Priority:
        - If Remote is Closed & Local is Open -> Update Local to [x]
        - If Local is Closed & Remote is Open -> Close Remote Issue
        """
        if not os.path.exists(local_path):
            self.logger.warning(f"Local file not found: {local_path}. Skipping sync.")
            return

        # 1. Fetch Remote Issues (with pagination)
        remote_issues = self.connector.fetch_issues(self.repo, state="all", limit=500) # Assuming connector handles pagination or increased limit
        if not remote_issues:
            self.logger.warning("No remote issues fetched. Skipping sync.")
            return

        # Map by issue ID (if present in local file) or Title (less reliable)
        remote_map_id = {str(i['number']): i for i in remote_issues}
        remote_map_title = {i['title']: i for i in remote_issues}

        # 2. Read Local File
        with open(local_path, "r") as f:
            lines = f.readlines()

        updated_lines = []
        changes_count = 0

        # Optimized Regex for Markdown checkbox
        # Supports:
        # - [ ] Task Title
        # - [x] **Task Title**
        # - [ ] [Task Title](url)
        # - [ ] Task Title #123
        pattern = re.compile(r'^\s*- \[([ x])\] (.*?)(?: #(\d+))?\s*$')

        for line in lines:
            line_stripped = line.strip()
            # Skip non-task lines quickly
            if not line_stripped.startswith("- ["):
                updated_lines.append(line)
                continue

            match = pattern.search(line_stripped)
            new_line = line
            
            if match:
                is_checked = match.group(1) == 'x'
                raw_content = match.group(2).strip()
                issue_id = match.group(3)
                
                # Extract clean title by removing Markdown links/bold if needed for matching
                # But for now, we rely on exact title match if no ID, which might be flaky with formatting.
                # Better approach: Try to match ID first, then title.
                
                # Clean title for matching (remove ** and [])
                clean_title = re.sub(r'\[(.*?)\]\(.*?\)', r'\1', raw_content) # Remove links
                clean_title = clean_title.replace('**', '').replace('__', '').strip()

                remote_task = None
                if issue_id and issue_id in remote_map_id:
                    remote_task = remote_map_id[issue_id]
                elif clean_title in remote_map_title:
                    remote_task = remote_map_title[clean_title]
                elif raw_content in remote_map_title: # Try raw content too
                     remote_task = remote_map_title[raw_content]

                if remote_task:
                    remote_is_closed = remote_task['state'] == 'closed'
                    remote_id = str(remote_task['number'])

                    # Sync Logic
                    if remote_is_closed and not is_checked:
                        # Remote Closed -> Update Local
                        # Use exact replacement of [ ] with [x] to preserve indentation
                        new_line = line.replace('- [ ]', '- [x]', 1)
                        self.logger.info(f"Sync: Remote #{remote_id} Closed -> Local Updated")
                        changes_count += 1
                    elif is_checked and not remote_is_closed:
                        # Local Checked -> Close Remote
                        try:
                            self.connector.close_issue(self.repo, remote_id, "Closed via Local Sync")
                            self.logger.info(f"Sync: Local Checked -> Remote #{remote_id} Closed")
                            changes_count += 1
                        except Exception as e:
                            self.logger.error(f"Failed to close remote issue #{remote_id}: {e}")

                    # Backfill ID if missing
                    if not issue_id:
                        # Append ID if not present
                        # Check if line already ends with ID pattern to be safe
                        if not re.search(r'#\d+\s*$', new_line.strip()):
                            # Preserve newline
                            new_line = new_line.rstrip() + f" #{remote_id}\n"
                            changes_count += 1
            
            updated_lines.append(new_line)

        # 3. Write Back
        if changes_count > 0:
            with open(local_path, "w") as f:
                f.writelines(updated_lines)
            self.logger.info(f"Sync completed. Updated {changes_count} items.")
        else:
            self.logger.info("Sync completed. No changes detected.")
