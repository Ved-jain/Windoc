"""Deterministic evidence-driven hypothesis engine for WinDoc."""

from enum import Enum
from typing import Dict, List, Optional
from pydantic import BaseModel, Field

from windoc.core.models import CheckStatus, DiagnosticResult, Severity


class HypothesisStatus(str, Enum):
    """Categorical assessment of a hypothesis based on accumulated evidence."""
    CONFIRMED = "CONFIRMED"        # Substantial evidence; confidence >= 80%
    LIKELY = "LIKELY"              # Leading explanation; confidence >= 50%
    POSSIBLE = "POSSIBLE"          # Incomplete evidence; confidence >= 25%
    RULED_OUT = "RULED_OUT"        # Strong contradicting evidence; confidence <= 10%
    INCONCLUSIVE = "INCONCLUSIVE"  # Evidence conflicting or insufficient


class DiagnosisFinding(BaseModel):
    """A single evaluated hypothesis explaining the observed state."""
    cause_id: str = Field(..., description="Unique machine-readable cause identifier")
    title: str = Field(..., description="Human-readable title of the root cause")
    description: str = Field(..., description="Explanation of what this root cause means")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Normalized confidence score (0.0 to 1.0)")
    status: HypothesisStatus = Field(..., description="Categorical evaluation status")
    supporting_evidence: List[str] = Field(default_factory=list, description="Observations that support this cause")
    refuting_evidence: List[str] = Field(default_factory=list, description="Observations that contradict this cause")
    recommended_action: str = Field(..., description="Next diagnostic test or proposed repair direction")


class DiagnosisReport(BaseModel):
    """Comprehensive diagnostic verdict produced by the hypothesis engine."""
    domain: str = Field(..., description="Problem domain diagnosed")
    primary_finding: Optional[DiagnosisFinding] = Field(default=None, description="Leading root cause if conclusive")
    all_findings: List[DiagnosisFinding] = Field(default_factory=list, description="All evaluated candidate hypotheses")
    evidence_count: int = Field(default=0, description="Total diagnostic checks analyzed")
    is_conclusive: bool = Field(default=False, description="Whether a decisive diagnosis was established")
    summary: str = Field(..., description="High-level conclusion for the user")


