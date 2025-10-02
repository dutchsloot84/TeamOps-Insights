#!/usr/bin/env python3
"""Compose least-privilege IAM policies from captured stack resources."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable


def _write_policy(path: Path, document: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document, indent=2) + "\n", encoding="utf-8")


def _log_group_arns(region: str, account: str, names: Iterable[str]) -> list[str]:
    return [f"arn:aws:logs:{region}:{account}:log-group:{name}:*" for name in names]


def _dynamodb_arns(region: str, account: str, tables: Iterable[str]) -> list[str]:
    arns: list[str] = []
    for table in tables:
        arns.append(f"arn:aws:dynamodb:{region}:{account}:table/{table}")
        arns.append(f"arn:aws:dynamodb:{region}:{account}:table/{table}/index/*")
    return arns


def _secret_arns(region: str, account: str, secrets: Iterable[str]) -> list[str]:
    return [f"arn:aws:secretsmanager:{region}:{account}:secret:{name}" for name in secrets]


def _role_arns(account: str, roles: Iterable[str]) -> list[str]:
    return [f"arn:aws:iam::{account}:role/{role}" for role in roles]


def build_documents(resources: dict) -> dict[str, dict]:
    account = resources.get("accountId", "${aws:AccountId}")
    region = resources.get("region", "${aws:Region}")
    qualifier = resources.get("bootstrapQualifier", "hnb659fds")
    project_prefix = resources.get("projectPrefix", "ReleaseCopilot")

    log_groups = resources.get("logGroups", [])
    dynamo_tables = resources.get("dynamoTables", [])
    secrets = resources.get("secrets", [])
    roles = resources.get("roles", [])

    documents: dict[str, dict] = {}

    documents["cfn.least-priv.json"] = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "ManageStacks",
                "Effect": "Allow",
                "Action": [
                    "cloudformation:CreateChangeSet",
                    "cloudformation:CreateStack",
                    "cloudformation:DeleteChangeSet",
                    "cloudformation:DeleteStack",
                    "cloudformation:DescribeChangeSet",
                    "cloudformation:DescribeStackEvents",
                    "cloudformation:DescribeStacks",
                    "cloudformation:ExecuteChangeSet",
                    "cloudformation:GetTemplate",
                    "cloudformation:TagResource",
                    "cloudformation:UntagResource",
                    "cloudformation:UpdateStack"
                ],
                "Resource": f"arn:aws:cloudformation:{region}:{account}:stack/{project_prefix}-*/*"
            }
        ]
    }

    bucket = f"cdk-{qualifier}-assets-{account}-{region}"
    documents["s3_bootstrap.least-priv.json"] = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Sid": "BootstrapAssets",
                "Effect": "Allow",
                "Action": [
                    "s3:GetObject",
                    "s3:PutObject",
                    "s3:DeleteObject",
                    "s3:GetObjectVersion",
                    "s3:ListBucket",
                    "s3:GetBucketLocation"
                ],
                "Resource": [
                    f"arn:aws:s3:::{bucket}",
                    f"arn:aws:s3:::{bucket}/*"
                ]
            }
        ]
    }

    if log_groups:
        documents["logs.least-priv.json"] = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ManageLogGroups",
                    "Effect": "Allow",
                    "Action": [
                        "logs:CreateLogGroup",
                        "logs:CreateLogStream",
                        "logs:DeleteLogGroup",
                        "logs:DeleteLogStream",
                        "logs:DescribeLogGroups",
                        "logs:DescribeLogStreams",
                        "logs:PutLogEvents",
                        "logs:PutRetentionPolicy",
                        "logs:TagLogGroup"
                    ],
                    "Resource": _log_group_arns(region, account, log_groups)
                }
            ]
        }

    if dynamo_tables:
        documents["dynamodb.least-priv.json"] = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ManageTables",
                    "Effect": "Allow",
                    "Action": [
                        "dynamodb:BatchWriteItem",
                        "dynamodb:CreateTable",
                        "dynamodb:DeleteItem",
                        "dynamodb:DeleteTable",
                        "dynamodb:DescribeContinuousBackups",
                        "dynamodb:DescribeTable",
                        "dynamodb:DescribeTimeToLive",
                        "dynamodb:GetItem",
                        "dynamodb:ListTagsOfResource",
                        "dynamodb:PutItem",
                        "dynamodb:Query",
                        "dynamodb:TagResource",
                        "dynamodb:UpdateContinuousBackups",
                        "dynamodb:UpdateItem",
                        "dynamodb:UpdateTable"
                    ],
                    "Resource": _dynamodb_arns(region, account, dynamo_tables)
                }
            ]
        }

    if secrets:
        documents["secrets.least-priv.json"] = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "ManageSecrets",
                    "Effect": "Allow",
                    "Action": [
                        "secretsmanager:CreateSecret",
                        "secretsmanager:DeleteSecret",
                        "secretsmanager:DescribeSecret",
                        "secretsmanager:GetResourcePolicy",
                        "secretsmanager:GetSecretValue",
                        "secretsmanager:PutSecretValue",
                        "secretsmanager:RestoreSecret",
                        "secretsmanager:TagResource",
                        "secretsmanager:UpdateSecret"
                    ],
                    "Resource": _secret_arns(region, account, secrets)
                }
            ]
        }

    if roles:
        documents["passrole.least-priv.json"] = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Sid": "PassRoles",
                    "Effect": "Allow",
                    "Action": "iam:PassRole",
                    "Resource": _role_arns(account, roles)
                }
            ]
        }

    return documents


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--resources",
        type=Path,
        default=Path("infra/iam/resources.json"),
        help="Path to the resources.json file collected from diagnostics",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("infra/iam/policies/generated"),
        help="Directory to write composed policy documents",
    )
    args = parser.parse_args()

    resources = json.loads(args.resources.read_text(encoding="utf-8"))
    documents = build_documents(resources)

    for name, document in documents.items():
        output_path = args.output_dir / name
        _write_policy(output_path, document)
        print(f"wrote {output_path}")


if __name__ == "__main__":
    main()
