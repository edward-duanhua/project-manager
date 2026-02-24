import requests
import logging
import json
import os

class GitCodeConnector:
    """
    Connects to GitCode API (GitLab-compatible).
    Requires GITCODE_TOKEN env var.
    """
    def __init__(self, logger=None, base_url="https://api.gitcode.com/api/v5"):
        # GitCode API is mostly GitLab v4 compatible, but endpoint is v5
        # If v5 fails for projects, it might be due to namespace issues or v4 is preferred.
        # Let's try v5 first as configured.
        self.logger = logger or logging.getLogger(__name__)
        self.base_url = base_url.rstrip('/')
        self.token = os.environ.get("GITCODE_TOKEN")
        
    def _headers(self):
        return {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

    def create_repo(self, repo_path, description=None, private=True):
        """
        Creates a new project in GitCode.
        repo_path: "owner/repo" or "repo"
        """
        parts = repo_path.split('/')
        if len(parts) == 2:
            owner, name = parts
        else:
            owner = None # Will default to user
            name = repo_path

        data = {
            "name": name,
            "private": private,
            "description": description or ""
        }
        
        # Determine endpoint based on owner
        if owner:
            # Check if owner is current user (optimization, or just use /user/repos)
            # But safer to try /orgs/{owner}/repos if not user. 
            # GitCode v5 seems GitHub compatible.
            # If owner is 'computing_application_lab', try /orgs first.
            url = f"{self.base_url}/orgs/{owner}/repos"
            
            # Fallback for user namespace if orgs fails? 
            # Or maybe just use /user/repos if owner is me?
            # Let's try /orgs/ first.
        else:
            url = f"{self.base_url}/user/repos"

        try:
            res = requests.post(url, headers=self._headers(), json=data)
            if res.status_code == 404 and owner:
                 # Maybe it's a user, not an org? Or endpoint is different?
                 # Try /user/repos if the owner matches authenticated user login?
                 # For now, let's just log and raise if 404 on org.
                 self.logger.warning(f"Failed to create in org {owner}, maybe it's a user? Retrying as user repo (if name matches).")
            
            res.raise_for_status()
            return res.json()
        except Exception as e:
            self.logger.error(f"Failed to create repo at {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                self.logger.error(f"Response: {e.response.text}")
            raise e

    def create_label(self, repo, name, color, description=None):
        # GitCode v5 seems to require query parameters for labels
        # and color must include #
        url = f"{self.base_url}/repos/{repo}/labels"
        
        # Ensure color has #
        safe_color = f"#{color}" if not color.startswith("#") else color
        
        params = {
            "name": name,
            "color": safe_color
        }
        if description:
            params["description"] = description
            
        try:
            # Pass params, empty json body or just no body
            res = requests.post(url, headers=self._headers(), params=params)
            
            if res.status_code == 422 or res.status_code == 409: 
                self.logger.info(f"Label {name} already exists or invalid.")
                return None
            
            # GitCode might return 400 if color is invalid format even with #
            if res.status_code == 400:
                self.logger.warning(f"Failed to create label {name}: {res.text}")
                return None
                
            res.raise_for_status()
            return res.json()
        except Exception as e:
            self.logger.error(f"Failed to create label {name}: {e}")
            return None

    def check_auth(self):
        if not self.token:
            self.logger.error("GITCODE_TOKEN not found.")
            return False
        try:
            res = requests.get(f"{self.base_url}/user", headers=self._headers())
            return res.status_code == 200
        except Exception as e:
            self.logger.error(f"Auth check failed: {e}")
            return False

    def fetch_issues(self, repo, state="opened", labels=None, limit=100):
        # GitCode/GitLab use 'opened' instead of 'open'
        state_map = {"open": "opened", "closed": "closed", "all": "all"}
        api_state = state_map.get(state, "opened")
        
        # Consistent with create_issue fix: use /repos/:owner/:repo/issues if possible
        if "/" in str(repo):
             url = f"{self.base_url}/repos/{repo}/issues"
        else:
             url = f"{self.base_url}/projects/{repo}/issues"
        
        all_issues = []
        page = 1
        per_page = 100 # GitCode usually caps at 100
        
        while len(all_issues) < limit:
            params = {
                "state": api_state,
                "per_page": per_page,
                "page": page
            }
            if labels:
                params["labels"] = ",".join(labels)
                
            try:
                res = requests.get(url, headers=self._headers(), params=params)
                res.raise_for_status()
                data = res.json()
                
                if not data:
                    break # No more pages
                    
                for item in data:
                    if len(all_issues) >= limit:
                        break
                    
                    all_issues.append({
                        "number": item.get("iid"),
                        "title": item.get("title"),
                        "state": item.get("state"), # opened/closed
                        "labels": item.get("labels", []),
                        "assignees": item.get("assignees", []),
                        "milestone": item.get("milestone", None),
                        "createdAt": item.get("created_at")
                    })
                
                # Check pagination headers if available, or just check if full page returned
                if len(data) < per_page:
                    break
                    
                page += 1
                
            except Exception as e:
                self.logger.error(f"Failed to fetch issues (page {page}): {e}")
                break
                
        return all_issues

    def create_issue(self, repo, title, body, labels=None, assignees=None):
        if "/" in str(repo):
             url = f"{self.base_url}/repos/{repo}/issues"
        else:
             url = f"{self.base_url}/projects/{repo}/issues"

        # V5 API requires 'labels' as a comma-separated string even in JSON?
        # Or maybe the error "body parsing" means we are sending something it doesn't like at all.
        # Let's try to be super standard.
        
        # GitCode doc says: 
        # POST /repos/:owner/:repo/issues
        # Body: { title, body, labels: "label1,label2" } (String) OR List?
        # The error 400 usually comes when types mismatch.
        
        # Let's try formatting labels as a STRING, not list. 
        # Most GitCode/GitLab APIs prefer string for labels.
        
        data = {
            "title": title,
            "body": body
        }
        
        # NOTE: GitCode API v5 quirks
        # - It prefers 'labels' as a comma-separated STRING in the JSON body
        # - It might not like 'labels' key at all if empty?
        # Let's ensure we only add it if we have labels.
        
        if labels:
            if isinstance(labels, list):
                # Join with commas: "bug,p1"
                data["labels"] = ",".join(labels)
            else:
                data["labels"] = labels
            
        try:
            # IMPORTANT: GitCode v5 might require query params for 'labels' similar to label creation?
            # Or it strictly validates Content-Type.
            # Let's try passing data as *JSON*.
            
            res = requests.post(url, headers=self._headers(), json=data)
            
            # If 400 Bad Request with "body parsing error", maybe it wants 'description' instead of 'body'?
            # GitLab uses 'description'. GitHub uses 'body'. 
            # If GitCode v5 is hybrid, it's tricky.
            # Let's fallback to try 'description' if 400.
            
            if res.status_code == 400:
                self.logger.warning(f"Creation failed with 'body' (400). Retrying with 'description'...")
                data["description"] = data.pop("body")
                res = requests.post(url, headers=self._headers(), json=data)
            
            res.raise_for_status()
            return res.json()
        except Exception as e:
            self.logger.error(f"Failed to create issue at {url}: {e}")
            if hasattr(e, 'response') and e.response is not None:
                 self.logger.error(f"Response: {e.response.text}")
            raise e

    def close_issue(self, repo, issue_number, comment=None):
        encoded_repo = repo.replace("/", "%2F")
        url = f"{self.base_url}/projects/{encoded_repo}/issues/{issue_number}"
        
        data = {"state_event": "close"}
        
        try:
            res = requests.put(url, headers=self._headers(), json=data)
            res.raise_for_status()
            
            if comment:
                # Add comment separately
                comment_url = f"{url}/notes"
                requests.post(comment_url, headers=self._headers(), json={"body": comment})
                
            return res.json()
        except Exception as e:
            self.logger.error(f"Failed to close issue: {e}")
            raise e