def evaluate_network_hypotheses(evidence: List[DiagnosticResult]) -> DiagnosisReport:
    """Evaluate network domain evidence using transparent, deterministic scoring rules.
    
    Interview Defense:
    Each hypothesis maintains an explicit score. Each diagnostic check provides positive
    evidence weight (+support) or negative refutation weight (-refute).
    The scores are clamped to [0, 100] and normalized to a [0.0, 1.0] confidence score.
    """
    evidence_by_id: Dict[str, DiagnosticResult] = {r.check_id: r for r in evidence}
    
    # 1. Candidate Hypothesis Initial Definitions
    candidates = [
        {
            "cause_id": "NET_ALL_HEALTHY",
            "title": "All Network Subsystems Operational",
            "description": "Network adapters, IP configuration, gateway, DNS, and external reachability are functional.",
            "recommended_action": "No repair needed; network is fully operational.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_PHYSICAL_DISCONNECTED",
            "title": "Physical Media Disconnected or Disabled",
            "description": "No active operational network adapters detected, or Wi-Fi radio is off / cable unplugged.",
            "recommended_action": "Reconnect the Ethernet cable, toggle Wi-Fi radio on, or enable disabled adapter.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_DHCP_LEASE_FAILED",
            "title": "DHCP Address Assignment Failed (APIPA Active)",
            "description": "The system received no IP from the local router/DHCP server and defaulted to an auto-assigned 169.254.x.x address.",
            "recommended_action": "Release and renew DHCP lease or verify DHCP server / router status.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_GATEWAY_UNREACHABLE",
            "title": "Default Gateway Unreachable",
            "description": "The local router or default gateway route is missing or not responding to traffic.",
            "recommended_action": "Restart the local router or verify subnet IP and default route settings.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_DNS_RESOLUTION_FAILED",
            "title": "DNS Server Unresponsive or Misconfigured",
            "description": "Network routing is functional, but the configured DNS servers cannot resolve domain names.",
            "recommended_action": "Flush local DNS cache or switch DNS to a public resolver (e.g. 1.1.1.1 or 8.8.8.8).",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
        {
            "cause_id": "NET_CAPTIVE_PORTAL_OR_PROXY",
            "title": "Captive Portal or Proxy Interception",
            "description": "Direct TCP traffic is routed, but HTTP web probes are intercepted or blocked (common on public Wi-Fi).",
            "recommended_action": "Open a web browser to complete public network login / sign-in portal.",
            "score": 0.0,
            "supports": [],
            "refutes": [],
        },
    ]

    c_map = {c["cause_id"]: c for c in candidates}

    # 2. Rule-Based Evidence Evaluation
    # Check 1: Adapter summary & active count
    adap_summary = evidence_by_id.get("net.adapter.summary")
    if adap_summary:
        if adap_summary.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 20
            c_map["NET_ALL_HEALTHY"]["supports"].append("Network adapters detected and operational.")
            c_map["NET_PHYSICAL_DISCONNECTED"]["score"] -= 50
            c_map["NET_PHYSICAL_DISCONNECTED"]["refutes"].append("Operational network adapter is active.")
        else:
            c_map["NET_PHYSICAL_DISCONNECTED"]["score"] += 60
            c_map["NET_PHYSICAL_DISCONNECTED"]["supports"].append("No operational network adapters detected.")
            c_map["NET_ALL_HEALTHY"]["score"] -= 80
            c_map["NET_ALL_HEALTHY"]["refutes"].append("No operational network adapters.")

    # Check 2: IP Configuration & APIPA
    ip_status = evidence_by_id.get("net.ip.status")
    has_valid_ip = ip_status is not None and ip_status.status == CheckStatus.PASS
    has_apipa = any("apipa" in k and r.status == CheckStatus.WARNING for k, r in evidence_by_id.items())
    
    if has_apipa and not has_valid_ip:
        c_map["NET_DHCP_LEASE_FAILED"]["score"] += 90
        c_map["NET_DHCP_LEASE_FAILED"]["supports"].append("Interface has an APIPA (169.254.x.x) address and no valid IP exists.")
        c_map["NET_ALL_HEALTHY"]["score"] -= 80
        c_map["NET_ALL_HEALTHY"]["refutes"].append("APIPA address indicates DHCP assignment failure.")
        c_map["NET_GATEWAY_UNREACHABLE"]["score"] -= 40
        c_map["NET_GATEWAY_UNREACHABLE"]["refutes"].append("Missing gateway is a downstream symptom of DHCP failure.")
    elif has_valid_ip:
        c_map["NET_ALL_HEALTHY"]["score"] += 25
        c_map["NET_ALL_HEALTHY"]["supports"].append("Valid IPv4 address assigned to active interface.")
        c_map["NET_DHCP_LEASE_FAILED"]["score"] -= 70
        c_map["NET_DHCP_LEASE_FAILED"]["refutes"].append("Valid routable IPv4 address is present on active interface.")

    # Check 3: Default Gateway Reachability
    gw_pres = evidence_by_id.get("net.gateway.presence")
    gw_reach = evidence_by_id.get("net.gateway.reachability")

    if gw_pres and gw_pres.status == CheckStatus.FAIL:
        if not has_apipa:
            c_map["NET_GATEWAY_UNREACHABLE"]["score"] += 80
            c_map["NET_GATEWAY_UNREACHABLE"]["supports"].append("No active default gateway route configured.")
        c_map["NET_ALL_HEALTHY"]["score"] -= 80
        c_map["NET_ALL_HEALTHY"]["refutes"].append("Default gateway is absent.")
    elif gw_reach:
        if gw_reach.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 20
            c_map["NET_ALL_HEALTHY"]["supports"].append("Default gateway responded to reachability probe.")
            c_map["NET_GATEWAY_UNREACHABLE"]["score"] -= 70
            c_map["NET_GATEWAY_UNREACHABLE"]["refutes"].append("Default gateway is reachable.")
        elif gw_reach.status == CheckStatus.WARNING:
            if not has_apipa:
                c_map["NET_GATEWAY_UNREACHABLE"]["score"] += 50
                c_map["NET_GATEWAY_UNREACHABLE"]["supports"].append("Default gateway failed ICMP probe.")

    # Check 4: DNS Resolution
    dns_res = evidence_by_id.get("net.dns.resolution")
    if dns_res:
        if dns_res.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 20
            c_map["NET_ALL_HEALTHY"]["supports"].append("DNS resolution succeeded for all test domains.")
            c_map["NET_DNS_RESOLUTION_FAILED"]["score"] -= 80
            c_map["NET_DNS_RESOLUTION_FAILED"]["refutes"].append("DNS resolution is functional.")
        elif dns_res.status in (CheckStatus.FAIL, CheckStatus.WARNING):
            c_map["NET_DNS_RESOLUTION_FAILED"]["score"] += 65
            c_map["NET_DNS_RESOLUTION_FAILED"]["supports"].append("Domain name resolution failed or timed out.")
            c_map["NET_ALL_HEALTHY"]["score"] -= 70
            c_map["NET_ALL_HEALTHY"]["refutes"].append("DNS resolution failed.")

    # Check 5: External Reachability (Dual Pathway)
    ext_conn = evidence_by_id.get("net.external.connectivity")
    if ext_conn:
        if ext_conn.status == CheckStatus.PASS:
            c_map["NET_ALL_HEALTHY"]["score"] += 50
            c_map["NET_ALL_HEALTHY"]["supports"].append("External internet connectivity confirmed via TCP and HTTP.")
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["score"] -= 60
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["refutes"].append("Direct internet probes succeeded.")
            c_map["NET_DHCP_LEASE_FAILED"]["score"] -= 70
            c_map["NET_DHCP_LEASE_FAILED"]["refutes"].append("Active interface has working external connectivity.")
        elif ext_conn.status == CheckStatus.WARNING:
            # TCP works, but HTTP NCSI failed -> Captive portal signature!
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["score"] += 75
            c_map["NET_CAPTIVE_PORTAL_OR_PROXY"]["supports"].append("TCP port 53 succeeded but HTTP probe failed (captive portal signature).")
            c_map["NET_ALL_HEALTHY"]["score"] -= 50
        elif ext_conn.status == CheckStatus.FAIL:
            c_map["NET_ALL_HEALTHY"]["score"] -= 80
            c_map["NET_ALL_HEALTHY"]["refutes"].append("External internet connectivity is unavailable.")

    # 3. Score Normalization and Status Determination
    findings: List[DiagnosisFinding] = []
    for c in candidates:
        raw_score = max(0.0, min(100.0, c["score"]))
        confidence = round(raw_score / 100.0, 2)

        if confidence >= 0.80:
            status = HypothesisStatus.CONFIRMED
        elif confidence >= 0.50:
            status = HypothesisStatus.LIKELY
        elif confidence >= 0.25:
            status = HypothesisStatus.POSSIBLE
        elif confidence <= 0.10:
            status = HypothesisStatus.RULED_OUT
        else:
            status = HypothesisStatus.INCONCLUSIVE

        findings.append(
            DiagnosisFinding(
                cause_id=c["cause_id"],
                title=c["title"],
                description=c["description"],
                confidence=confidence,
                status=status,
                supporting_evidence=c["supports"],
                refuting_evidence=c["refutes"],
                recommended_action=c["recommended_action"],
            )
        )

    # Sort findings by confidence descending
    findings.sort(key=lambda f: f.confidence, reverse=True)
    primary = findings[0] if findings and findings[0].confidence >= 0.50 else None

    # High-level conclusion summary
    if primary and primary.status == HypothesisStatus.CONFIRMED:
        summary = f"Confirmed root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    elif primary and primary.status == HypothesisStatus.LIKELY:
        summary = f"Probable root cause: {primary.title} (Confidence: {int(primary.confidence * 100)}%)."
    else:
        summary = "Diagnostic evidence is inconclusive; manual investigation required."

    return DiagnosisReport(
        domain="network",
        primary_finding=primary,
        all_findings=findings,
        evidence_count=len(evidence),
        is_conclusive=primary is not None and primary.status in (HypothesisStatus.CONFIRMED, HypothesisStatus.LIKELY),
        summary=summary,
    )
