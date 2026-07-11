import json
import subprocess
import time
from pathlib import Path

import pytest

from hive_web_runtime.core.config import RuntimeConfig
from hive_web_runtime.core.egress_routes import DEFAULT_EGRESS_ROUTES, EgressRouteManager


def test_default_config_is_created_with_ozon_rule(tmp_path):
    config = RuntimeConfig(egress_routes_config_path=tmp_path / "egress-routes.json", egress_routes_state_path=tmp_path / "egress-routes-state.json")
    EgressRouteManager(config)

    data = json.loads((tmp_path / "egress-routes.json").read_text(encoding="utf-8"))
    assert data["enabled"]
    assert data["refresh_interval_seconds"] == 3600
    assert data["rules"] == DEFAULT_EGRESS_ROUTES["rules"]


def test_domain_matching_supports_exact_and_suffix_rules(tmp_path):
    config = RuntimeConfig(egress_routes_config_path=tmp_path / "egress-routes.json", egress_routes_state_path=tmp_path / "egress-routes-state.json")
    manager = EgressRouteManager(config)

    assert manager.host_matches_domain("ozon.ru", "ozon.ru")
    assert manager.host_matches_domain("www.ozon.ru", ".ozon.ru")
    assert manager.host_matches_domain("baz.ozon.ru", ".ozon.ru")


def test_manager_refreshes_stale_state_and_writes_new_ips(tmp_path):
    config = RuntimeConfig(egress_routes_config_path=tmp_path / "egress-routes.json", egress_routes_state_path=tmp_path / "egress-routes-state.json")
    manager = EgressRouteManager(config)
    old_state = {
        "updated_at": 0,
        "rules": {
            "ozon-direct": {
                "resolved_at": int(time.time()) - 7200,
                "resolved_ips": {"ozon.ru": ["1.1.1.1"], "www.ozon.ru": ["2.2.2.2"]},
                "last_status": {},
            }
        },
    }
    with (tmp_path / "egress-routes-state.json").open("w", encoding="utf-8") as f:
        json.dump(old_state, f)

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd == ["route", "-n", "get", "default"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gateway: 10.1.1.1\ninterface: en0\n")
        if cmd[:3] == ["route", "-n", "get"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gateway: 10.1.1.1\ninterface: en0\n")
        if cmd[1:4] in (["-n", "change", "-host"], ["-n", "add", "-host"]):
            return subprocess.CompletedProcess(cmd, 0, stdout="")
        return subprocess.CompletedProcess(cmd, 1, stderr="unexpected command")

    manager._is_supported_platform = lambda: True
    manager._run_route = fake_run
    manager._get_default_route = lambda: {"gateway": "10.1.1.1", "interface": "en0"}
    manager._resolve_host = lambda host: {"ozon.ru": ["9.9.9.9"], "www.ozon.ru": ["8.8.8.8"]}[host]
    manager._get_route = lambda ip: {"gateway": "10.1.1.1", "interface": "en0"}

    manager.ensure_for_host("ozon.ru", force=False)
    state = json.loads((tmp_path / "egress-routes-state.json").read_text(encoding="utf-8"))
    resolved = state["rules"]["ozon-direct"]["resolved_ips"]
    assert resolved["ozon.ru"] == ["9.9.9.9"]
    assert resolved["www.ozon.ru"] == ["8.8.8.8"]


def test_permission_failure_returns_warning_without_strict_failure(tmp_path):
    config = RuntimeConfig(egress_routes_config_path=tmp_path / "egress-routes.json", egress_routes_state_path=tmp_path / "egress-routes-state.json")
    manager = EgressRouteManager(config)

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd == ["route", "-n", "get", "default"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gateway: 10.1.1.1\ninterface: en0\n")
        if cmd[:3] == ["route", "-n", "get"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gateway: 1.1.1.1\ninterface: en1\n")
        return subprocess.CompletedProcess(cmd, 1, stderr="operation not permitted")

    manager._is_supported_platform = lambda: True
    manager._run_route = fake_run
    manager._get_default_route = lambda: {"gateway": "10.1.1.1", "interface": "en0"}
    manager._resolve_host = lambda host: {"ozon.ru": ["6.6.6.6"], "www.ozon.ru": ["7.7.7.7"]}[host]
    manager._get_route = lambda ip: {"gateway": "1.1.1.1", "interface": "en1"}

    result = manager.ensure_for_host("www.ozon.ru")
    codes = {warning["code"] for warning in result["warnings"]}
    assert "ROUTE_APPLY_FAILED" in codes


def test_strict_failure_raises_error(tmp_path):
    strict_config = dict(DEFAULT_EGRESS_ROUTES)
    strict_config["rules"] = [dict(rule, strict=True) for rule in strict_config["rules"]]
    config_path = tmp_path / "egress-routes.json"
    config_path.write_text(json.dumps(strict_config, ensure_ascii=False), encoding="utf-8")
    config = RuntimeConfig(egress_routes_config_path=config_path, egress_routes_state_path=tmp_path / "egress-routes-state.json")
    manager = EgressRouteManager(config)

    def fake_run(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        if cmd == ["route", "-n", "get", "default"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gateway: 10.1.1.1\ninterface: en0\n")
        if cmd[:3] == ["route", "-n", "get"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="gateway: 1.1.1.1\ninterface: en1\n")
        return subprocess.CompletedProcess(cmd, 1, stderr="operation not permitted")

    manager._is_supported_platform = lambda: True
    manager._run_route = fake_run
    manager._get_default_route = lambda: {"gateway": "10.1.1.1", "interface": "en0"}
    manager._resolve_host = lambda host: {"ozon.ru": ["6.6.6.6"], "www.ozon.ru": ["7.7.7.7"]}[host]
    manager._get_route = lambda ip: {"gateway": "1.1.1.1", "interface": "en1"}

    with pytest.raises(RuntimeError):
        manager.ensure_for_host("ozon.ru", force=True)
