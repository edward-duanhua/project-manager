#!/usr/bin/env python3
import json
import logging
import os
import datetime
import subprocess

class ReportGenerator:
    """
    Generates markdown reports and charts.
    """
    def __init__(self, connector, resource_mgr, repo_name, config):
        self.connector = connector
        self.resource_mgr = resource_mgr
        self.repo = repo_name
        self.config = config
        self.logger = logging.getLogger(__name__)

    def generate(self, output_path):
        """Generates a full status report."""
        issues = self.connector.fetch_issues(self.repo, state="all", limit=500)
        
        # Calculate Stats
        total = len(issues)
        closed = len([i for i in issues if i['state'] == 'closed'])
        progress = int((closed / total) * 100) if total > 0 else 0
        
        # Risk Analysis
        risks = self.analyze_risks(issues)
        
        # Gantt Chart Data
        gantt_data = self.generate_gantt(issues)
        
        # Markdown Content
        content = f"# 📊 Project Report: {self.repo}\n\n"
        content += f"## Status: {progress}% Complete\n"
        content += f"- **Total Tasks**: {total}\n"
        content += f"- **Closed**: {closed}\n"
        content += f"- **Open**: {total - closed}\n\n"
        
        if risks:
            content += "## ⚠️ Risks Detected\n"
            for risk in risks:
                content += f"- {risk}\n"
            content += "\n"
        
        # Traceability Matrix
        content += "## 🔗 Traceability Matrix\n"
        content += "| Parent Task | Derived Task | Status |\n|---|---|---|\n"
        
        # Simple heuristic mapping based on body content
        for i in issues:
            if "Derived from #" in i.get('body', ''):
                import re
                match = re.search(r"Derived from #(\d+)", i['body'])
                if match:
                    parent_id = match.group(1)
                    # Find parent info
                    parent = next((p for p in issues if str(p['number']) == parent_id), None)
                    parent_title = parent['title'] if parent else "Unknown"
                    content += f"| #{parent_id} {parent_title} | #{i['number']} {i['title']} | {i['state']} |\n"
        content += "\n"

        content += "## 📅 Schedule (Gantt)\n"
        content += "```mermaid\n" + gantt_data + "\n```\n"
        
        with open(output_path, "w") as f:
            f.write(content)
        
        self.logger.info(f"Report generated at {output_path}")

    def analyze_risks(self, issues):
        """Analyzes overdue, overloaded, and unassigned tasks."""
        risks = []
        today = datetime.date.today()
        
        # Check overdue
        for i in issues:
            if i['state'] == 'open' and i.get('milestone') and i['milestone'].get('dueOn'):
                due = datetime.datetime.strptime(i['milestone']['dueOn'].split('T')[0], "%Y-%m-%d").date()
                if due < today:
                    risks.append(f"OVERDUE: #{i['number']} {i['title']} (Due: {due})")
        
        # Check unassigned
        unassigned = [i for i in issues if i['state'] == 'open' and not i['assignees']]
        if unassigned:
            risks.append(f"UNASSIGNED: {len(unassigned)} open tasks found without owner.")
            
        return risks

    def _get_phase_from_labels(self, labels):
        """
        Determines the phase of an issue based on its labels and config.
        """
        if not labels:
            return "Other"
            
        label_names = [l['name'] for l in labels]
        sources = self.config.get("sources", {})
        
        # Iterate through config to find a match
        # phases in config: "requirements", "design", "development"
        # labels in config: ["type:requirement"], ["type:design"], ...
        
        for phase_key, data in sources.items():
            config_labels = data.get("labels", [])
            for cl in config_labels:
                if cl in label_names:
                    return phase_key.title() # e.g. "Requirements"
        
        return "Other"

    def generate_gantt(self, issues):
        """Generates Mermaid Gantt chart syntax."""
        chart = "gantt\n    dateFormat YYYY-MM-DD\n    title Project Schedule\n"
        today = datetime.date.today().strftime("%Y-%m-%d")
        
        # Group by Phase (Config-driven)
        phases = {}
        for i in issues:
            phase = self._get_phase_from_labels(i.get('labels', []))
            
            if phase not in phases: phases[phase] = []
            phases[phase].append(i)
            
        # Sort phases if possible? Config keys order is somewhat preserved in Py3.7+
        # Let's enforce a standard order if keys match standard ones
        standard_order = ["Requirements", "Design", "Development", "Test", "Other"]
        sorted_phase_keys = sorted(phases.keys(), key=lambda k: standard_order.index(k) if k in standard_order else 99)

        for phase in sorted_phase_keys:
            items = phases[phase]
            chart += f"    section {phase}\n"
            for item in items[:10]: # Limit to avoid chart clutter
                status = "done" if item['state'] == 'closed' else "active"
                start = item.get('createdAt', today).split('T')[0]
                # End date approximation (created + 7 days)
                end = (datetime.datetime.strptime(start, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                
                # Mermaid syntax safety: remove colons from titles
                safe_title = item['title'].replace(':', '')
                chart += f"    {safe_title} : {status}, {start}, {end}\n"
                
        return chart
