# NSCT_HEC Operations Runbook

## Maintainer setup
1. Configure repository as private.
2. Add repository secret `CNIC_PEPPER`.
3. Ensure Actions are enabled.
4. Enable branch protection for `main` (PR required, review required).

## Daily operations
1. Triage new issues with labels from forms.
2. Wait for workflow output comment:
   - `status:validated` means eligible for PR.
   - `status:needs-info` means request update from submitter.
3. Review generated PR and merge only after verification.

## Correction operations
1. Correction issue creates pending payload in `data/pending_corrections/`.
2. Advisor must comment exactly `/approve-correction`.
3. Approval workflow applies correction and opens PR.
4. Merge only after confirming advisor identity and change reason.

## Label suggestions
- `intake:new`
- `intake:correction`
- `status:new`
- `status:awaiting-advisor`
- `status:validated`
- `status:needs-info`

## Incident handling
- If raw CNIC appears in files or comments, immediately remove via new commit and rotate `CNIC_PEPPER`.
- If suspicious requests are submitted, apply `status:needs-info` and ask for advisor confirmation.
