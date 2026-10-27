# WinDoc (Windows Doctor)

> **Evidence-Driven Windows Diagnostics and Repair CLI**  
> *"Diagnostics and repairs for everyday people — no jargon, no hassle."*

[![Tests](https://img.shields.io/badge/tests-128%20passed-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)]()
[![Version](https://img.shields.io/badge/version-1.0.0%20(Completed)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

WinDoc is an open-source, local, terminal-based diagnostic and repair tool designed for Windows. Unlike generic troubleshooting utilities that execute destructive, one-size-fits-all scripts, WinDoc operates like a medical doctor: it collects verifiable evidence about your system's actual state, evaluates competing hypotheses through deterministic inference, runs targeted tests, and offers safe, allowlisted repairs with independent post-fix verification.

---

## 🖥️ Live Terminal Demo

Here is how WinDoc looks and works in practice.

### Demo 1: `windoc scan` with Instant One-Key Repair Prompt
Run `windoc scan` to inspect your PC across 6 subsystems in seconds. If an issue is discovered, WinDoc diagnoses the root cause and asks if you'd like to fix it on the spot:

```text
PS C:\> windoc scan

Starting comprehensive diagnostic scan...

┌────────────────────────────────────── Network Diagnostics ──────────────────────────────────────┐
│ Status │ Check ID                   │ Observation                                 │ Source      │
├────────┼────────────────────────────┼─────────────────────────────────────────────┼─────────────┤
│  PASS  │ net.adapter.wi-fi.state    │ Adapter 'Wi-Fi' is Up (Operational)         │ Get-NetAdap │
│  PASS  │ net.ip.status              │ Valid IPv4 address configured (192.168.1.45)│ Get-NetIPAd │
│  PASS  │ net.gateway.ping           │ Default gateway 192.168.1.1 is reachable    │ ping        │
│  FAIL  │ net.dns.resolution         │ DNS resolution failed for 3/3 test domains  │ socket      │
│  FAIL  │ net.connectivity.probe     │ External internet connectivity unreachable  │ probe       │
└────────┴────────────────────────────┴─────────────────────────────────────────────┴─────────────┘
Summary: 3 Passed | 0 Warnings | 2 Failed | 0 Other

┌─ Root Cause Diagnosis ──────────────────────────────────────────────────────────────────────────┐
│ [!] Root Cause: DNS Resolution Failure (Confidence: 90%)                                        │
│ Status: CONFIRMED                                                                               │
│                                                                                                 │
│ All configured DNS servers failed to resolve public internet addresses. Stale cache detected.  │
│                                                                                                 │
│ Supporting Evidence:                                                                            │
│  - DNS resolution failed completely for all 3 test domains.                                     │
│  - Gateway is reachable, but internet endpoints cannot be mapped.                               │
│                                                                                                 │
│ Recommended Next Step: Flush local DNS cache and renew upstream resolvers.                      │
│                                                                                                 │
│ Ready to Fix: Simply run windoc fix to automatically apply and verify this fix.                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

WinDoc detected issue(s). Would you like to automatically apply verified fixes now? [Y/n]: Y

WinDoc found 1 issue(s) that can be fixed:

┌─ Issue: DNS Resolution Failure ─────────────────────────────────────────────────────────────────┐
│ Problem Detected: DNS Resolution Failure                                                        │
│ Recommended Fix: Flush DNS Resolver Cache                                                       │
│ Subsystem: Network | Procedure ID: net.flush_dns | Risk: LOW                                    │
│ Expected Effect: Clears DNS cache; next DNS query will fetch directly from upstream servers.    │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

Apply fix for 'DNS Resolution Failure' now? [Y/n]: Y

┌─ Repair Verification: SUCCESS ──────────────────────────────────────────────────────────────────┐
│ [OK] Fixed and Verified!                                                                        │
│                                                                                                 │
│ DNS resolution verified successfully after cache flush. (3/3 test domains resolved).            │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Demo 2: Zero-Hassle Auto-Fix (`windoc fix`)
No procedure IDs to copy-paste or remember. Just run `windoc fix` (or target a single domain like `windoc fix network`):

```text
PS C:\> windoc fix

┌─ WinDoc Auto-Fix ───────────────────────────────────────────────────────────────────────────────┐
│ Scanning system to detect any issues and automatically apply verified fixes...                  │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

WinDoc found 1 issue(s) that can be fixed:

┌─ Issue: Windows Update Services Disabled ───────────────────────────────────────────────────────┐
│ Problem Detected: Windows Update Services Disabled                                              │
│ Recommended Fix: Reset and Enable Windows Update Services                                       │
│ Subsystem: Windows Update | Procedure ID: upd.reset_services | Risk: LOW                         │
│ Expected Effect: Enables Windows Update and cryptographic services to resume downloading updates│
└─────────────────────────────────────────────────────────────────────────────────────────────────┘

Apply fix for 'Windows Update Services Disabled' now? [Y/n]: Y

┌─ Repair Verification: SUCCESS ──────────────────────────────────────────────────────────────────┐
│ [OK] Fixed and Verified!                                                                        │
│                                                                                                 │
│ Windows Update services (wuauserv, bits, cryptsvc) verified active and running.                 │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## ⚡ Everyday Workflows

Everyday users don't need to memorize complex CLI arguments or arcane procedure IDs:

```powershell
# 1. Scan your entire PC in seconds across all 6 subsystems
windoc scan

# 2. Automatically find problems, apply verified fixes, and re-test
windoc fix

# 3. Fix a specific subsystem without waiting for the whole PC to scan
windoc fix network       # or: windoc fix net
windoc fix bluetooth     # or: windoc fix bth
windoc fix drivers       # or: windoc fix drv
windoc fix update        # or: windoc fix upd
windoc fix system        # or: windoc fix sys
windoc fix performance   # or: windoc fix perf

# 4. Diagnose and fix in one command
windoc diagnose network --fix
windoc diagnose performance --fix

# 5. One-touch unattended auto-fix (skip confirmation prompts)
windoc fix --yes
```

> 📖 **Full Command Reference:** For the complete list of all 25+ diagnostic cause codes, 20 controlled repairs, and technical details, see the **[Commands & Codes Guide (COMMANDS.md)](COMMANDS.md)**.

---

## 🔍 Supported Diagnostic Domains

WinDoc actively investigates and fixes **6 core Windows subsystems**:

| Subsystem | What WinDoc Inspects | Supported Controlled Repairs (100% Coverage) |
| :--- | :--- | :--- |
| **🌐 Network** | Wi-Fi/Ethernet adapters, IPv4/APIPA configuration, Default Gateway reachability, DNS resolver, proxy/captive portals. | • Flush DNS Resolver Cache (`net.flush_dns`)<br>• Renew DHCP Lease (`net.renew_dhcp`)<br>• Restart Adapter (`net.restart_adapter`)<br>• Reset TCP/IP Stack & Winsock (`net.reset_tcpip`)<br>• Reset WinHTTP/User Proxy (`net.reset_proxy`) |
| **📶 Bluetooth** | Radio controller hardware state, `bthserv` service, driver errors, peripheral protocol stack. | • Restart Bluetooth Service (`bth.restart_service`)<br>• Enable Bluetooth Controller (`bth.enable_adapter`)<br>• Rescan Bluetooth Hardware (`bth.rescan_hardware`)<br>• Power-Cycle Bluetooth Device (`bth.restart_device`)<br>• Reset Bluetooth Stack (`bth.reset_stack`) |
| **🔌 Hardware & Drivers** | Plug and Play (PnP) devices, missing drivers (Code 28), crashed devices (Code 43), disabled devices (Code 22), reboot required (Code 14). | • Scan Missing Drivers & Windows Update (`drv.scan_missing_drivers`)<br>• Rescan PnP Hardware Tree (`drv.rescan_devices`)<br>• Re-enable Disabled Devices (`drv.enable_device`)<br>• Schedule Driver Finalization Restart (`drv.schedule_restart`) |
| **🔄 Windows Update** | Core update services (`wuauserv`, `bits`, `cryptsvc`), pending restart registry keys, hotfix history, `SoftwareDistribution` cache. | • Reset & Enable Update Services (`upd.reset_services`)<br>• Clear Corrupt Download Cache (`upd.reset_cache`)<br>• Schedule Update Installation Restart (`upd.schedule_restart`) |
| **🛡️ System Integrity** | Windows Component Store (WinSxS), core OS services (`RpcSs`, `DcomLaunch`, `EventLog`, `Winmgmt`), recent BSOD bugchecks, Safe Mode boot state. | • Repair Component Store via DISM (`sys.repair_component_store`)<br>• Restore Core OS Services (`sys.restart_services`)<br>• System File Checker Scan (`sys.sfc_scan`)<br>• Exit Safe Mode & Restore Normal Boot (`sys.exit_safe_mode`) |
| **⚡ Performance & Resources** | Multi-core CPU utilization, physical RAM pressure (>92%), drive `C:` storage capacity, continuous operating uptime. | • Clean Temp Files Cache (`perf.clean_temp_files`)<br>• Empty Recycle Bin (`perf.empty_recycle_bin`)<br>• Purge Stale Update Cache (`perf.clean_update_cache`)<br>• Terminate Runaway RAM Consumers (`perf.free_memory`)<br>• Terminate CPU-Saturating Workers (`perf.free_cpu`)<br>• Graceful Uptime Reboot (`perf.schedule_restart`) |

---

## 🏆 Project Milestones & Progress (11/11 Completed)

WinDoc was built systematically across **11 development milestones**, progressing from foundational architecture to a fully unified, zero-hassle multi-domain diagnostic and repair suite:

| Milestone | Subsystem / Focus | Key Engineering Deliverables | Test Coverage | Status |
| :--- | :--- | :--- | :---: | :---: |
| **Milestone 1** | Foundation & CLI Architecture | Typer CLI skeleton, Rich color formatting, `--version`, `info`, `list-domains`. | Unit Tests | ✅ Complete |
| **Milestone 2** | Diagnostic Models & Safe Runner | Immutable Pydantic models (`DiagnosticResult`, `CheckStatus`), `shell=False` execution, strict timeouts, structured JSON parser. | Unit Tests | ✅ Complete |
| **Milestone 3** | Network Diagnostics Domain | `Get-NetAdapter`, APIPA address detection, Default Gateway ICMP probes, DNS resolution tests, captive portal HTTP NCSI probes. | Unit Tests | ✅ Complete |
| **Milestone 4** | Deterministic Hypothesis Engine | Weighted scoring engine, confidence ratings, primary root cause isolation (`NET_DNS_RESOLUTION_FAILED`, etc.). | Unit Tests | ✅ Complete |
| **Milestone 5** | Controlled Repair Registry | Allowlisted repairs (`net.flush_dns`, `net.renew_dhcp`), user consent gates, elevation checks, independent post-repair verification. | Unit Tests | ✅ Complete |
| **Milestone 6** | Bluetooth Diagnostics & Repairs | Radio hardware status, `bthserv` service monitoring, paired devices, service restart & adapter re-enable repairs. | Unit Tests | ✅ Complete |
| **Milestone 7** | Hardware & Drivers Domain | Plug and Play (PnP) queries, Device Manager error codes (Code 28, 43, 22, 14), display and USB controllers, driver re-enable repair. | Unit Tests | ✅ Complete |
| **Milestone 8** | Windows Update Subsystem | Update background services (`wuauserv`, `bits`, `cryptsvc`), pending reboot registry flags, hotfix verification, service reset repair. | Unit Tests | ✅ Complete |
| **Milestone 9** | System Integrity & Core Services | Windows Component Store (`DISM /CheckHealth`), core subsystem services (`RpcSs`, `Winmgmt`, `EventLog`), BSOD crash dump detection. | Unit Tests | ✅ Complete |
| **Milestone 10** | Performance & Resource Diagnostics | Multi-core CPU load, physical RAM pressure (>92%), system drive C: storage capacity, uptime monitoring, and disk cleanup repairs. | Unit Tests | ✅ Complete |
| **Milestone 11** | Zero-Hassle UX & 100% Repair Coverage | Unified `windoc scan` & `windoc fix [domain]`, `--fix` on all diagnose subcommands, in-line auto-fix prompts, global `windoc activate` launcher, and 128 passing tests. | 128 Tests | ✅ Complete |

---

## 🛡️ Core Engineering & Security Principles

WinDoc was built with strict software engineering discipline:

1. **Evidence-Driven, Not Script-Happy:** Repairs are never suggested without positive diagnostic evidence.
2. **Deterministic & Explainable:** Every diagnosis is calculated using weighted, rule-based inference with supporting and refuting telemetry—no black-box AI hallucinations.
3. **Quarantined Least Privilege:** Diagnostic scans run entirely in unprivileged user mode. Elevation is only requested when an approved repair strictly requires administrative access.
4. **Independent Post-Repair Verification:** If a Windows command returns exit code 0 but the problem persists, WinDoc marks the repair as `VERIFICATION_FAILED` so users are never misled.
5. **No Blind Resets:** Destructive actions (registry wipers, blind network stack purges, driver wipers) are prohibited. All repairs are non-destructive, targeted, and verified.
6. **Subprocess Safety:** External commands execute with `shell=False`, strict timeouts, and safe UTF-8 decoding fallbacks to eliminate shell injection vulnerabilities.

---

## 🚀 Installation & Global Activation

### Prerequisites
- Windows 10 or Windows 11 (64-bit)
- Python 3.10+
- PowerShell 5.1+

### Quick Install
Double-click `install.cmd` in the repository root or run:
```powershell
.\install.cmd
```

### Global Activation (`windoc activate`)
Run once after installing:
```powershell
windoc activate
```
This registers `windoc` globally in your user PATH and `~/.local/bin`. You can now run `windoc` from **any terminal, any directory**, with **no virtual environment activation required**!

---

## 🧪 Testing & Quality Assurance

WinDoc has a comprehensive test suite of **128 unit tests** covering all 6 domains, runner security, hypothesis inference, 100% repair coverage verification, and CLI workflows:

```powershell
# Run the complete test suite
.\.venv\Scripts\pytest -v
```

```
============================= 128 passed in 1.11s =============================
```

---

## 📁 Repository Architecture

```
Windoc/
├── src/windoc/
│   ├── cli.py                     # Typer CLI application, commands, Rich tables
│   ├── core/
│   │   ├── engine.py              # Deterministic hypothesis evaluation engine
│   │   ├── models.py              # Pydantic models (DiagnosticResult, CheckStatus, etc.)
│   │   └── runner.py              # Safe subprocess & PowerShell runner (shell=False)
│   ├── domains/
│   │   ├── network/               # Domain A: Network adapters, IP, DNS, Gateway, Proxy
│   │   ├── bluetooth/             # Domain B: Bluetooth radio, services, devices, stack
│   │   ├── drivers/               # Domain C: PnP devices, Code 28/43/22/14, GPU/USB
│   │   ├── update/                # Domain D: Windows Update services, cache, reboot pending
│   │   ├── system/                # Domain E: Component store, core services, crash dumps, safe mode
│   │   └── performance/           # Domain F: CPU load, RAM pressure, disk space, uptime
│   └── repairs/
│       ├── models.py              # RepairAction, RiskLevel, RepairExecutionResult
│       ├── registry.py            # Controlled repair registry & verification callbacks (100% coverage)
│       └── executor.py            # Consent handling, elevation check, pre/post verification
├── tests/                         # 128 automated pytest unit tests
├── COMMANDS.md                    # Complete user & developer command and code reference
├── ARCHITECTURE.md                # In-depth architectural design specification
└── pyproject.toml                 # Packaging and dependency configuration
```

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
