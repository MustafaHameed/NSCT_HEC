from __future__ import annotations

import argparse
import fnmatch
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Sequence

FORMATTED_CNIC_PATTERN = r"(?<!\d)\d{5}-\d{7}-\d(?!\d)"
DIGITS_ONLY_CNIC_PATTERN = r"(?<!\d)\d{13}(?!\d)"
TEXT_SUFFIXES_TO_SKIP = {
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".bmp",
    ".pdf",
    ".zip",
    ".xlsx",
    ".xls",
    ".doc",
    ".docx",
    ".ppt",
    ".pptx",
    ".pyc",
    ".ico",
}
SUPPRESSION_TOKEN = "CNIC_SCAN_ALLOW"

try:
    import re
except ImportError as exc:  # pragma: no cover
    raise RuntimeError("Python regex support is required") from exc

FORMATTED_CNIC_REGEX = re.compile(FORMATTED_CNIC_PATTERN)
DIGITS_ONLY_CNIC_REGEX = re.compile(DIGITS_ONLY_CNIC_PATTERN)


@dataclass
class Finding:
    path: str
    line_number: int
    matched_text: str
    line_excerpt: str


def read_allowlist(allowlist_path: Path) -> List[str]:
    if not allowlist_path.exists():
        return []
    patterns: List[str] = []
    for raw_line in allowlist_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if line and not line.startswith("#"):
            patterns.append(line)
    return patterns


def resolve_allowlist_path(repo_root: Path, configured_path: str) -> Path:
    primary = (repo_root / configured_path).resolve()
    if primary.exists():
        return primary

    fallback = (repo_root / "NSCT_HEC" / configured_path).resolve()
    return fallback if fallback.exists() else primary


def default_scan_roots(repo_root: Path) -> List[str]:
    if (repo_root / "NSCT_HEC").is_dir():
        return ["NSCT_HEC", ".github"]

    return [
        ".github",
        "config",
        "data",
        "docs",
        "schemas",
        "scripts",
        "tests",
        "README.md",
        "requirements.txt",
        "CODEOWNERS",
    ]


def is_allowlisted(relative_path: str, patterns: Sequence[str]) -> bool:
    normalized = relative_path.replace("\\", "/")
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in patterns)


def is_text_candidate(path: Path) -> bool:
    return path.suffix.lower() not in TEXT_SUFFIXES_TO_SKIP


def git_tracked_files(repo_root: Path) -> List[Path]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
        check=True,
    )
    files = [repo_root / line for line in result.stdout.splitlines() if line.strip()]
    return files


def is_within_scan_roots(repo_root: Path, file_path: Path, scan_roots: Sequence[str]) -> bool:
    relative_path = file_path.resolve().relative_to(repo_root.resolve()).as_posix()
    normalized_roots = [root.strip("/") for root in scan_roots if root.strip()]
    return any(
        relative_path == root or relative_path.startswith(f"{root}/")
        for root in normalized_roots
    )


def walk_files(repo_root: Path, scan_roots: Sequence[str]) -> List[Path]:
    files: List[Path] = []
    for scan_root in scan_roots:
        absolute = (repo_root / scan_root).resolve()
        if absolute.is_file():
            files.append(absolute)
            continue
        if absolute.is_dir():
            for path in absolute.rglob("*"):
                if path.is_file():
                    files.append(path)
    return files


def collect_candidate_files(repo_root: Path, tracked_only: bool, scan_roots: Sequence[str]) -> List[Path]:
    candidates = git_tracked_files(repo_root) if tracked_only else walk_files(repo_root, scan_roots)
    unique: List[Path] = []
    seen = set()
    for path in candidates:
        resolved = path.resolve()
        if tracked_only and not is_within_scan_roots(repo_root, resolved, scan_roots):
            continue
        if resolved not in seen and is_text_candidate(resolved):
            seen.add(resolved)
            unique.append(resolved)
    return unique


def scan_file(repo_root: Path, file_path: Path, allowlist_patterns: Sequence[str]) -> List[Finding]:
    relative_path = file_path.relative_to(repo_root).as_posix()
    if is_allowlisted(relative_path, allowlist_patterns):
        return []

    try:
        contents = file_path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return []

    findings: List[Finding] = []
    for line_number, line in enumerate(contents.splitlines(), start=1):
        if SUPPRESSION_TOKEN in line:
            continue

        for regex in (FORMATTED_CNIC_REGEX, DIGITS_ONLY_CNIC_REGEX):
            for match in regex.finditer(line):
                findings.append(
                    Finding(
                        path=relative_path,
                        line_number=line_number,
                        matched_text=match.group(0),
                        line_excerpt=line.strip(),
                    )
                )
    return findings


def scan_paths(repo_root: Path, candidate_files: Sequence[Path], allowlist_patterns: Sequence[str]) -> List[Finding]:
    findings: List[Finding] = []
    for file_path in candidate_files:
        findings.extend(scan_file(repo_root, file_path, allowlist_patterns))
    return findings


def write_summary(mode: str, findings: Sequence[Finding]) -> None:
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    title = "## Raw CNIC detector"
    lines = [title]
    if not findings:
        lines.append("- No raw CNIC-like patterns detected in scanned tracked files.")
    else:
        lines.append(f"- Mode: `{mode}`")
        lines.append(f"- Findings: `{len(findings)}`")
        for finding in findings[:20]:
            lines.append(
                f"- `{finding.path}:{finding.line_number}` matched `{finding.matched_text}`"
            )
    with open(summary_path, "a", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")


def print_findings(findings: Sequence[Finding]) -> None:
    for finding in findings:
        print(
            f"{finding.path}:{finding.line_number}: raw CNIC-like pattern detected -> "
            f"{finding.matched_text} | {finding.line_excerpt}"
        )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Detect raw CNIC-like patterns in tracked files")
    parser.add_argument("--repo-root", default=".", help="Repository root path")
    parser.add_argument(
        "--scan-root",
        action="append",
        default=[],
        help="Relative root to scan when not using --tracked-only (repeatable)",
    )
    parser.add_argument(
        "--allowlist",
        default="config/cnic_scan_allowlist.txt",
        help="Relative path to allowlist file",
    )
    parser.add_argument(
        "--tracked-only",
        action="store_true",
        help="Scan only git-tracked files",
    )
    parser.add_argument(
        "--mode",
        choices=["warn", "fail"],
        default="fail",
        help="Exit behavior when findings are detected",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    repo_root = Path(args.repo_root).resolve()
    allowlist_path = resolve_allowlist_path(repo_root, args.allowlist)
    allowlist_patterns = read_allowlist(allowlist_path)

    scan_roots = args.scan_root or default_scan_roots(repo_root)
    candidate_files = collect_candidate_files(repo_root, args.tracked_only, scan_roots)
    findings = scan_paths(repo_root, candidate_files, allowlist_patterns)

    write_summary(args.mode, findings)

    if findings:
        print_findings(findings)
        if args.mode == "warn":
            print(f"Warning: detected {len(findings)} raw CNIC-like pattern(s).")
            return 0
        print(f"Error: detected {len(findings)} raw CNIC-like pattern(s).")
        return 1

    print("No raw CNIC-like patterns detected.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
