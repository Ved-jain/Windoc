"""Safe command execution engine for Windows subprocesses and PowerShell."""

import json
import subprocess
import time
from typing import Any, List, Optional
from pydantic import BaseModel, Field


class CommandResult(BaseModel):
    """Result of an executed system command."""
    args: List[str] = Field(..., description="The command and arguments executed")
    exit_code: int = Field(..., description="Process exit code, or -1 on failure")
    stdout: str = Field(default="", description="Captured standard output")
    stderr: str = Field(default="", description="Captured standard error")
    duration_ms: float = Field(default=0.0, description="Execution duration in milliseconds")
    timed_out: bool = Field(default=False, description="Whether the process timed out")
    error: Optional[str] = Field(default=None, description="System error message if process failed to start or timed out")

    @property
    def is_success(self) -> bool:
        """Return True if command finished with exit code 0 and did not time out."""
        return self.exit_code == 0 and not self.timed_out and self.error is None


def run_command(
    args: List[str],
    timeout_seconds: float = 10.0,
    cwd: Optional[str] = None,
) -> CommandResult:
    """Safely execute an external command without shell interpretation.
    
    Security guarantees:
    - shell=False strictly enforced to prevent command injection.
    - Strict timeout enforcement to prevent hung processes.
    - Safe encoding fallback using errors='replace' to prevent UnicodeDecodeError.
    """
    start_time = time.perf_counter()
    try:
        proc = subprocess.run(
            args,
            shell=False,
            capture_output=True,
            timeout=timeout_seconds,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return CommandResult(
            args=args,
            exit_code=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            duration_ms=round(duration_ms, 2),
            timed_out=False,
            error=None,
        )
    except subprocess.TimeoutExpired as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        stdout = exc.stdout.decode("utf-8", errors="replace").strip() if isinstance(exc.stdout, bytes) else (exc.stdout or "").strip()
        stderr = exc.stderr.decode("utf-8", errors="replace").strip() if isinstance(exc.stderr, bytes) else (exc.stderr or "").strip()
        return CommandResult(
            args=args,
            exit_code=-1,
            stdout=stdout,
            stderr=stderr,
            duration_ms=round(duration_ms, 2),
            timed_out=True,
            error=f"Command timed out after {timeout_seconds} seconds",
        )
    except FileNotFoundError:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return CommandResult(
            args=args,
            exit_code=-1,
            stdout="",
            stderr="",
            duration_ms=round(duration_ms, 2),
            timed_out=False,
            error=f"Executable not found: {args[0] if args else ''}",
        )
    except OSError as exc:
        duration_ms = (time.perf_counter() - start_time) * 1000.0
        return CommandResult(
            args=args,
            exit_code=-1,
            stdout="",
            stderr="",
            duration_ms=round(duration_ms, 2),
            timed_out=False,
            error=f"OS execution error: {exc}",
        )


def run_powershell(
    script: str,
    timeout_seconds: float = 15.0,
    as_json: bool = False,
    ensure_list: bool = False,
) -> tuple[CommandResult, Any]:
    """Execute a PowerShell command safely and optionally deserialize structured JSON output.
    
    Args:
        script: The PowerShell command or pipeline to run.
        timeout_seconds: Maximum time allowed before terminating the process.
        as_json: If True, appends ConvertTo-Json and parses the JSON response into Python objects.
        ensure_list: If True and as_json is True, ensures the parsed data is returned as a list.
        
    Returns:
        A tuple of (CommandResult, parsed_json_or_none).
    """
    exec_script = script
    if as_json:
        # Wrap the expression in parentheses and convert to compressed JSON with depth limit
        exec_script = f"@({script}) | ConvertTo-Json -Compress -Depth 4"

    args = [
        "powershell.exe",
        "-NoProfile",
        "-NonInteractive",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        exec_script,
    ]

    cmd_result = run_command(args, timeout_seconds=timeout_seconds)
    parsed_data = None

    if as_json and cmd_result.is_success and cmd_result.stdout:
        try:
            parsed_data = json.loads(cmd_result.stdout)
            if ensure_list:
                if parsed_data is None:
                    parsed_data = []
                elif isinstance(parsed_data, dict):
                    parsed_data = [parsed_data]
        except json.JSONDecodeError:
            # If JSON decoding fails, return None for parsed data while keeping stdout in cmd_result
            parsed_data = None

    return cmd_result, parsed_data
