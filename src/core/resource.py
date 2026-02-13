#!/usr/bin/env python3
import json
import os
import random
import logging

class ResourceManager:
    """
    Manages team resources, skill matching, and availability tracking.
    """
    def __init__(self, config_path="skills/project-manager/data/team.json", logger=None):
        self.config_path = config_path
        self.logger = logger or logging.getLogger(__name__)
        self.team = self.load_team()

    def load_team(self):
        """Loads team configuration from JSON."""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, "r") as f:
                    return json.load(f)
            except json.JSONDecodeError as e:
                self.logger.error(f"Invalid team config: {e}. Returning empty.")
                return {"members": []}
        else:
            # Default template if file missing
            self.logger.warning(f"Team config not found at {self.config_path}. Using default.")
            return {"members": [
                {"id": "edward-duanhua", "role": "PM", "skills": ["manage", "review"], "status": "active"},
                {"id": "dev-01", "role": "Backend", "skills": ["python", "api"], "status": "active"},
                {"id": "dev-02", "role": "Frontend", "skills": ["react", "ui"], "status": "active"}
            ]}

    def find_best_assignee(self, task_tags):
        """
        Finds the best assignee based on skill match and availability.
        Returns a list of assignee IDs (e.g., ['dev-01']) or None.
        """
        candidates = []
        
        # 1. Filter by status (active only)
        active_members = [m for m in self.team["members"] if m.get("status") == "active"]
        if not active_members:
            self.logger.warning("No active members found.")
            return None

        # 2. Filter by skill match
        matched_members = []
        for member in active_members:
            score = 0
            member_skills = set(member.get("skills", []))
            task_skills = set(task_tags)
            
            # Improved skill matching: split tag by delimiters to avoid partial matches
            # e.g. "java" should not match "javascript"
            # But "api" should match "domain:api"
            import re
            
            for tag in task_skills:
                # Split tag into parts (e.g., "domain:api" -> ["domain", "api"])
                tag_parts = re.split(r'[:\-\s]+', tag.lower())
                for skill in member_skills:
                    if skill.lower() in tag_parts:
                        score += 1
            
            if score > 0:
                matched_members.append({"member": member, "score": score})
        
        # 3. Sort by score (descending)
        matched_members.sort(key=lambda x: x["score"], reverse=True)
        
        if matched_members:
            # Pick top scorer (can be random among ties)
            best_pick = matched_members[0]["member"]["id"]
            self.logger.info(f"Assigned {best_pick} (score: {matched_members[0]['score']}) based on skill match.")
            return [best_pick]
        
        # Fallback: Random pick from active members (Round-robin ideally)
        fallback = random.choice(active_members)["id"]
        self.logger.info(f"Fallback assignment: {fallback} (no specific skill match).")
        return [fallback]

    def update_status(self, member_id, new_status):
        """Updates a member's availability status."""
        for m in self.team["members"]:
            if m["id"] == member_id:
                m["status"] = new_status
                self.save_team()
                return True
        return False

    def save_team(self):
        """Saves team configuration to JSON."""
        os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
        with open(self.config_path, "w") as f:
            json.dump(self.team, f, indent=2)
