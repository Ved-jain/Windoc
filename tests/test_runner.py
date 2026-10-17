"""Unit tests for the safe command runner and PowerShell executor."""

import sys
from unittest.mock import patch
import subprocess
import pytest

from windoc.core.runner import run_command, run_powershell


def test_run_command_success() -> None:
    """Test running a valid python command returning 0."""
    result = run_command([sys.executable, "-c", "print('hello windoc')"])
    assert result.is_success is True
    assert result.exit_code == 0
    assert result.stdout == "hello windoc"
    assert result.stderr == ""
    assert result.duration_ms > 0
    assert result.timed_out is False


def test_run_command_non_zero_exit() -> None:
    """Test running a command that exits with non-zero status."""
    result = run_command([sys.executable, "-c", "import sys; sys.exit(42)"])
    assert result.is_success is False
    assert result.exit_code == 42
    assert result.timed_out is False


def test_run_command_not_found() -> None:
    """Test executing a non-existent binary returns an error without raising an exception."""
    result = run_command(["non_existent_binary_xyz_12345"])
    assert result.is_success is False
    assert result.exit_code == -1
    assert "Executable not found" in (result.error or "")


def test_run_command_timeout() -> None:
    """Test that a command exceeding timeout is terminated safely."""
    # Run python sleep for 2 seconds with a 0.2 second timeout
    result = run_command(
        [sys.executable, "-c", "import time; time.sleep(2)"],
        timeout_seconds=0.2,
    )
    assert result.is_success is False
    assert result.timed_out is True
    assert result.exit_code == -1
    assert "timed out" in (result.error or "")


def test_run_powershell_structured_json() -> None:
    """Test running PowerShell with JSON serialization."""
    ps_script = "[PSCustomObject]@{ Status = 'Up'; Speed = 1000 }"
    cmd_result, parsed = run_powershell(ps_script, as_json=True, ensure_list=True)

    assert cmd_result.is_success is True
    assert isinstance(parsed, list)
    assert len(parsed) == 1
    assert parsed[0]["Status"] == "Up"
    assert parsed[0]["Speed"] == 1000


def test_run_powershell_malformed_json_fallback() -> None:
    """Test that malformed JSON from stdout is handled safely without crashing."""
    with patch("windoc.core.runner.run_command") as mock_run:
        from windoc.core.runner import CommandResult
        mock_run.return_value = CommandResult(
            args=["powershell.exe"],
            exit_code=0,
            stdout="NOT_VALID_JSON",
            stderr="",
            duration_ms=10.0,
            timed_out=False,
            error=None,
        )
        cmd_result, parsed = run_powershell("Get-Something", as_json=True)
        assert cmd_result.is_success is True
        assert parsed is None
