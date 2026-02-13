#!/usr/bin/env python3
import json
import logging
import os
import datetime
import subprocess

class PhaseManager:
    """
    Manages project lifecycle phases, gate checks, and transitions.
    """
    def __init__(self, connector, resource_mgr, repo_name):
        self.connector = connector
        self.resource_mgr = resource_mgr
        self.repo = repo_name
        self.logger = logging.getLogger(__name__)

    def check_gate(self, current_phase, next_phase):
        """Validates all conditions before phase transition. Returns closed tasks for next step."""
        self.logger.info(f"Checking gate conditions: {current_phase} -> {next_phase}")
        
        label_map = {
            'requirement': ['type:requirement'],
            'design': ['type:design'],
            'dev': ['type:dev']
        }
        
        required_labels = label_map.get(current_phase)
        if not required_labels:
            self.logger.warning(f"Unknown phase '{current_phase}'. Cannot gate check.")
            return [] 

        # 1. Fetch OPEN issues (must be empty for strict gate)
        open_issues = self.connector.fetch_issues(self.repo, state="open", labels=required_labels)
        if open_issues:
            self.logger.error(f"Gate failed: {len(open_issues)} open tasks found in phase '{current_phase}'.")
            for i in open_issues:
                self.logger.info(f" - #{i['number']} {i['title']}")
            return []
        
        # 2. CI Check
        if current_phase == 'dev' and next_phase == 'test':
             if not self.check_ci_status():
                 self.logger.error("Gate failed: CI build failed.")
                 return []

        self.logger.info("Gate passed: All conditions met.")
        
        # 3. Fetch CLOSED issues to serve as parents for next phase
        closed_issues = self.connector.fetch_issues(self.repo, state="closed", labels=required_labels)
        return closed_issues

    def check_ci_status(self):
        """Checks latest GitHub Action run status."""
        try:
            cmd = ["gh", "run", "list", "--repo", self.repo, "--limit", "1", "--json", "conclusion"]
            res = subprocess.run(cmd, capture_output=True, text=True)
            
            if res.returncode != 0:
                self.logger.error(f"Failed to fetch CI status: {res.stderr.strip()}")
                return False
                
            runs = json.loads(res.stdout)
            if not runs: return True # No runs found, assume OK or warn
            
            status = runs[0].get("conclusion")
            self.logger.info(f"Latest CI Status: {status}")
            return status == "success"
        except Exception as e:
            self.logger.error(f"Error parsing CI status: {e}")
            return False

    def execute_transition(self, tasks_to_create):
        """
        Executes the transition by creating new tasks for the next phase.
        Tasks should be a list of dicts: {"title": str, "body": str, "labels": list, "parent_id": int}
        """
        success_count = 0
        for task in tasks_to_create:
            # Resource Assignment Logic
            assignees = self.resource_mgr.find_best_assignee(task.get('labels', []))
            
            # Traceability: Append Parent Link to Body
            body = task.get('body', '')
            if task.get('parent_id'):
                body += f"\n\n> **Traceability**: Derived from #{task['parent_id']}"
            
            try:
                self.connector.create_issue(
                    self.repo, 
                    title=task['title'], 
                    body=body,
                    labels=task.get('labels', []),
                    assignees=assignees
                )
                success_count += 1
                self.logger.info(f"Created task: {task['title']} (Ref: #{task.get('parent_id', 'N/A')})")
            except Exception as e:
                self.logger.error(f"Failed to create task '{task['title']}': {e}")
        
        return success_count
