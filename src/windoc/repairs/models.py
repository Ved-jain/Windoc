"""Data models and contracts for the WinDoc controlled repair subsystem."""

from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from pydantic import BaseModel, Field

from windoc.core.models import DiagnosticResult
from windoc.core.runner import CommandResult


class RiskLevel(str, Enum):
    """Risk classification of a repair operation."""
    LOW = "LOW"          # Reversible, non-destructive, minimal or no service interruption
    MEDIUM = "MEDIUM"    # May temporarily interrupt network connections or restart services
    HIGH = "HIGH"        # May modify persistent system configuration or require a reboot
    CRITICAL = "CRITICAL"# High-impact action (disallowed in Version 1)


class RepairStatus(str, Enum):
    """Outcome of a repair execution attempt."""
    SUCCESS = "SUCCESS"                      # Operation executed AND independent verification passed
    PARTIAL_SUCCESS = "PARTIAL_SUCCESS"      # Some improvements observed, but symptom persists partially
    FAILED = "FAILED"                        # Command failed to execute or exited with an error
    PERMISSION_DENIED = "PERMISSION_DENIED"  # Requires administrator privileges that were not available
    ABORTED = "ABORTED"                      # User declined to authorize the repair
    VERIFICATION_FAILED = "VERIFICATION_FAILED"  # Command succeeded (exit code 0), but verification failed!


class RepairExecutionResult(BaseModel):
    """Comprehensive result of an attempted repair procedure."""
    repair_id: str = Field(..., description="Unique identifier of the repair executed")
    name: str = Field(..., description="Human-readable name of the repair")
    status: RepairStatus = Field(..., description="Final outcome of the repair attempt")
    message: str = Field(..., description="Detailed explanation of the outcome for the user")
    command_result: Optional[CommandResult] = Field(default=None, description="Subprocess execution output if run")
    pre_state: Dict[str, Any] = Field(default_factory=dict, description="Captured system state before repair")
    post_state: Dict[str, Any] = Field(default_factory=dict, description="Captured system state after repair")
    verified: bool = Field(default=False, description="Whether independent post-repair verification succeeded")
    verification_results: List[DiagnosticResult] = Field(default_factory=list, description="Diagnostic evidence from post-repair verification")
