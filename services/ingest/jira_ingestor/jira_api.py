import time, json, requests
from tenacity import retry, wait_exponential, stop_after_attempt

# --- OAuth token refresh ---
@retry(wait=wait_exponential(min=1, max=30), stop=stop_after_attempt(5))
def refresh_access_token(client_id, client_secret, refresh_token):
    r = requests.post("https://auth.atlassian.com/oauth/token", json={
        "grant_type": "refresh_token",
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token
    }, timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

# --- Jira HTTP GET with simple 429 handling ---
def jira_get(base_url, token, path, params=None):
    url = f"{base_url}{path}"
    h = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    r = requests.get(url, headers=h, params=params or {}, timeout=30)
    if r.status_code == 429:
        retry_after = int(r.headers.get("Retry-After", "5"))
        time.sleep(retry_after)
        r = requests.get(url, headers=h, params=params or {}, timeout=30)
    r.raise_for_status()
    return r.json()

# --- Find custom fields once; return ids for AC & Deployment Notes ---
def discover_field_map(base_url, token, synonyms=None):
    synonyms = synonyms or {
        "acceptance_criteria": ["acceptance criteria", "acceptance-criteria", "ac", "gherkin"],
        "deployment_notes": ["deployment notes", "deploy notes", "release notes (tech)"]
    }
    fields = jira_get(base_url, token, "/rest/api/3/field")
    def find_id(target_names):
        tset = set(n.lower() for n in target_names)
        for f in fields:
            name = (f.get("name") or "").strip().lower()
            if name in tset:
                return f.get("id")
        return None
    return {
        "acceptance_criteria": find_id(synonyms["acceptance_criteria"]),
        "deployment_notes": find_id(synonyms["deployment_notes"]),
        "raw": fields
    }

# --- Search issues (paged) ---
def search_page(base_url, token, jql, fields_csv, start_at=0, max_results=100):
    return jira_get(base_url, token, "/rest/api/3/search", {
        "jql": jql, "fields": fields_csv, "startAt": start_at, "maxResults": max_results
    })

# --- Fetch all comments if truncated on search response ---
def get_all_comments_if_needed(base_url, token, issue):
    f = issue.get("fields", {})
    summary = f.get("summary")
    comment_block = f.get("comment") or {}
    comments = comment_block.get("comments", []) or []
    total = comment_block.get("total", len(comments))
    if len(comments) >= total:
        return comments  # already complete
    # page remaining
    all_comments = comments[:]
    start_at = len(comments)
    while len(all_comments) < total:
        data = jira_get(base_url, token, f"/rest/api/3/issue/{issue['id']}/comment", {
            "startAt": start_at, "maxResults": 100
        })
        page = data.get("comments", []) or []
        if not page:
            break
        all_comments.extend(page)
        start_at += len(page)
        time.sleep(0.2)
    return all_comments
