"""Core engine, runner, models, and hypothesis evaluation for WinDoc."""

from windoc.core.engine import (
    DiagnosisFinding,
    DiagnosisReport,
    HypothesisStatus,
    evaluate_bluetooth_hypotheses,
    evaluate_network_hypotheses,
)
from windoc.core.models import (
    CheckStatus,
    DiagnosticResult,
    ResultKind,
    Severity,
)
from windoc.core.runner import (
    CommandResult,
    run_command,
    run_powershell,
)

__all__ = [
    "CheckStatus",
    "DiagnosticResult",
    "ResultKind",
    "Severity",
    "CommandResult",
    "run_command",
    "run_powershell",
    "HypothesisStatus",
    "DiagnosisFinding",
    "DiagnosisReport",
    "evaluate_network_hypotheses",
    "evaluate_bluetooth_hypotheses",
]
