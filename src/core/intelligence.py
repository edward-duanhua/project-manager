#!/usr/bin/env python3
import json
import logging
import os
import urllib.request
import urllib.error

class IntelligenceEngine:
    """
    AI Engine supporting both Heuristics (Rule-based) and LLM (API-based).
    Configurable via data/config.json.
    """
    def __init__(self, logger=None, config_path="skills/project-manager/data/config.json"):
        self.logger = logger or logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Domain Knowledge Base (Heuristic Fallback)
        self.domains = {
            "api": ["REST", "GraphQL", "Swagger", "Postman", "Endpoint", "Backend", "API"],
            "ui": ["React", "Vue", "Angular", "CSS", "Frontend", "Mobile", "App", "UI", "UX"],
            "db": ["SQL", "NoSQL", "Schema", "Migration", "Redis", "Data", "Database"],
            "security": ["Auth", "OAuth", "JWT", "Encryption", "Audit", "PenTest", "Secure", "Login"],
            "ops": ["Docker", "K8s", "CI/CD", "Deploy", "Monitor", "Log", "Pipeline"]
        }
        
        # Task Templates (Heuristic Fallback)
        self.templates = {
            "api": [
                {"title": "Design API Specification (OpenAPI)", "labels": ["type:design", "domain:api"]},
                {"title": "Implement Core Endpoints", "labels": ["type:dev", "domain:api"]},
                {"title": "Write Integration Tests for API", "labels": ["type:test", "domain:api"]}
            ],
            "ui": [
                {"title": "Design UI Mockups / Wireframes", "labels": ["type:design", "domain:ui"]},
                {"title": "Implement Frontend Components", "labels": ["type:dev", "domain:ui"]},
                {"title": "Conduct UX Review", "labels": ["type:test", "domain:ui"]}
            ],
            "db": [
                {"title": "Design Database Schema", "labels": ["type:design", "domain:db"]},
                {"title": "Implement Data Migration Scripts", "labels": ["type:dev", "domain:db"]}
            ],
            "security": [
                {"title": "Design Authentication Flow (OAuth/JWT)", "labels": ["type:design", "domain:security"]},
                {"title": "Conduct Security Audit", "labels": ["type:test", "domain:security"]}
            ],
            "ops": [
                {"title": "Setup CI/CD Pipeline", "labels": ["type:ops", "domain:ops"]},
                {"title": "Configure Monitoring & Alerts", "labels": ["type:ops", "domain:ops"]}
            ]
        }

    def _load_config(self, path):
        if os.path.exists(path):
            try:
                with open(path, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def analyze_requirement(self, text):
        """
        Entry point for analysis.
        Checks config to decide between LLM and Heuristics.
        """
        mode = self.config.get("intelligence", {}).get("mode", "heuristic")
        
        if mode == "llm":
            self.logger.info("Attempting AI Analysis via LLM...")
            tasks = self._call_llm(text)
            if tasks:
                return tasks
            self.logger.warning("LLM failed or returned empty. Falling back to Heuristics.")
        
        return self._analyze_heuristic(text)

    def _call_llm(self, text):
        """
        Calls OpenAI-compatible API to generate tasks.
        """
        conf = self.config.get("intelligence", {})
        # Prioritize direct key in config, fallback to env var
        api_key = conf.get("api_key") or os.getenv(conf.get("api_key_env", "OPENAI_API_KEY"))
        
        if not api_key:
            self.logger.error("LLM Configured but API Key not found in config or environment variables.")
            return None

        prompt = f"""
        You are a Senior Project Manager.
        Analyze the following requirement and break it down into 5-10 technical tasks.
        Return ONLY a JSON array of objects with 'title' and 'labels' keys.
        Labels should include 'type:design' or 'type:dev' or 'type:test', and domain labels like 'domain:api'.
        
        Requirement: "{text}"
        
        Example JSON Output:
        [
          {{"title": "Design Database Schema", "labels": ["type:design", "domain:db"]}}
        ]
        """
        
        payload = {
            "model": conf.get("model", "gpt-3.5-turbo"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": conf.get("temperature", 0.7)
        }
        
        try:
            req = urllib.request.Request(
                f"{conf.get('api_base', 'https://api.openai.com/v1')}/chat/completions",
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "Authorization": f"Bearer {api_key}"
                }
            )
            
            with urllib.request.urlopen(req) as response:
                result = json.load(response)
                content = result['choices'][0]['message']['content']
                
                # Try to parse JSON from content (it might have markdown blocks)
                if "```json" in content:
                    content = content.split("```json")[1].split("```")[0].strip()
                elif "```" in content:
                    content = content.split("```")[1].split("```")[0].strip()
                
                return json.loads(content)
                
        except Exception as e:
            self.logger.error(f"LLM Call Failed: {e}")
            return None

    def _analyze_heuristic(self, text):
        """
        Legacy heuristic analysis.
        """
        detected_domains = set()
        text_lower = text.lower()
        
        # 1. Detect Domains
        for domain, keywords in self.domains.items():
            for kw in keywords:
                if kw.lower() in text_lower:
                    detected_domains.add(domain)
                    break
        
        # Heuristic improvements
        if "api" in text_lower or "backend" in text_lower: detected_domains.add("api")
        
        # Always suggest Ops/Security for robust projects
        if not detected_domains:
            detected_domains.add("api") # Default
        
        detected_domains.add("ops")
        detected_domains.add("security")
        
        self.logger.info(f"Heuristic Analysis: Detected domains: {list(detected_domains)}")
        
        # 2. Generate Tasks
        suggested_tasks = []
        for domain in detected_domains:
            templates = self.templates.get(domain, [])
            for tmpl in templates:
                # Contextualize title
                context_title = tmpl['title']
                if domain == 'api' and 'user' in text_lower:
                    context_title += " for User Module"
                
                suggested_tasks.append({
                    "title": context_title,
                    "labels": tmpl['labels']
                })
                
        return suggested_tasks

    def generate_design_checklist(self, requirement_title, requirement_body):

        """
        Generates a design checklist based on requirement context.
        """
        checklist = []
        text = (requirement_title + " " + requirement_body).lower()
        
        if "api" in text or "backend" in text:
            checklist.extend([
                "- [ ] Define API Endpoints (Method, URL, Params)",
                "- [ ] Design Data Models (Schema)",
                "- [ ] Handle Error Codes & Responses"
            ])
        if "ui" in text or "frontend" in text:
            checklist.extend([
                "- [ ] Create Wireframes / Mockups",
                "- [ ] Define Component Hierarchy",
                "- [ ] Check Responsiveness (Mobile/Desktop)"
            ])
        if "security" in text or "auth" in text:
            checklist.extend([
                "- [ ] Review Authentication Flow",
                "- [ ] Check Data Encryption Requirements"
            ])
            
        if not checklist:
            checklist.append("- [ ] General Design Review")
            
        return "\n".join(checklist)
