#!/usr/bin/env python3
import json
import logging
import os
import datetime
import subprocess

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

        # 1. Fetch Remote Issues
        remote_issues = self.connector.fetch_issues(self.repo, state="all")
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

        # Regex for Markdown checkbox: - [ ] Title #123
        import re
        pattern = re.compile(r'- \[([ x])\] (.*?)(?: #(\d+))?$')

        for line in lines:
            match = pattern.search(line.strip())
            new_line = line
            
            if match:
                is_checked = match.group(1) == 'x'
                title = match.group(2).strip()
                issue_id = match.group(3)

                remote_task = None
                if issue_id and issue_id in remote_map_id:
                    remote_task = remote_map_id[issue_id]
                elif title in remote_map_title:
                    remote_task = remote_map_title[title]

                if remote_task:
                    remote_is_closed = remote_task['state'] == 'closed'
                    remote_id = str(remote_task['number'])

                    # Sync Logic
                    if remote_is_closed and not is_checked:
                        # Remote Closed -> Update Local
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
                        if not re.search(r'#\d+$', new_line.strip()):
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
