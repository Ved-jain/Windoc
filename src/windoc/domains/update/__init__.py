"""Windows Update diagnostic domain for WinDoc."""

from windoc.domains.update.checks import run_all_update_checks

__all__ = ["run_all_update_checks"]
