from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
NEXT_CONFIG = PROJECT_ROOT / "ui" / "next.config.ts"
START_HYBRID = PROJECT_ROOT / "scripts" / "start-hybrid.ps1"


def test_next_dev_origin_is_explicit_and_not_wildcarded() -> None:
    config = NEXT_CONFIG.read_text(encoding="utf-8")

    assert "LINEALERT_UI_ALLOWED_DEV_ORIGIN" in config
    assert "allowedDevOrigins" in config
    assert "allowedDevOrigin ? [allowedDevOrigin] : []" in config
    assert '"*"' not in config
    assert "'*'" not in config


def test_hybrid_launcher_derives_default_route_ipv4_for_next_dev() -> None:
    script = START_HYBRID.read_text(encoding="utf-8")

    assert "LINEALERT_UI_ALLOWED_DEV_ORIGIN" in script
    assert 'Get-NetRoute -DestinationPrefix "0.0.0.0/0"' in script
    assert "Get-NetIPAddress -InterfaceIndex $defaultRoute.InterfaceIndex" in script
    assert '$_.IPAddress -ne "127.0.0.1"' in script
    assert '$_.IPAddress -notlike "169.254.*"' in script
    assert "Allowed Next.js LAN dev origin: $lanDevOrigin" in script


def test_lan_origin_change_does_not_expose_loopback_services() -> None:
    script = START_HYBRID.read_text(encoding="utf-8")

    assert "127.0.0.1 -Port 8767" in script
    assert "127.0.0.1 -Port 8768" in script
    assert "historian_emulator_service" in script
    assert "service_case_service" in script
