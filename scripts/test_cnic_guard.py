from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from cnic_leak_guard import collect_candidate_files, read_allowlist, scan_paths


def find_repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current.parent] + list(current.parents):
        if (parent / "config" / "cnic_scan_allowlist.txt").exists():
            return parent
    raise FileNotFoundError("Could not locate standalone NSCT_HEC repo root.")


def run_guard_test() -> None:
    repo_root = find_repo_root()
    allowlist = read_allowlist(repo_root / "config" / "cnic_scan_allowlist.txt")

    with tempfile.TemporaryDirectory() as tmp_dir:
        sandbox = Path(tmp_dir) / "scan"
        sandbox.mkdir(parents=True, exist_ok=True)

        safe_file = sandbox / "safe.txt"
        safe_file.write_text("No sensitive value here. Masked CNIC xxxxx-xxxx1234 only.\n", encoding="utf-8")

        unsafe_file = sandbox / "unsafe.txt"
        unsafe_file.write_text("Accidental raw CNIC 35202-1234567-1 should be detected.\n", encoding="utf-8")

        findings = scan_paths(repo_root=sandbox, candidate_files=[safe_file, unsafe_file], allowlist_patterns=[])
        assert len(findings) == 1, f"Expected 1 finding, got {len(findings)}"
        assert findings[0].matched_text == "35202-1234567-1"

        fixture_path = repo_root / "tests" / "fixtures" / "cnic_scan" / "unsafe_sample.txt"
        fixture_copy = sandbox / "tests" / "fixtures" / "cnic_scan" / "unsafe_sample.txt"
        fixture_copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(fixture_path, fixture_copy)

        allowed_findings = scan_paths(repo_root=sandbox, candidate_files=[fixture_copy], allowlist_patterns=allowlist)
        assert len(allowed_findings) == 0, "Allowlisted fixture should be ignored"

        candidates = collect_candidate_files(sandbox, tracked_only=False, scan_roots=["."])
        assert safe_file in candidates and unsafe_file in candidates

    print("CNIC guard test passed: detects raw CNIC and respects allowlist.")


if __name__ == "__main__":
    run_guard_test()
