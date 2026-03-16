from __future__ import annotations

import json
import shutil
import tempfile
from pathlib import Path

from intake_core import apply_approved_correction, process_correction_request_issue, process_new_student_issue


def run_harness() -> None:
    root = Path(__file__).resolve().parents[1]
    pepper = "dev-pepper-for-tests"
    advisor_login = "MustafaHameed"

    with tempfile.TemporaryDirectory() as tmp_dir:
        sandbox = Path(tmp_dir) / "NSCT_HEC"
        shutil.copytree(root, sandbox)

        new_issue_body = """### Student Full Name
Ali Raza

### CNIC
3520212345671

### Program
BSIT

### Session
2024-2028

### Roll Number
BSIT-24-001

### Email
ali@example.com

### Phone
+923001112233
"""

        result_new = process_new_student_issue(
            repo_root=sandbox,
            issue_number=101,
            issue_author="student-user",
            issue_body=new_issue_body,
            pepper=pepper,
            advisor_login=advisor_login,
        )
        assert result_new.valid and result_new.proceed_pr, result_new.message

        duplicate_result = process_new_student_issue(
            repo_root=sandbox,
            issue_number=102,
            issue_author="student-user",
            issue_body=new_issue_body,
            pepper=pepper,
            advisor_login=advisor_login,
        )
        assert not duplicate_result.valid, "Duplicate should fail"

        correction_body = """### Existing CNIC
35202-1234567-1

### Fields to Correct
email,phone

### Corrected Email
ali.updated@example.com

### Corrected Phone
+923009998887

### Reason for Correction
Typo in contact details.
"""

        correction_result = process_correction_request_issue(
            repo_root=sandbox,
            issue_number=201,
            issue_author="student-user",
            issue_body=correction_body,
            pepper=pepper,
            advisor_login=advisor_login,
        )
        assert correction_result.valid and correction_result.proceed_pr, correction_result.message

        denied_approval = apply_approved_correction(
            repo_root=sandbox,
            issue_number=201,
            approver_login="other-advisor",
            advisor_login=advisor_login,
        )
        assert not denied_approval.valid, "Mismatched advisor should fail"

        approved_approval = apply_approved_correction(
            repo_root=sandbox,
            issue_number=201,
            approver_login="MustafaHameed",
            advisor_login=advisor_login,
        )
        assert approved_approval.valid and approved_approval.proceed_pr, approved_approval.message

        rows = (sandbox / "data" / "master" / "students.json").read_text(encoding="utf-8")
        data = json.loads(rows)
        assert data[0]["email"] == "ali.updated@example.com"

    print("NSCT_HEC harness passed: new intake, duplicate block, correction approval flow.")


if __name__ == "__main__":
    run_harness()
