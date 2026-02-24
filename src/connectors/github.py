#!/usr/bin/env python3
import shutil
import subprocess
import json
import logging
import time
import os

class GitHubConnector:
    """
    Connects to GitHub CLI (gh) with robust error handling and retries.
    Can use GITHUB_TOKEN from env if provided.
    """
    def __init__(self, logger=None, token_env="GITHUB_TOKEN"):
        self.logger = logger or logging.getLogger(__name__)
        self.token_env = token_env
        self.token = os.getenv(token_env)
        
    def _get_env(self):
        """Injects token into env if available."""
        env = os.environ.copy()
        if self.token:
            env["GITHUB_TOKEN"] = self.token
        return env
        
    def check_auth(self):
        if not shutil.which("gh"):
            self.logger.error("GitHub CLI (gh) not found.")
            return False
        try:
            # gh auth status might fail if using token only (it expects login),
            # so we try a simple api call instead if token is present
            if self.token:
                res = subprocess.run(["gh", "api", "user"], capture_output=True, env=self._get_env())
            else:
                res = subprocess.run(["gh", "auth", "status"], capture_output=True)
            return res.returncode == 0
        except Exception as e:
            self.logger.error(f"Auth check failed: {e}")
            return False

    def run_command(self, cmd, check=True, retries=3):
        """Execute gh command with retry logic."""
        env = self._get_env()
        for attempt in range(retries):
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=check, env=env)
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
        # GitHub CLI limits to 30 by default, so explicit limit is important.
        # But 'gh issue list' doesn't support pagination via simple page param easily, 
        # it uses --limit to fetch up to N.
        # So we just pass the user-requested limit directly. 
        # If limit > 1000, gh might truncate, but for CLI tool usually acceptable.
        
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
