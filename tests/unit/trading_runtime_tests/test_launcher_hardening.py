"""Tests for ATS One-Command Launcher Hardening and Toolchain Resolution."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path("d:/Projects/ATS/worktrees/final-a2-integration")
COMMON_PS1 = REPO_ROOT / "scripts" / "ats-common.ps1"
START_PS1 = REPO_ROOT / "scripts" / "ats-start.ps1"


def _run_powershell(code: str, cwd: str = "C:\\Windows\\System32") -> subprocess.CompletedProcess[str]:
    cmd = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", code]
    return subprocess.run(cmd, capture_output=True, text=True, cwd=cwd)


def test_ats_toolchain_resolution_from_system32() -> None:
    ps_code = f"""
    . '{COMMON_PS1}'
    Assert-AtsToolchain
    Write-Host "NODE_PATH:$($env:Path.Split(';')[0])"
    """
    res = _run_powershell(ps_code, cwd="C:\\Windows\\System32")
    assert res.returncode == 0, res.stderr
    assert "D:\\Projects\\ATS\\toolchains\\node-v24.19.0-win-x64" in res.stdout


def test_ats_repo_resolution_is_cwd_independent() -> None:
    ps_code = f"""
    Set-Location 'C:\\Windows\\System32'
    . '{COMMON_PS1}'
    Write-Host "REPO:$script:AtsRepo"
    """
    res = _run_powershell(ps_code, cwd="C:\\Windows\\System32")
    assert res.returncode == 0, res.stderr
    assert REPO_ROOT.resolve().name in res.stdout or "final-a2-integration" in res.stdout


def test_ats_pnpm_version_is_strictly_11_9_0() -> None:
    ps_code = f"""
    . '{COMMON_PS1}'
    $node = Join-Path $script:AtsNodeRoot 'node.exe'
    $ver = (& $node $script:AtsPnpmJs --version).Trim()
    Write-Host "PNPM_VER:$ver"
    """
    res = _run_powershell(ps_code, cwd="C:\\Windows\\System32")
    assert res.returncode == 0, res.stderr
    assert "PNPM_VER:11.9.0" in res.stdout


def test_missing_ats_node_fails_closed() -> None:
    ps_code = f"""
    . '{COMMON_PS1}'
    $script:AtsNodeRoot = 'D:\\InvalidPathThatDoesNotExist'
    try {{
        Assert-AtsToolchain
        Write-Host "FAILED_TO_RAISE"
    }} catch {{
        Write-Host "RAISED:$($_.Exception.Message)"
    }}
    """
    res = _run_powershell(ps_code, cwd="C:\\Windows\\System32")
    assert res.returncode == 0, res.stderr
    assert "RAISED:ATS_NODE_24_19_0_MISSING" in res.stdout


def test_ollama_preflight_has_bounded_local_recovery() -> None:
    source = COMMON_PS1.read_text(encoding="utf-8")
    assert "function Assert-AtsOllama([int]$StartupTimeoutSec = 30)" in source
    assert "Start-Process -FilePath $ollama.Source" in source
    assert "Get-Process -Name 'ollama'" in source
    assert ".AddSeconds($StartupTimeoutSec)" in source
    assert "throw 'ATS_OLLAMA_OFFLINE'" in source
    assert "@('qwen3:14b', 'qwen2.5:14b')" in source
