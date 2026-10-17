"""Core data models and contracts for WinDoc diagnostics."""

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional
from pydantic import BaseModel, ConfigDict, Field


class CheckStatus(str, Enum):
    """Status of a diagnostic check execution."""
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"
    UNKNOWN = "UNKNOWN"
    SKIPPED = "SKIPPED"
    ERROR = "ERROR"


class Severity(str, Enum):
    """Severity classification for a diagnostic finding."""
    INFO = "INFO"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class ResultKind(str, Enum):
    """Categorization of what the result represents."""
    OBSERVATION = "OBSERVATION"      # Direct measurement (e.g. adapter link state is Down)
    INFERENCE = "INFERENCE"          # Derived conclusion (e.g. DHCP failure inferred from 169.254.x.x IP)
    CONFIRMED = "CONFIRMED"          # Independently verified condition


class DiagnosticResult(BaseModel):
    """Standardized result format for all WinDoc diagnostic checks."""
    check_id: str = Field(..., description="Unique identifier for the check, e.g. 'net.adapter.physical_state'")
    domain: str = Field(..., description="Problem domain, e.g. 'network', 'bluetooth', 'update'")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc), description="UTC timestamp of the check")
    observation: str = Field(..., description="Human-readable description of what was observed")
    status: CheckStatus = Field(..., description="Standardized check outcome")
    severity: Severity = Field(default=Severity.INFO, description="Severity of the finding")
    result_kind: ResultKind = Field(default=ResultKind.OBSERVATION, description="Nature of the result")
    
    # Optional diagnostic metadata
    measured_value: Optional[Any] = Field(default=None, description="Raw measured value or property map")
    error_code: Optional[str] = Field(default=None, description="System error code if applicable, e.g. '0x80070005'")
    data_source: str = Field(default="system", description="Command or API providing the data, e.g. 'Get-NetAdapter'")
    limitations: Optional[str] = Field(default=None, description="Known check limitations or boundary conditions")
    admin_required: bool = Field(default=False, description="Whether administrator elevation is required for this check")
    admin_available: bool = Field(default=False, description="Whether administrator privileges were active during the check")
    execution_error: Optional[str] = Field(default=None, description="Subprocess or unexpected runtime error message if status == ERROR")

    model_config = ConfigDict(frozen=True)
