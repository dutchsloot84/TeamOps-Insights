import datetime as dt
import json
import logging
import os
import time
import boto3
from jira_api import refresh_access_token, search_page, discover_field_map, get_all_comments_if_needed
from adf_md import to_markdown

log = logging.getLogger()
log.setLevel(logging.INFO)

secrets = boto3.client("secretsmanager")
ssm = boto3.client("ssm")
s3 = boto3.client("s3")

S3_BUCKET = os.environ["S3_BUCKET"]
CURSOR_PARAM = os.environ.get("CURSOR_PARAM", "/rag/jira/last_sync")
JIRA_OAUTH_SECRET = os.environ["JIRA_OAUTH_SECRET"]

def _get_secret():
    data = secrets.get_secret_value(SecretId=JIRA_OAUTH_SECRET)
    val = json.loads(data["SecretString"])
    return val["client_id"], val["client_secret"], val["refresh_token"], val["base_url"]

def _load_cursor():
    try:
        return ssm.get_parameter(Name=CURSOR_PARAM)["Parameter"]["Value"]
    except ssm.exceptions.ParameterNotFound:
        return (dt.datetime.utcnow() - dt.timedelta(days=30)).strftime("%Y-%m-%d %H:%M")

def _save_cursor(val):
    ssm.put_parameter(Name=CURSOR_PARAM, Value=val, Type="String", Overwrite=True)

def _put_s3_json(key, obj):
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=json.dumps(obj, ensure_ascii=False).encode("utf-8"))

def _normalize_issue(issue, field_ids, base_url):
    f = issue["fields"]

    # Ensure full comment list
    comments = get_all_comments_if_needed(base_url, token=None, issue=issue)  # token unused in helper
    # Build comment objects with ADF->MD
    norm_comments = []
    for cm in comments:
        norm_comments.append({
            "author": (cm.get("author") or {}).get("displayName"),
            "created": cm.get("created"),
            "adf": cm.get("body"),
            "markdown": to_markdown(cm.get("body"))
        })

    # Linked issues
    links = []
    for link in f.get("issuelinks", []) or []:
        t = (link.get("type") or {}).get("name")
        if "outwardIssue" in link:
            links.append({"type": t, "direction": "outward", "key": link["outwardIssue"]["key"]})
        if "inwardIssue" in link:
            links.append({"type": t, "direction": "inward", "key": link["inwardIssue"]["key"]})

    # Custom fields
    ac_id = field_ids.get("acceptance_criteria")
    dn_id = field_ids.get("deployment_notes")

    def wrap(adf):
        return {"adf": adf, "markdown": to_markdown(adf)}

    obj = {
        "source": "jira",
        "key": issue["key"],
        "project": (f.get("project") or {}).get("key"),
        "issue_type": (f.get("issuetype") or {}).get("name"),
        "status": (f.get("status") or {}).get("name"),
        "summary": f.get("summary"),
        "description": wrap(f.get("description")),
        "acceptance_criteria": wrap(f.get(ac_id)) if ac_id else {"adf": None, "markdown": ""},
        "deployment_notes": wrap(f.get(dn_id)) if dn_id else {"adf": None, "markdown": ""},
        "comments": norm_comments,
        "links": links,
        "labels": f.get("labels") or [],
        "components": [c["name"] for c in (f.get("components") or [])],
        "fix_versions": [v["name"] for v in (f.get("fixVersions") or [])],
        "reporter": (f.get("reporter") or {}).get("displayName"),
        "assignee": (f.get("assignee") or {}).get("displayName"),
        "created": f.get("created"),
        "updated": f.get("updated"),
        "uri": f"{base_url}/browse/{issue['key']}",
        "fetched_at": dt.datetime.utcnow().isoformat() + "Z"
    }
    return obj

def handler(event, context):
    client_id, client_secret, refresh_token, base_url = _get_secret()
    token = refresh_access_token(client_id, client_secret, refresh_token)

    # Discover custom fields (Acceptance Criteria, Deployment Notes)
    field_map = discover_field_map(base_url, token)
    ac_id = field_map.get("acceptance_criteria")
    dn_id = field_map.get("deployment_notes")

    fields = [
        "summary","description","comment","issuelinks","labels","components",
        "fixVersions","issuetype","status","project","reporter","assignee",
        "created","updated"
    ]
    if ac_id:
        fields.append(ac_id)
    if dn_id:
        fields.append(dn_id)
    fields_csv = ",".join(fields)

    cursor = _load_cursor()
    jql = f'updated >= "{cursor}" ORDER BY updated ASC'
    log.info(f"JQL: {jql}")
    start = 0
    last_seen = cursor
    total_processed = 0

    while True:
        page = search_page(base_url, token, jql, fields_csv, start_at=start, max_results=100)
        issues = page.get("issues", [])
        if not issues:
            break

        for it in issues:
            # Save RAW with a timestamped key
            raw_key = f'raw/jira/{it["key"]}/{it["id"]}-{it["fields"]["updated"].replace(":","").replace(" ","_")}.json'
            _put_s3_json(raw_key, it)

            # Build normalized doc
            norm = _normalize_issue(it, {"acceptance_criteria": ac_id, "deployment_notes": dn_id}, base_url)
            _put_s3_json(f'normalized/jira/{it["key"]}.json', norm)

            last_seen = it["fields"]["updated"]
            total_processed += 1

        start += len(issues)
        time.sleep(0.2)  # be gentle to Jira rate limits

    _save_cursor(last_seen)
    return {"synced_through": last_seen, "count": total_processed}
