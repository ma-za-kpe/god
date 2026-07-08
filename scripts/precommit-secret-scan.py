#!/usr/bin/env python3
"""Fail fast on secret-like defaults in committed config.

This is intentionally narrow and low-noise. Full secret scanners still run in
CI, but this catches the common local failure mode where a Compose/env fallback
turns a development password into committed source.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TEXT_SUFFIXES = {
    ".cfg",
    ".env",
    ".ini",
    ".js",
    ".json",
    ".md",
    ".mjs",
    ".py",
    ".sh",
    ".toml",
    ".ts",
    ".tsx",
    ".yaml",
    ".yml",
}
IGNORED_PARTS = {
    ".git",
    "node_modules",
    "dist",
    "contracts/lib",
}
RULES = (
    (
        "NEO4J_PASSWORD_DEFAULT",
        re.compile(
            r"\$\{NEO4J_[^}:]*(?:PASSWORD|AUTH)[^}:]*:-[^}\s]+\}",
            re.IGNORECASE,
        ),
        "Do not commit default Neo4j credentials; use auth-free localhost dev or external env.",
    ),
    (
        "NEO4J_AUTH_LITERAL",
        re.compile(r"NEO4J_AUTH\s*=\s*neo4j/[^$\s{]+", re.IGNORECASE),
        "Do not commit literal Neo4j credentials; set NEO4J_AUTH outside Git.",
    ),
    (
        "CYPHER_SHELL_PASSWORD_DEFAULT",
        re.compile(r"cypher-shell\b.*\$\{NEO4J_[^}:]*(?:PASSWORD|AUTH)[^}:]*:-", re.IGNORECASE),
        "Do not commit cypher-shell password fallbacks.",
    ),
)


def main(argv: list[str]) -> int:
    findings: list[str] = []
    paths = _paths_from_args(argv[1:])
    for raw_path in paths:
        path = (ROOT / raw_path).resolve()
        if not _should_scan(path):
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(text.splitlines(), start=1):
            for code, pattern, message in RULES:
                match = pattern.search(line)
                if match:
                    findings.append(f"{relative}:{line_number}: {code}: {message}")

    if findings:
        print("Secret-like committed defaults detected:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    return 0


def _paths_from_args(args: list[str]) -> list[str]:
    if args and args != ["--all-files"]:
        return args
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def _should_scan(path: Path) -> bool:
    try:
        relative = path.relative_to(ROOT)
    except ValueError:
        return False
    normalized = relative.as_posix()
    if any(part in normalized for part in IGNORED_PARTS):
        return False
    if path.name == ".env.example":
        return False
    return path.is_file() and (path.suffix in TEXT_SUFFIXES or path.name.startswith(".env"))


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
