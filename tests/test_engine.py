"""Unit tests for the deterministic hypothesis engine."""

import pytest
from windoc.core.engine import (
    DiagnosisReport,
    HypothesisStatus,
    evaluate_network_hypotheses,
)
from windoc.core.models import CheckStatus, DiagnosticResult, Severity


def test_evaluate_healthy_network() -> None:
    """Verify that a set of all-passing checks confirms NET_ALL_HEALTHY."""
    evidence = [
        DiagnosticResult(
            check_id="net.adapter.summary",
            domain="network",
            observation="2 operational adapters",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.ip.status",
            domain="network",
            observation="Valid IPv4 address detected",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.gateway.reachability",
            domain="network",
            observation="Gateway reachable",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.dns.resolution",
            domain="network",
            observation="DNS resolved all domains",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.external.connectivity",
            domain="network",
            observation="Full external connectivity confirmed",
            status=CheckStatus.PASS,
        ),
    ]

    report = evaluate_network_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "NET_ALL_HEALTHY"
    assert report.primary_finding.status == HypothesisStatus.CONFIRMED
    assert report.primary_finding.confidence >= 0.80


def test_evaluate_physical_disconnection() -> None:
    """Verify that failing adapter summary leads to NET_PHYSICAL_DISCONNECTED."""
    evidence = [
        DiagnosticResult(
            check_id="net.adapter.summary",
            domain="network",
            observation="0 operational adapters",
            status=CheckStatus.FAIL,
        ),
        DiagnosticResult(
            check_id="net.external.connectivity",
            domain="network",
            observation="No external connectivity",
            status=CheckStatus.FAIL,
        ),
    ]

    report = evaluate_network_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "NET_PHYSICAL_DISCONNECTED"
    assert report.primary_finding.confidence >= 0.50


def test_evaluate_dhcp_apipa_failure() -> None:
    """Verify that detecting an APIPA address diagnoses NET_DHCP_LEASE_FAILED."""
    evidence = [
        DiagnosticResult(
            check_id="net.adapter.summary",
            domain="network",
            observation="1 operational adapter",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.ip.wi-fi.apipa",
            domain="network",
            observation="APIPA address 169.254.10.20 detected",
            status=CheckStatus.WARNING,
        ),
        DiagnosticResult(
            check_id="net.gateway.presence",
            domain="network",
            observation="No default gateway route",
            status=CheckStatus.FAIL,
        ),
    ]

    report = evaluate_network_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "NET_DHCP_LEASE_FAILED"
    assert report.primary_finding.confidence >= 0.50
    assert "APIPA" in report.primary_finding.supporting_evidence[0]


def test_evaluate_dns_resolution_failure() -> None:
    """Verify that failed DNS while IP & Gateway work diagnoses NET_DNS_RESOLUTION_FAILED."""
    evidence = [
        DiagnosticResult(
            check_id="net.adapter.summary",
            domain="network",
            observation="Adapter operational",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.ip.status",
            domain="network",
            observation="Valid IP assigned",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.gateway.reachability",
            domain="network",
            observation="Default gateway reachable",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.dns.resolution",
            domain="network",
            observation="DNS resolution failed completely",
            status=CheckStatus.FAIL,
        ),
    ]

    report = evaluate_network_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "NET_DNS_RESOLUTION_FAILED"
    assert report.primary_finding.confidence >= 0.50
    assert "DNS" in report.primary_finding.title


def test_evaluate_captive_portal() -> None:
    """Verify that TCP connectivity pass + HTTP fail diagnoses NET_CAPTIVE_PORTAL_OR_PROXY."""
    evidence = [
        DiagnosticResult(
            check_id="net.adapter.summary",
            domain="network",
            observation="Adapter operational",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.ip.status",
            domain="network",
            observation="Valid IP assigned",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.gateway.reachability",
            domain="network",
            observation="Gateway reachable",
            status=CheckStatus.PASS,
        ),
        DiagnosticResult(
            check_id="net.external.connectivity",
            domain="network",
            observation="TCP works, but HTTP NCSI probe failed",
            status=CheckStatus.WARNING,
        ),
    ]

    report = evaluate_network_hypotheses(evidence)
    assert report.is_conclusive is True
    assert report.primary_finding is not None
    assert report.primary_finding.cause_id == "NET_CAPTIVE_PORTAL_OR_PROXY"
    assert report.primary_finding.confidence >= 0.50


def test_diagnosis_report_json_serialization() -> None:
    """Ensure DiagnosisReport serializes and deserializes cleanly."""
    evidence = [
        DiagnosticResult(
            check_id="net.adapter.summary",
            domain="network",
            observation="No operational adapters",
            status=CheckStatus.FAIL,
        ),
    ]
    report = evaluate_network_hypotheses(evidence)
    json_str = report.model_dump_json()
    reconstructed = DiagnosisReport.model_validate_json(json_str)

    assert reconstructed.domain == report.domain
    assert reconstructed.is_conclusive == report.is_conclusive
    assert reconstructed.evidence_count == report.evidence_count
