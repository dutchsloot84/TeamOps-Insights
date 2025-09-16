"""AWS Lambda entry point for running the releasecopilot audit."""
from __future__ import annotations

import json
import logging
from typing import Any, Dict

from main import AuditConfig, run_audit

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def lambda_handler(event: Dict[str, Any], _context: Any) -> Dict[str, Any]:
    """AWS Lambda handler that proxies events into the CLI orchestration."""
    logger.info("Received event: %s", json.dumps(event))

    config = AuditConfig(
        fix_version=event["fix_version"],
        repos=event.get("repos", []),
        branches=event.get("branches"),
        window_days=int(event.get("window_days", 28)),
        freeze_date=event.get("freeze_date"),
        develop_only=event.get("develop_only", False),
        upload_s3=event.get("upload_s3", False),
        use_cache=event.get("use_cache", False),
        s3_bucket=event.get("s3_bucket"),
        s3_prefix=event.get("s3_prefix", "releasecopilot"),
        output_prefix=event.get("output_prefix", "audit_results"),
    )

    result = run_audit(config)
    response = {
        "status": "success",
        "summary": result["summary"],
        "artifacts": result.get("artifacts", {}),
    }
    logger.info("Audit completed: %s", json.dumps(response["summary"]))
    return response
