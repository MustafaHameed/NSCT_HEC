from __future__ import annotations

import csv
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Tuple

CNIC_REGEX = re.compile(r"^\d{5}-\d{7}-\d$")

REQUIRED_MASTER_HEADERS = [
    "student_id",
    "cnic_hash",
    "masked_cnic",
    "full_name",
    "program",
    "session",
    "roll_number",
    "email",
    "phone",
    "advisor_github",
    "status",
    "created_at",
    "updated_at",
    "source_issue",
    "source_type",
]

ISSUE_FIELD_MAP = {
    "student full name": "full_name",
    "cnic": "cnic",
    "program": "program",
    "session": "session",
    "roll number": "roll_number",
    "email": "email",
    "phone": "phone",
    "advisor github username": "advisor_github",
    "existing cnic": "existing_cnic",
    "fields to correct": "fields_to_correct",
    "corrected full name": "corrected_full_name",
    "corrected program": "corrected_program",
    "corrected session": "corrected_session",
    "corrected roll number": "corrected_roll_number",
    "corrected email": "corrected_email",
    "corrected phone": "corrected_phone",
    "reason for correction": "reason_for_correction",
}


@dataclass
class ActionResult:
    proceed_pr: bool
    valid: bool
    message: str
    commit_message: str = ""
    pr_title: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def normalize_cnic(cnic_value: str) -> str:
    digits = re.sub(r"\D", "", cnic_value or "")
    if len(digits) != 13:
        return ""
    return f"{digits[:5]}-{digits[5:12]}-{digits[12]}"


def mask_cnic(cnic_value: str) -> str:
    normalized = normalize_cnic(cnic_value)
    if not normalized:
        return ""
    return f"xxxxx-xxxx{normalized[-4:]}"


def is_valid_cnic(cnic_value: str) -> bool:
    return bool(CNIC_REGEX.match(cnic_value))


def hash_cnic(cnic_value: str, pepper: str) -> str:
    normalized = normalize_cnic(cnic_value)
    digest = hashlib.sha256(f"{normalized}|{pepper}".encode("utf-8")).hexdigest()
    return digest


def parse_issue_form(body: str) -> Dict[str, str]:
    parsed: Dict[str, str] = {}
    if not body:
        return parsed

    pattern = re.compile(r"^###\s+(.+?)\n(.*?)(?=^###\s+|\Z)", re.MULTILINE | re.DOTALL)
    for match in pattern.finditer(body):
        key = match.group(1).strip().lower()
        value = match.group(2).strip()
        canonical_key = ISSUE_FIELD_MAP.get(key)
        if canonical_key:
            parsed[canonical_key] = sanitize_form_value(value)

    return parsed


def sanitize_form_value(value: str) -> str:
    if value is None:
        return ""
    cleaned = value.strip()
    if cleaned in {"_No response_", "No response", "N/A", "n/a"}:
        return ""
    return cleaned


def parse_correction_fields(value: str) -> List[str]:
    if not value:
        return []
    fields: List[str] = []
    for part in value.split(","):
        normalized = part.strip().lower().replace(" ", "_")
        if normalized:
            fields.append(normalized)
    return fields


def ensure_storage(repo_root: Path) -> Tuple[Path, Path, Path]:
    students_csv = repo_root / "data" / "master" / "students.csv"
    students_json = repo_root / "data" / "master" / "students.json"
    pending_dir = repo_root / "data" / "pending_corrections"

    students_csv.parent.mkdir(parents=True, exist_ok=True)
    pending_dir.mkdir(parents=True, exist_ok=True)

    if not students_csv.exists():
        with students_csv.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REQUIRED_MASTER_HEADERS)
            writer.writeheader()

    if not students_json.exists():
        students_json.write_text("[]\n", encoding="utf-8")

    return students_csv, students_json, pending_dir


