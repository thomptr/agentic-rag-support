"""Guard test: zero secret-shaped tokens anywhere in tracked source.

Greps the working tree for known secret prefixes (OpenAI sk-, Langfuse pk-lf-,
JWT eyJ...) and asserts no matches in the code paths we ship. Excludes test
fixtures, lockfiles, and meta directories that legitimately reference these
shapes for documentation purposes.

This satisfies SC-006 (no secret exposure) by catching mistakes at commit time
rather than after a leak.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

# Prefixes treated as "shaped like a real secret". Anchored to start-of-token
# to avoid false positives on URLs or unrelated strings.
SECRET_PATTERNS = [
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}"),  # OpenAI / Anthropic
    re.compile(r"\bpk-lf-[A-Za-z0-9-]{20,}"),  # Langfuse public key
    re.compile(r"\bsk-lf-[A-Za-z0-9-]{20,}"),  # Langfuse secret key
    re.compile(r"\beyJ[A-Za-z0-9_=-]{20,}\.[A-Za-z0-9_=-]{20,}\.[A-Za-z0-9_=-]{20,}"),  # JWT
]

# Paths exempt from scanning. Tests/specs/meta directories may legitimately
# contain regex literals, placeholder examples, or lockfile hashes that look
# secret-shaped but aren't real credentials.
EXCLUDED_DIRS = {
    ".git",
    ".venv",
    ".specify",
    ".terraform",
    "tests",
    "node_modules",
    "lambdas/_dist",
    "specs",
    ".claude",
}
EXCLUDED_FILES = {
    "uv.lock",
    "package-lock.json",
    "tfplan",
    ".terraform.lock.hcl",
}


def _tracked_files() -> list[Path]:
    """Return git-tracked files only.

    We deliberately ignore working-tree-only files (`.env`, `.terraform/`,
    `lambdas/_dist/`, `tfplan`, etc.) because the goal is to catch
    *committed* secrets, not local development credentials. We also skip
    tests/specs/.claude dirs that legitimately contain placeholder examples
    (e.g., `sk-ant-...` mentioned in markdown).
    """
    result = subprocess.run(
        ["git", "-C", str(REPO_ROOT), "ls-files"],
        capture_output=True,
        text=True,
        check=True,
    )
    out: list[Path] = []
    for line in result.stdout.splitlines():
        rel = Path(line)
        parts = set(rel.parts)
        if parts & EXCLUDED_DIRS:
            continue
        if rel.name in EXCLUDED_FILES:
            continue
        if rel.suffix in {".png", ".jpg", ".jpeg", ".pdf", ".zip", ".so", ".dylib"}:
            continue
        out.append(REPO_ROOT / rel)
    return out


def test_no_secret_shaped_tokens_in_source():
    """SC-006: zero matches of secret-shaped tokens in shipped code."""
    leaks: list[tuple[Path, str, str]] = []
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for pat in SECRET_PATTERNS:
            for m in pat.finditer(text):
                leaks.append((path.relative_to(REPO_ROOT), pat.pattern, m.group(0)[:40]))
    assert not leaks, "Possible committed secrets found:\n" + "\n".join(
        f"  {p} :: {pat} -> {match}..." for p, pat, match in leaks
    )


def test_no_aws_keys_in_source():
    """SC-006: zero AWS access-key-shaped tokens in shipped code."""
    pat = re.compile(r"\b(AKIA|ASIA)[0-9A-Z]{16}\b")
    leaks: list[tuple[Path, str]] = []
    for path in _tracked_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in pat.finditer(text):
            leaks.append((path.relative_to(REPO_ROOT), m.group(0)))
    assert not leaks, "Possible AWS keys found:\n" + "\n".join(
        f"  {p} :: {match}" for p, match in leaks
    )
