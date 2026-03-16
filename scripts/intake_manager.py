from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Dict, List

from intake_core import (
    ActionResult,
    apply_approved_correction,
    process_correction_request_issue,
    process_new_student_issue,
)


def write_outputs(result: ActionResult) -> None:
    output_path = os.getenv("GITHUB_OUTPUT")
    if not output_path:
        return

    with open(output_path, "a", encoding="utf-8") as handle:
        handle.write(f"proceed_pr={'true' if result.proceed_pr else 'false'}\n")
        handle.write(f"valid={'true' if result.valid else 'false'}\n")
        handle.write(f"message={escape_output(result.message)}\n")
        handle.write(f"commit_message={escape_output(result.commit_message)}\n")
        handle.write(f"pr_title={escape_output(result.pr_title)}\n")


def escape_output(value: str) -> str:
    return value.replace("%", "%25").replace("\n", "%0A").replace("\r", "%0D")


def github_api_request(token: str, method: str, url: str, payload: Dict | None = None) -> None:
    body = None
    if payload is not None:
        body = json.dumps(payload).encode("utf-8")

    request = urllib.request.Request(url=url, method=method, data=body)
    request.add_header("Authorization", f"Bearer {token}")
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    if payload is not None:
        request.add_header("Content-Type", "application/json")

    with urllib.request.urlopen(request, timeout=20):
        return


def post_issue_comment(token: str, repository: str, issue_number: int, text: str) -> None:
    url = f"https://api.github.com/repos/{repository}/issues/{issue_number}/comments"
    github_api_request(token, "POST", url, {"body": text})


def add_issue_labels(token: str, repository: str, issue_number: int, labels: List[str]) -> None:
    if not labels:
        return
    url = f"https://api.github.com/repos/{repository}/issues/{issue_number}/labels"
    github_api_request(token, "POST", url, {"labels": labels})


def has_label(issue_labels: List[Dict], name: str) -> bool:
    return any((item.get("name") or "") == name for item in issue_labels)


def process_issue_event(event: Dict, repo_root: Path, pepper: str) -> ActionResult:
    issue = event.get("issue", {})
    issue_number = int(issue.get("number", 0))
    issue_author = (issue.get("user", {}) or {}).get("login", "")
    issue_body = issue.get("body", "")
    labels = issue.get("labels", [])

    if has_label(labels, "intake:new"):
        return process_new_student_issue(repo_root, issue_number, issue_author, issue_body, pepper)

    if has_label(labels, "intake:correction"):
        return process_correction_request_issue(repo_root, issue_number, issue_author, issue_body, pepper)

    return ActionResult(False, False, "Issue is not labeled for NSCT intake processing.")


def process_approval_comment_event(event: Dict, repo_root: Path) -> ActionResult:
    issue = event.get("issue", {})
    issue_number = int(issue.get("number", 0))
    issue_labels = issue.get("labels", [])
    comment = event.get("comment", {})
    comment_body = (comment.get("body") or "").strip().lower()
    approver = ((comment.get("user") or {}).get("login") or "").strip()

    if not has_label(issue_labels, "intake:correction"):
        return ActionResult(False, False, "Approval comment ignored: issue is not a correction request.")

    if comment_body != "/approve-correction":
        return ActionResult(False, False, "Approval comment ignored: command token not matched.")

    return apply_approved_correction(repo_root, issue_number, approver)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="NSCT HEC intake manager")
    parser.add_argument("command", choices=["process-issue", "process-approval"], help="Execution command")
    parser.add_argument("--event", required=True, help="Path to GitHub event JSON")
    parser.add_argument("--repo-root", required=True, help="Path to NSCT_HEC project root")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    event_path = Path(args.event)
    repo_root = Path(args.repo_root)

    if not event_path.exists():
        print("Event file not found.")
        return 1

    event = json.loads(event_path.read_text(encoding="utf-8"))
    pepper = os.getenv("CNIC_PEPPER", "")

    if args.command == "process-issue":
        result = process_issue_event(event, repo_root, pepper)
    else:
        result = process_approval_comment_event(event, repo_root)

    print(result.message)
    write_outputs(result)

    repository = os.getenv("GITHUB_REPOSITORY", "")
    token = os.getenv("GITHUB_TOKEN", "")
    issue_number = int((event.get("issue") or {}).get("number") or 0)

    if repository and token and issue_number:
        try:
            post_issue_comment(token, repository, issue_number, result.message)
            labels = []
            if result.valid and result.proceed_pr:
                labels.append("status:validated")
            elif not result.valid:
                labels.append("status:needs-info")
            add_issue_labels(token, repository, issue_number, labels)
        except urllib.error.URLError as exc:
            print(f"Warning: failed to post comment/labels: {exc}")

    return 0 if result.valid else 2


if __name__ == "__main__":
    sys.exit(main())
