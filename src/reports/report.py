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
    def __init__(self, connector, resource_mgr, repo_name):
        self.connector = connector
        self.resource_mgr = resource_mgr
        self.repo = repo_name
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

    def generate_gantt(self, issues):
        """Generates Mermaid Gantt chart syntax."""
        chart = "gantt\n    dateFormat YYYY-MM-DD\n    title Project Schedule\n"
        today = datetime.date.today().strftime("%Y-%m-%d")
        
        # Group by label (Phase)
        phases = {}
        for i in issues:
            labels = [l['name'] for l in i.get('labels', [])]
            phase = next((l for l in labels if l.startswith('type:')), 'Other')
            if phase not in phases: phases[phase] = []
            phases[phase].append(i)
            
        for phase, items in phases.items():
            section_name = phase.replace('type:', '').title()
            chart += f"    section {section_name}\n"
            for item in items[:10]: # Limit to avoid chart clutter
                status = "done" if item['state'] == 'closed' else "active"
                start = item.get('createdAt', today).split('T')[0]
                # End date approximation (created + 7 days)
                end = (datetime.datetime.strptime(start, "%Y-%m-%d") + datetime.timedelta(days=7)).strftime("%Y-%m-%d")
                
                chart += f"    {item['title'].replace(':', '')} : {status}, {start}, {end}\n"
                
        return chart
