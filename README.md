# NSCT_HEC Student Intake (GitHub-Only)

This project implements a **GitHub-only** student intake and correction workflow for NSCT_HEC.

## What it does

- Collects **new student data** only when CNIC does not already exist.
- Accepts **correction requests** for existing students.
- Requires advisor verification via issue comment command: `/approve-correction`.
- Stores CNIC as **hash** (`cnic_hash`) and only keeps masked CNIC for display.
- Uses GitHub Issue Forms + GitHub Actions + Pull Requests for a full audit trail.

## Project layout

- `data/master/students.csv`: canonical master dataset
- `data/master/students.json`: JSON mirror of master dataset
- `data/pending_corrections/`: correction payloads awaiting approval
- `schemas/student.schema.json`: record schema
- `scripts/intake_core.py`: core validation and data logic
- `scripts/intake_manager.py`: workflow entrypoint for issue/comment events
- `scripts/cnic_leak_guard.py`: raw-CNIC detector for tracked files
- `scripts/test_harness.py`: local smoke test harness
- `scripts/test_cnic_guard.py`: local detector test
- `docs/intake-policy.md`: privacy and governance policy

## Required GitHub setup

1. Repository should be **Private**.
2. Add secret: `CNIC_PEPPER` (long random string).
3. Enable issue templates and Actions.
4. Configure branch protection on `main`:
   - Require pull request
   - Require status checks
   - Require at least 1 review

## Privacy preflight

- NSCT_HEC should be operated in a **private repository** because student data collection can expose sensitive identifiers.
- Keep the source Excel sheet local only; `NSCT_HEC/.gitignore` already blocks `.xlsx` files from commit.
- Never place raw CNIC in tracked files, PR descriptions, or manual comments.
- If the workflow detects a public repository, it now emits a GitHub Actions warning and writes guidance into the workflow summary.
- A dedicated workflow now scans tracked files for CNIC-like patterns and fails if a raw CNIC-like value is committed outside the allowlist.

## Shareable student links

- Planned standalone repo URL: `https://github.com/MustafaHameed/NSCT_HEC`
- New student record: `https://github.com/MustafaHameed/NSCT_HEC/issues/new?template=01_student_intake.yml`
- Update existing record: `https://github.com/MustafaHameed/NSCT_HEC/issues/new?template=02_correction_request.yml`
- These links become live after you create the standalone GitHub repository.

## One-command export

- Export this folder into a fresh standalone repo copy:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_standalone_repo.ps1 -DestinationPath "E:\Exports\NSCT_HEC" -Force
```

- Export and preconfigure the future GitHub remote:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_standalone_repo.ps1 -DestinationPath "E:\Exports\NSCT_HEC" -SetRemote -Force
```

- Export and push immediately after you create the GitHub repo and have git auth ready:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\export_standalone_repo.ps1 -DestinationPath "E:\Exports\NSCT_HEC" -SetRemote -Push -Force
```

- Script location: `scripts/export_standalone_repo.ps1`
- Default remote URL: `https://github.com/MustafaHameed/NSCT_HEC.git`

## Local test run

```powershell
cd "<standalone-NSCT_HEC-repo>"
python scripts\test_harness.py
python scripts\test_cnic_guard.py
```

## Operational flow

1. Student opens `NSCT HEC - 01 Student Intake` issue.
2. Workflow validates input and duplicates by CNIC hash.
3. Valid request creates PR updating master data.
4. For corrections, request is staged in `data/pending_corrections/`.
5. Advisor comments `/approve-correction`.
6. Approval workflow applies correction and opens PR.

## Notes

- GitHub Issue Forms do not support native CAPTCHA.
- Mitigation is private repo + validation + advisor verification + manual review labels.
- The raw-CNIC guard ignores `.github/ISSUE_TEMPLATE/*` and test fixtures because they intentionally contain example CNIC values.
