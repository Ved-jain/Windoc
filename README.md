# WinDoc (Windows Doctor)

> **Evidence-Driven Windows Diagnostics and Repair CLI**

WinDoc is an open-source, local, terminal-based diagnostic and repair tool designed for Windows. Unlike generic troubleshooting utilities that execute one-size-fits-all scripts, WinDoc operates like a medical doctor: it collects verifiable evidence about your system's actual state, evaluates competing hypotheses, runs discriminative tests, and offers targeted, safe repairs only when justified by evidence.

---

## Key Principles

- **Evidence-Driven, Not Script-Happy:** Repairs are only suggested when specific conditions are confirmed by diagnostic evidence.
- **Deterministic & Explainable:** Every diagnosis is arrived at through transparent, rule-based reasoning, allowing every step to be inspected and defended.
- **Least Privilege:** Diagnostic checks are read-only and run without administrative privileges wherever possible. Administrative elevation is quarantined to strictly protected operations.
- **Safe, Verified Repairs:** No blind registry wiping or destructive resets. Every repair checks preconditions, captures pre-repair state, requires explicit user consent, and verifies whether the original symptom was actually resolved.
- **100% Offline Core:** Works locally without requiring internet access or cloud/AI dependencies (except for inherently network-dependent checks like DNS/Gateway verification).

---

## Project Status

- **Version:** `0.1.0` (Milestone 1 — Foundation & CLI Architecture)
- **Target OS:** Windows 10 & Windows 11 (64-bit)

---

## Installation & Setup

### Prerequisites
- Windows 10 / 11
- Python 3.10 or higher
- PowerShell 5.1+

### Quick Install (One-Click)
Double-click `install.cmd` in the project root, or run:
```powershell
.\install.cmd
```
This automatically initializes the virtual environment, installs all dependencies, and registers `windoc` into your Windows user PATH.

### Global Activation (`windoc activate`)
Once installed, run:
```powershell
windoc activate
```
This registers global launchers in `~/.local/bin` and Windows environment PATH. You can now run `windoc` directly from **any terminal, any directory**, with **no virtual environment activation required**!

---

## Everyday Usage (Zero Hassle)

Regular users only need two commands:

```powershell
# 1. Scan your PC to see what is going on
windoc scan

# 2. Automatically find problems, apply verified fixes, and re-test
windoc fix
```

For zero-prompt auto-fixing, run:
```powershell
windoc fix --yes
```

> 📖 **Full Command Reference:** For a complete list of all diagnostic cause codes, repair IDs, and advanced developer commands, see the **[Commands & Codes Guide (COMMANDS.md)](COMMANDS.md)**.

---

## Architecture Overview

WinDoc is organized into modular layers:

```
CLI Layer (Typer + Rich)
       │
       ▼
Diagnostic Engine (Hypothesis Evaluator)
       │
  ┌────┴────────────────┐
  ▼                     ▼
Domain Modules     Hypothesis Registry
(Network, etc.)    (Deterministic Rules)
  │
  ▼
Safe Command Runner (subprocess with timeout & JSON parsing)
```

For more details, see [ARCHITECTURE.md](ARCHITECTURE.md).

---

## License

This project is licensed under the MIT License.
