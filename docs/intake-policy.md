# NSCT_HEC Intake Policy

## 1) Authoritative Key

- Authoritative unique key: **CNIC**.
- CNIC is normalized and converted to `cnic_hash` using SHA-256 + secret pepper (`CNIC_PEPPER`).

## 2) Privacy

- Do not store raw CNIC in master datasets.
- Store only:
  - `cnic_hash` (64-char SHA-256 hex)
  - `masked_cnic` (e.g., `xxxxx-xxxx1234`)
- Repository should remain private.
- If the repository is public, workflows will emit a privacy warning to remind maintainers that NSCT_HEC is intended for private use.
- Raw CNIC must not be copied into issue comments, PR descriptions, review comments, or tracked documentation.

## 3) New Student Intake

- New intake is accepted only if `cnic_hash` does not already exist.
- Required fields: `full_name`, `cnic`, `program`, `session`, `advisor_github`.
- At least one contact value is required: `email` or `phone`.

## 4) Correction Requests

- Correction requests are allowed only for existing students.
- Advisor approval is mandatory using issue comment command:
  - `/approve-correction`
- The commenter username must match the advisor username in the request.

## 5) Verification and Audit

- No direct writes to `main`.
- Every accepted change must be reviewed through Pull Request.
- Issue number is stored in `source_issue` for traceability.

## 6) Abuse Controls

- Use labels: `status:needs-info`, `status:validated`, `status:awaiting-advisor`.
- Review suspicious submissions manually.
- GitHub forms do not provide built-in CAPTCHA; rely on repo privacy and moderation.

## 7) Raw CNIC Detector

- The workflow `NSCT HEC Raw CNIC Guard` scans tracked files for CNIC-like patterns on push and pull request.
- Default mode is `fail`, so accidental raw CNIC in tracked files blocks the workflow.
- Known example files are excluded via `NSCT_HEC/config/cnic_scan_allowlist.txt`.
- If a legitimate example is ever required in a tracked file, it must be placed in an allowlisted path or marked with the suppression token `CNIC_SCAN_ALLOW`.