def load_students(students_csv: Path) -> List[Dict[str, str]]:
    with students_csv.open("r", encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
    return rows


def save_students(students_csv: Path, students_json: Path, rows: List[Dict[str, str]]) -> None:
    with students_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=REQUIRED_MASTER_HEADERS)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in REQUIRED_MASTER_HEADERS})

    students_json.write_text(json.dumps(rows, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def next_student_id(rows: List[Dict[str, str]]) -> str:
    if not rows:
        return "STU-000001"

    max_num = 0
    for row in rows:
        value = row.get("student_id", "")
        match = re.match(r"^STU-(\d+)$", value)
        if match:
            max_num = max(max_num, int(match.group(1)))

    return f"STU-{max_num + 1:06d}"


def find_student_index(rows: List[Dict[str, str]], cnic_hash: str) -> int:
    for index, row in enumerate(rows):
        if row.get("cnic_hash") == cnic_hash:
            return index
    return -1


def validate_new_issue(data: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    required_fields = ["full_name", "cnic", "program", "session", "advisor_github"]

    for field in required_fields:
        if not data.get(field):
            errors.append(f"Missing required field: {field}")

    cnic_value = normalize_cnic(data.get("cnic", ""))
    if not is_valid_cnic(cnic_value):
        errors.append("CNIC must be in 13-digit format (#####-#######-# or equivalent digits).")

    if not data.get("email") and not data.get("phone"):
        errors.append("At least one contact field is required: email or phone.")

    return errors


def validate_correction_issue(data: Dict[str, str]) -> List[str]:
    errors: List[str] = []
    required_fields = ["existing_cnic", "fields_to_correct", "reason_for_correction", "advisor_github"]

    for field in required_fields:
        if not data.get(field):
            errors.append(f"Missing required field: {field}")

    cnic_value = normalize_cnic(data.get("existing_cnic", ""))
    if not is_valid_cnic(cnic_value):
        errors.append("Existing CNIC must be valid.")

    correction_fields = parse_correction_fields(data.get("fields_to_correct", ""))
    if not correction_fields:
        errors.append("No correction fields were provided.")

    return errors


def process_new_student_issue(
    repo_root: Path,
    issue_number: int,
    issue_author: str,
    issue_body: str,
    pepper: str,
) -> ActionResult:
    if not pepper:
        return ActionResult(False, False, "CNIC pepper secret is not configured.")

    students_csv, students_json, _ = ensure_storage(repo_root)
    rows = load_students(students_csv)
    parsed = parse_issue_form(issue_body)
    errors = validate_new_issue(parsed)
    if errors:
        return ActionResult(False, False, "Validation failed: " + " | ".join(errors))

    cnic_normalized = normalize_cnic(parsed["cnic"])
    cnic_hash = hash_cnic(cnic_normalized, pepper)

    existing_index = find_student_index(rows, cnic_hash)
    if existing_index >= 0:
        return ActionResult(False, False, "Student already exists. Use correction workflow.")

    now = utc_now_iso()
    row = {
        "student_id": next_student_id(rows),
        "cnic_hash": cnic_hash,
        "masked_cnic": mask_cnic(cnic_normalized),
        "full_name": parsed.get("full_name", ""),
        "program": parsed.get("program", ""),
        "session": parsed.get("session", ""),
        "roll_number": parsed.get("roll_number", ""),
        "email": parsed.get("email", ""),
        "phone": parsed.get("phone", ""),
        "advisor_github": parsed.get("advisor_github", "").lstrip("@"),
        "status": "submitted",
        "created_at": now,
        "updated_at": now,
        "source_issue": str(issue_number),
        "source_type": "new_student",
    }
    rows.append(row)
    save_students(students_csv, students_json, rows)

    return ActionResult(
        proceed_pr=True,
        valid=True,
        message=f"New student accepted from issue #{issue_number} by {issue_author}.",
        commit_message=f"NSCT_HEC: add new student from issue #{issue_number}",
        pr_title=f"NSCT_HEC: Add new student (issue #{issue_number})",
    )


def process_correction_request_issue(
    repo_root: Path,
    issue_number: int,
    issue_author: str,
    issue_body: str,
    pepper: str,
) -> ActionResult:
    if not pepper:
        return ActionResult(False, False, "CNIC pepper secret is not configured.")

    students_csv, _, pending_dir = ensure_storage(repo_root)
    rows = load_students(students_csv)
    parsed = parse_issue_form(issue_body)

    errors = validate_correction_issue(parsed)
    if errors:
        return ActionResult(False, False, "Validation failed: " + " | ".join(errors))

    cnic_normalized = normalize_cnic(parsed["existing_cnic"])
    cnic_hash = hash_cnic(cnic_normalized, pepper)

    existing_index = find_student_index(rows, cnic_hash)
    if existing_index < 0:
        return ActionResult(False, False, "Student not found for correction request.")

    correction_payload = {
        "issue_number": issue_number,
        "issue_author": issue_author,
        "created_at": utc_now_iso(),
        "cnic_hash": cnic_hash,
        "masked_cnic": mask_cnic(cnic_normalized),
        "advisor_github": parsed.get("advisor_github", "").lstrip("@"),
        "fields_to_correct": parse_correction_fields(parsed.get("fields_to_correct", "")),
        "proposed_changes": {
            "full_name": parsed.get("corrected_full_name", ""),
            "program": parsed.get("corrected_program", ""),
            "session": parsed.get("corrected_session", ""),
            "roll_number": parsed.get("corrected_roll_number", ""),
            "email": parsed.get("corrected_email", ""),
            "phone": parsed.get("corrected_phone", ""),
        },
        "reason_for_correction": parsed.get("reason_for_correction", ""),
        "approved": False,
        "approved_by": "",
        "approved_at": "",
    }

    pending_file = pending_dir / f"issue-{issue_number}.json"
    pending_file.write_text(json.dumps(correction_payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return ActionResult(
        proceed_pr=True,
        valid=True,
        message=(
            "Correction request stored and awaiting advisor approval command "
            "(/approve-correction)."
        ),
        commit_message=f"NSCT_HEC: register correction request from issue #{issue_number}",
        pr_title=f"NSCT_HEC: Register correction request (issue #{issue_number})",
    )


def apply_approved_correction(
    repo_root: Path,
    issue_number: int,
    approver_login: str,
) -> ActionResult:
    students_csv, students_json, pending_dir = ensure_storage(repo_root)
    pending_file = pending_dir / f"issue-{issue_number}.json"

    if not pending_file.exists():
        return ActionResult(False, False, f"No pending correction file exists for issue #{issue_number}.")

    payload = json.loads(pending_file.read_text(encoding="utf-8"))
    advisor_expected = payload.get("advisor_github", "").lstrip("@").lower()
    if approver_login.lower() != advisor_expected:
        return ActionResult(False, False, "Advisor approval denied: commenter does not match requested advisor.")

    rows = load_students(students_csv)
    index = find_student_index(rows, payload.get("cnic_hash", ""))
    if index < 0:
        return ActionResult(False, False, "Target student for correction no longer exists.")

    target = rows[index]
    allowed_fields = {"full_name", "program", "session", "roll_number", "email", "phone"}
    requested_fields = payload.get("fields_to_correct", [])
    proposed = payload.get("proposed_changes", {})

    for field in requested_fields:
        if field in allowed_fields:
            new_value = sanitize_form_value(proposed.get(field, ""))
            if new_value:
                target[field] = new_value

    target["status"] = "corrected"
    target["updated_at"] = utc_now_iso()
    target["source_issue"] = str(issue_number)
    target["source_type"] = "correction"

    rows[index] = target
    save_students(students_csv, students_json, rows)

    payload["approved"] = True
    payload["approved_by"] = approver_login
    payload["approved_at"] = utc_now_iso()
    pending_file.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    return ActionResult(
        proceed_pr=True,
        valid=True,
        message=f"Correction applied for issue #{issue_number} with advisor approval by @{approver_login}.",
        commit_message=f"NSCT_HEC: apply approved correction for issue #{issue_number}",
        pr_title=f"NSCT_HEC: Apply correction (issue #{issue_number})",
    )
