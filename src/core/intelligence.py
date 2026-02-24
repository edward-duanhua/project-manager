import json
import logging
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

class IntelligenceEngine:
    """
    AI Engine supporting both Heuristics (Rule-based) and LLM (API-based).
    Configurable via data/config.json.
    """
    def __init__(self, logger=None, config_path="skills/project-manager/data/config.json"):
        self.logger = logger or logging.getLogger(__name__)
        self.config = self._load_config(config_path)
        
        # Setup session with retry
        self.session = requests.Session()
        retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
        self.session.mount('https://', HTTPAdapter(max_retries=retries))
        self.session.mount('http://', HTTPAdapter(max_retries=retries))
        
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
        Uses requests with retry logic.
        """
        conf = self.config.get("intelligence", {})
        
        # 1. Check api_key_env from config (e.g. "LLM_API_KEY")
        api_key = None
        env_var_name = conf.get("api_key_env")
        if env_var_name:
            api_key = os.getenv(env_var_name)
            
        # 2. Fallback to direct api_key in config
        if not api_key:
            api_key = conf.get("api_key")

        # 3. Fallback to standard OpenAI env var
        if not api_key:
            api_key = os.getenv("OPENAI_API_KEY")
        
        if not api_key:
            self.logger.error("LLM Configured but API Key not found (checked config.api_key_env, config.api_key, and env.OPENAI_API_KEY).")
            return None

        prompt = f"""
        You are a Senior Project Manager and Technical Architect.
        Analyze the following requirement deeply. Break it down into concrete, actionable technical tasks (5-10 tasks).
        
        Requirement: "{text}"
        
        Output format: JSON Array of objects.
        
        Each object MUST have:
        - "title": Concise, action-oriented title (e.g., "Design User Schema").
        - "body": Detailed description including:
            - **Goal**: What needs to be achieved.
            - **Technical Considerations**: API endpoints, DB changes, libraries.
            - **Acceptance Criteria**: Bullet points for DoD (Definition of Done).
        - "labels": Array of strings.
            - Must include ONE phase label: 'type:design', 'type:dev', or 'type:test'.
            - Must include domain labels: 'domain:api', 'domain:ui', 'domain:db', 'domain:security'.
            - Optional priority: 'p1', 'p2'.
        - "estimation": Story points (Fibonacci: 1, 2, 3, 5, 8).
        
        Example JSON Output:
        [
          {{
            "title": "Design Database Schema for User Profile",
            "body": "**Goal**: Create scalable schema for user profiles.\\n**Tech**: PostgreSQL, JSONB for preferences.\\n**DoD**:\\n- [ ] Schema migration script created\\n- [ ] Indexes added for email lookup",
            "labels": ["type:design", "domain:db", "p1"],
            "estimation": 3
          }}
        ]
        """
        
        payload = {
            "model": conf.get("model", "gpt-3.5-turbo"),
            "messages": [{"role": "user", "content": prompt}],
            "temperature": conf.get("temperature", 0.7)
        }
        
        url = f"{conf.get('api_base', 'https://api.openai.com/v1')}/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }

        try:
            response = self.session.post(url, json=payload, headers=headers, timeout=60)
            response.raise_for_status()
            
            result = response.json()
            content = result['choices'][0]['message']['content']
            
            # Try to parse JSON from content (it might have markdown blocks)
            if "```json" in content:
                content = content.split("```json")[1].split("```")[0].strip()
            elif "```" in content:
                content = content.split("```")[1].split("```")[0].strip()
            
            return json.loads(content)
                
        except requests.exceptions.Timeout:
            self.logger.error("LLM Call Timeout: The request took too long.")
            return None
        except requests.exceptions.RequestException as e:
            self.logger.error(f"LLM Call Failed: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            self.logger.error(f"Failed to parse LLM response as JSON: {e}. Content: {content[:100]}...")
            return None
        except Exception as e:
            self.logger.error(f"Unexpected error in LLM call: {e}")
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
