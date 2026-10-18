"""Controlled repair subsystem for WinDoc."""

from windoc.repairs.executor import execute_repair
from windoc.repairs.models import RepairExecutionResult, RepairStatus, RiskLevel
from windoc.repairs.registry import RepairAction, registry

__all__ = [
    "RepairAction",
    "RepairStatus",
    "RiskLevel",
    "RepairExecutionResult",
    "registry",
    "execute_repair",
]
