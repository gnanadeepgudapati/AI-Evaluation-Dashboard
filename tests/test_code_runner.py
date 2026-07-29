# test_code_runner.py
# Covers code_runner's passing, failing, timeout, and malicious-input cases.
# All code here runs in an isolated temp dir with a hard timeout.

from metrics.code_runner import run_code_test

PASSING_CODE = "def add(a, b):\n    return a + b\n"
PASSING_TEST = "from solution import add\n\n\ndef test_add():\n    assert add(2, 3) == 5\n"

FAILING_CODE = "def add(a, b):\n    return a - b\n"

SYNTAX_ERROR_CODE = "def add(a, b:\n    return a + b\n"

TIMEOUT_CODE = "import time\n\n\ndef add(a, b):\n    time.sleep(10)\n    return a + b\n"

# "Malicious" in the sense the plan asks for: code that imports OS/network
# modules. It must not hang or crash the runner -- the timeout is the backstop.
SUSPICIOUS_IMPORT_CODE = (
    "import os\nimport socket\n\n\ndef add(a, b):\n    _ = os.getcwd()\n    return a + b\n"
)


def test_code_runner_passing_code():
    result = run_code_test(PASSING_CODE, PASSING_TEST, timeout_s=5.0)
    assert result.passed is True
    assert result.timed_out is False
    assert result.error is None


def test_code_runner_failing_assertion():
    result = run_code_test(FAILING_CODE, PASSING_TEST, timeout_s=5.0)
    assert result.passed is False
    assert result.timed_out is False
    assert result.error is not None


def test_code_runner_syntax_error_does_not_crash():
    result = run_code_test(SYNTAX_ERROR_CODE, PASSING_TEST, timeout_s=5.0)
    assert result.passed is False
    assert result.timed_out is False
    assert result.error is not None


def test_code_runner_timeout():
    result = run_code_test(TIMEOUT_CODE, PASSING_TEST, timeout_s=1.0)
    assert result.passed is False
    assert result.timed_out is True
    assert result.error == "timeout"


def test_code_runner_suspicious_import_does_not_hang():
    result = run_code_test(SUSPICIOUS_IMPORT_CODE, PASSING_TEST, timeout_s=5.0)
    assert result.timed_out is False
    assert result.passed is True
