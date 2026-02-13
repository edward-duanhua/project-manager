#!/usr/bin/env python3
import shutil
import subprocess
import json
import logging
import time

class GitHubConnector:
    """
    Connects to GitHub CLI (gh) with robust error handling and retries.
    """
    def __init__(self, logger=None):
        self.logger = logger or logging.getLogger(__name__)
        
    def check_auth(self):
        if not shutil.which("gh"):
            self.logger.error("GitHub CLI (gh) not found.")
            return False
        try:
            res = subprocess.run(["gh", "auth", "status"], capture_output=True)
            return res.returncode == 0
        except Exception as e:
            self.logger.error(f"Auth check failed: {e}")
            return False

    def run_command(self, cmd, check=True, retries=3):
        """Execute gh command with retry logic."""
        for attempt in range(retries):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=check)
                return result
            except subprocess.CalledProcessError as e:
                if attempt == retries - 1:
                    if check: raise e
                    return e # Return the error object if not raising
                self.logger.warning(f"Command failed (attempt {attempt+1}/{retries}): {e.stderr.strip()}. Retrying...")
                time.sleep(1) # Simple backoff
            except Exception as e:
                self.logger.error(f"System error: {e}")
                raise e

    def fetch_issues(self, repo, state="open", labels=None, limit=100):
        cmd = ["gh", "issue", "list", "--repo", repo, "--state", state, "--json", "number,title,state,assignees,labels,milestone,createdAt", "--limit", str(limit)]
        if labels:
            for label in labels:
                cmd.extend(["--label", label])
        
        try:
            res = self.run_command(cmd)
            return json.loads(res.stdout)
        except Exception:
            self.logger.error("Failed to fetch issues.")
            return []

    def create_issue(self, repo, title, body, labels=None, assignees=None):
        cmd = ["gh", "issue", "create", "--repo", repo, "--title", title, "--body", body]
        if labels:
            for label in labels:
                cmd.extend(["--label", label])
        if assignees:
            for assignee in assignees:
                cmd.extend(["--assignee", assignee])
        
        return self.run_command(cmd)

    def close_issue(self, repo, issue_number, comment=None):
        cmd = ["gh", "issue", "close", str(issue_number), "--repo", repo]
        if comment:
            cmd.extend(["--comment", comment])
        return self.run_command(cmd, check=False)
