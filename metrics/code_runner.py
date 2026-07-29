# code_runner.py
# Executes LLM-generated code against a suite item's unit tests in an
# isolated subprocess, with a hard timeout, and reports pass/fail.
#
# SECURITY NOTE: this provides process isolation + a timeout, matching the
# plan's Windows-compatible design (no resource.setrlimit, which is
# Linux-only). It is NOT a full security sandbox — generated code still runs
# with the same OS permissions as the server process (no seccomp/container
# boundary, no network firewall). Do not point this at untrusted code in a
# production deployment without adding container-level isolation
# (e.g. gVisor, Docker with --network=none, a restricted user).

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path


@dataclass
class CodeRunResult:
    passed: bool
    error: str | None
    timed_out: bool


def run_code_test(code: str, unit_test: str, timeout_s: float = 5.0) -> CodeRunResult:
    """Run `code` (expected to define a `solution.py` module) against `unit_test`.

    Writes both files into a fresh temp directory, invokes pytest as a
    subprocess (no shell=True), and cleans up the directory unconditionally.
    """
    python_executable = sys.executable or shutil.which("python") or shutil.which("python3")
    if not python_executable:
        return CodeRunResult(passed=False, error="No Python executable found.", timed_out=False)

    tmp_dir = tempfile.mkdtemp(prefix="code_runner_")
    try:
        Path(tmp_dir, "solution.py").write_text(code, encoding="utf-8")
        Path(tmp_dir, "test_solution.py").write_text(unit_test, encoding="utf-8")

        try:
            result = subprocess.run(
                [python_executable, "-m", "pytest", "test_solution.py", "-x", "--tb=short"],
                cwd=tmp_dir,
                timeout=timeout_s,
                capture_output=True,
                text=True,
                shell=False,
            )
        except subprocess.TimeoutExpired:
            return CodeRunResult(passed=False, error="timeout", timed_out=True)

        if result.returncode == 0:
            return CodeRunResult(passed=True, error=None, timed_out=False)

        combined_output = (result.stdout + result.stderr).strip()
        return CodeRunResult(passed=False, error=combined_output[-2000:], timed_out=False)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
