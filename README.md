# WinDoc (Windows Doctor)

> **Evidence-Driven Windows Diagnostics and Repair CLI**  
> *"Diagnostics and repairs for everyday people — no jargon, no hassle."*

[![Tests](https://img.shields.io/badge/tests-116%20passed-brightgreen.svg)]()
[![Platform](https://img.shields.io/badge/platform-Windows%2010%20%7C%2011-blue.svg)]()
[![Python](https://img.shields.io/badge/python-3.10%20%7C%203.11%20%7C%203.12%20%7C%203.13-blue.svg)]()
[![Version](https://img.shields.io/badge/version-1.0.0%20(Completed)-brightgreen.svg)]()
[![License](https://img.shields.io/badge/license-MIT-green.svg)]()

WinDoc is an open-source, local, terminal-based diagnostic and repair tool designed for Windows. Unlike generic troubleshooting utilities that execute destructive, one-size-fits-all scripts, WinDoc operates like a medical doctor: it collects verifiable evidence about your system's actual state, evaluates competing hypotheses through deterministic inference, runs targeted tests, and offers safe, allowlisted repairs only when justified by diagnostic proof.

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
| **Milestone 11** | Zero-Hassle UX & Production Release | Unified `windoc scan` & `windoc fix`, global `windoc activate` launcher, comprehensive docs, and 116 passing tests. | 116 Tests | ✅ Complete |

---

## ⚡ Zero-Hassle User Experience

Everyday users don't need to memorize complex CLI arguments or multi-step repair commands. WinDoc is designed around two simple workflows:

```powershell
# 1. Scan your entire PC in 5 seconds across all 6 subsystems
windoc scan

# 2. Automatically find problems, apply verified fixes, and re-test
windoc fix

# (Optional) One-touch unattended auto-fix
windoc fix --yes
```

> 📖 **Full Command Reference:** For the complete list of all 22+ diagnostic cause codes, 10 controlled repairs, and technical details, see the **[Commands & Codes Guide (COMMANDS.md)](COMMANDS.md)**.

---

## 🔍 Supported Diagnostic Domains

WinDoc actively investigates **6 core Windows subsystems**:

| Subsystem | What WinDoc Inspects | Telemetry Sources |
| :--- | :--- | :--- |
| **🌐 Network** | Wi-Fi/Ethernet adapters, IPv4/APIPA configuration, Default Gateway reachability, DNS resolver, captive portals. | `Get-NetAdapter`, `Get-NetIPConfiguration`, ICMP ping, socket resolution, HTTP NCSI probes. |
| **📶 Bluetooth** | Radio controller hardware state, `bthserv` background service, paired accessories responsiveness. | `Get-Service`, `Get-PnpDevice (Bluetooth)`, Device Manager error codes. |
| **🔌 Hardware & Drivers** | Plug and Play (PnP) devices, missing drivers (Code 28), crashed devices (Code 43), disabled devices (Code 22), reboot required (Code 14), display and USB controllers. | `Get-PnpDevice`, Device Manager configuration manager status. |
| **🔄 Windows Update** | Core update services (`wuauserv`, `bits`, `cryptsvc`), pending restart registry keys, hotfix history, `SoftwareDistribution` cache. | `Get-Service`, Registry (`RebootRequired`), `Get-HotFix`, cache integrity checks. |
| **🛡️ System Integrity** | Windows Component Store (WinSxS), core OS services (`RpcSs`, `DcomLaunch`, `EventLog`, `Winmgmt`), recent BSOD bugchecks, Safe Mode boot state. | `DISM CheckHealth`, CBS servicing registry, `C:\Windows\Minidump`, `Win32_ComputerSystem`. |
| **⚡ Performance & Resources** | Multi-core CPU utilization, physical RAM pressure and starvation, drive `C:` storage capacity, continuous operating uptime. | `Win32_Processor`, `Win32_OperatingSystem`, `Get-Volume C:`. |

---

## 🛡️ Core Engineering & Security Principles

WinDoc was built with strict software engineering discipline:

1. **Evidence-Driven, Not Script-Happy:** Repairs are never suggested without positive diagnostic evidence.
2. **Deterministic & Explainable:** Every diagnosis is calculated using weighted, rule-based inference with supporting and refuting telemetry—no black-box AI hallucinations.
3. **Quarantined Least Privilege:** Diagnostic scans run entirely in unprivileged user mode. Elevation is only requested when an approved repair strictly requires administrative access.
4. **Independent Post-Repair Verification:** If a Windows command returns exit code 0 but the problem persists, WinDoc marks the repair as `VERIFICATION_FAILED` so users are never misled.
5. **No Blind Resets:** Destructive actions (registry wipers, network stack wiping, driver purges) are prohibited. All repairs are non-destructive and scoped.
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

WinDoc has a comprehensive test suite of **116 unit tests** covering all 6 domains, runner security, and CLI workflows:

```powershell
# Run the complete test suite
.\.venv\Scripts\pytest -v
```

```
============================= 116 passed in 1.00s =============================
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
│   │   ├── network/               # Domain A: Network adapters, IP, DNS, Gateway
│   │   ├── bluetooth/             # Domain B: Bluetooth radio, services, devices
│   │   ├── drivers/               # Domain C: PnP devices, Code 28/43/22, GPU/USB
│   │   ├── update/                # Domain D: Windows Update services, reboot pending
│   │   ├── system/                # Domain E: Component store, core services, crash dumps
│   │   └── performance/           # Domain F: CPU load, RAM pressure, disk space, uptime
│   └── repairs/
│       ├── models.py              # RepairAction, RiskLevel, RepairExecutionResult
│       ├── registry.py            # Controlled repair registry & verification callbacks
│       └── executor.py            # Consent handling, elevation check, pre/post verification
├── tests/                         # 116 automated pytest unit tests
├── COMMANDS.md                    # Complete user & developer command and code reference
├── ARCHITECTURE.md                # In-depth architectural design specification
└── pyproject.toml                 # Packaging and dependency configuration
```

---

## 📄 License

This project is open-source and available under the [MIT License](LICENSE).
