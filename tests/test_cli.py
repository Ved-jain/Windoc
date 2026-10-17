"""Unit tests for the WinDoc CLI interface."""

import pytest
from typer.testing import CliRunner

from windoc import __version__
from windoc.cli import app

runner = CliRunner()


def test_cli_version() -> None:
    """Verify that `windoc --version` prints the version string and exits with 0."""
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "WinDoc" in result.stdout
    assert __version__ in result.stdout


def test_cli_help() -> None:
    """Verify that `windoc --help` displays command usage and subcommands."""
    result = runner.invoke(app, ["--help"])
    assert result.exit_code == 0
    assert "Evidence-driven Windows diagnostics" in result.stdout
    assert "info" in result.stdout
    assert "list-domains" in result.stdout


def test_cli_info() -> None:
    """Verify that `windoc info` runs cleanly and reports system information."""
    result = runner.invoke(app, ["info"])
    assert result.exit_code == 0
    assert "WinDoc Environment" in result.stdout
    assert "Operating System" in result.stdout
    assert "Administrator Privileges" in result.stdout


def test_cli_list_domains() -> None:
    """Verify that `windoc list-domains` displays supported and planned diagnostic domains."""
    result = runner.invoke(app, ["list-domains"])
    assert result.exit_code == 0
    assert "Diagnostic Domains" in result.stdout
    assert "network" in result.stdout
    assert "bluetooth" in result.stdout
    assert "drivers" in result.stdout
    assert "update" in result.stdout
