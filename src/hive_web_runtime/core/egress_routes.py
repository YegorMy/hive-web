from __future__ import annotations

import argparse
import json
import re
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from pydantic import BaseModel, Field

from hive_web_runtime.core.config import RuntimeConfig


class EgressRouteRule(BaseModel):
    name: str
    enabled: bool = True
    domains: list[str] = Field(default_factory=list)
    resolve_hosts: list[str] = Field(default_factory=list)
    gateway: str = "auto"
    interface: str = "auto"
    strict: bool = False


class EgressRouteConfig(BaseModel):
    enabled: bool = True
    refresh_interval_seconds: int = 3600
    rules: list[EgressRouteRule] = Field(default_factory=list)


DEFAULT_EGRESS_ROUTES = {
    "enabled": True,
    "refresh_interval_seconds": 3600,
    "rules": [
        {
            "name": "ozon-direct",
            "enabled": True,
            "domains": ["ozon.ru", "www.ozon.ru", ".ozon.ru"],
            "resolve_hosts": ["ozon.ru", "www.ozon.ru"],
            "gateway": "auto",
            "interface": "auto",
            "strict": False,
        }
    ],
}


class EgressRouteManager:
    def __init__(self, config: RuntimeConfig | None = None, config_path: Path | str | None = None, state_path: Path | str | None = None):
        self.config = config or RuntimeConfig()
        self.config_path = Path(config_path or self.config.egress_routes_config_path).expanduser()
        self.state_path = Path(state_path or self.config.egress_routes_state_path).expanduser()
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        self._load_or_create_config()

    @staticmethod
    def host_matches_domain(host: str, pattern: str) -> bool:
        host = (host or "").lower().strip(".")
        pattern = pattern.lower().strip()
        if pattern.startswith("."):
            normalized = pattern[1:].strip(".")
            return host == normalized or host.endswith(f".{normalized}")
        return host == pattern

    def ensure_for_url(self, url: str, force: bool = False) -> dict[str, Any]:
        parsed = urlparse(url)
        host = parsed.hostname
        if not host:
            return {
                "matched": False,
                "url": url,
                "host": None,
                "rules": [],
                "warnings": [{"code": "ROUTE_URL_PARSE_FAILED", "message": "Could not parse host from URL"}],
                "errors": [],
            }
        return self.ensure_for_host(host, force=force)

    def ensure_for_host(self, host: str, force: bool = False) -> dict[str, Any]:
        host = host.lower().strip(".")
        config = self._reload_config()
        result: dict[str, Any] = {
            "matched": False,
            "host": host,
            "rules": [],
            "warnings": [],
            "errors": [],
        }

        if not config.enabled:
            result["warnings"].append({"code": "ROUTE_DISABLED", "message": "Egress route manager disabled"})
            return result

        matching_rules = [rule for rule in config.rules if rule.enabled and any(self.host_matches_domain(host, domain) for domain in rule.domains)]
        if not matching_rules:
            return result

        result["matched"] = True
        if not self._is_supported_platform():
            result["warnings"].append(
                {
                    "code": "EGRESS_ROUTE_PLATFORM_UNSUPPORTED",
                    "message": "Egress route enforcement is a no-op on non-macOS platforms",
                    "platform": sys.platform,
                }
            )
            for rule in matching_rules:
                result["rules"].append(self._status_for_rule(rule, {}, []))
            return result

        default_route = self._get_default_route()
        state = self._load_state()
        now = int(time.time())
        strict_errors: list[dict[str, Any]] = []

        for rule in matching_rules:
            rule_state = state.get("rules", {}).setdefault(rule.name, {})
            stale = force or self._is_stale(rule_state, now, config.refresh_interval_seconds)

            if stale:
                resolved_ips: dict[str, list[str]] = {}
                for resolve_host in rule.resolve_hosts:
                    resolved_ips[resolve_host] = self._resolve_host(resolve_host)
                rule_state["resolved_ips"] = resolved_ips
                rule_state["resolved_at"] = now
            else:
                resolved_ips = rule_state.get("resolved_ips", {})
                if not isinstance(resolved_ips, dict):
                    resolved_ips = {}

            route_results = []
            for resolved_host in rule.resolve_hosts:
                ips = resolved_ips.get(resolved_host, [])
                if not isinstance(ips, list):
                    ips = []
                if not ips:
                    warning = {
                        "code": "ROUTE_RESOLVE_FAILED",
                        "message": "No IPs resolved for route host",
                        "rule": rule.name,
                        "resolve_host": resolved_host,
                        "host": host,
                    }
                    route_results.append({"host": resolved_host, "status": "warn", "action": "skipped", "warning": warning})
                    result["warnings"].append(warning)
                    if rule.strict:
                        strict_errors.append(warning | {"rule": rule.name})
                    continue
                for ip in ips:
                    status = self._ensure_ip_route(rule, ip, default_route, host)
                    route_results.append(status)
                    if status.get("warning"):
                        warn = status["warning"]
                        result["warnings"].append(warn)
                        if rule.strict:
                            strict_errors.append(warn | {"rule": rule.name, "ip": ip})

            rule_state["last_status"] = {"updated_at": now, "route_results": route_results, "strict": rule.strict}
            state.setdefault("rules", {})[rule.name] = rule_state
            result["rules"].append(self._status_for_rule(rule, resolved_ips, route_results))

        state["updated_at"] = now
        self._save_state(state)

        if strict_errors:
            raise RuntimeError(json.dumps({"error": "ROUTE_APPLY_FAILED", "details": strict_errors}, ensure_ascii=False))
        return result

    @staticmethod
    def _is_stale(rule_state: dict[str, Any], now: int, refresh_interval_seconds: int) -> bool:
        resolved_at = int(rule_state.get("resolved_at", 0))
        if resolved_at <= 0:
            return True
        return now - resolved_at >= refresh_interval_seconds

    @staticmethod
    def _status_for_rule(rule: EgressRouteRule, resolved_ips: dict[str, list[str]], route_results: list[dict[str, Any]]) -> dict[str, Any]:
        warnings = [result.get("warning") for result in route_results if result.get("warning")]
        return {
            "rule": rule.name,
            "strict": rule.strict,
            "resolved_ips": resolved_ips,
            "route_results": route_results,
            "warnings": [warning for warning in warnings if warning is not None],
        }

    def _ensure_ip_route(self, rule: EgressRouteRule, ip: str, default_route: dict[str, str] | None, host: str) -> dict[str, Any]:
        current = self._get_route(ip)
        desired_gateway = default_route.get("gateway") if rule.gateway == "auto" else rule.gateway
        desired_interface = default_route.get("interface") if rule.interface == "auto" else rule.interface
        if not desired_gateway:
            warning = {
                "code": "ROUTE_TARGET_UNRESOLVED",
                "message": "No desired gateway resolved for route rule",
                "rule": rule.name,
                "ip": ip,
                "host": host,
            }
            return {"ip": ip, "status": "warn", "action": "skipped", "warning": warning}

        if current and self._is_desired_route(current, desired_gateway, desired_interface):
            return {
                "ip": ip,
                "status": "ok",
                "action": "noop",
                "gateway": desired_gateway,
                "interface": desired_interface,
            }

        warning_error: str | None = None
        action = "change"
        result = self._run_route(["route", "-n", "change", "-host", ip, desired_gateway])
        if result.returncode != 0:
            warning_error = (result.stderr or result.stdout or "").strip()
            action = "add"
            result = self._run_route(["route", "-n", "add", "-host", ip, desired_gateway])
            if result.returncode != 0 and not warning_error:
                warning_error = (result.stderr or result.stdout or "").strip()

        if result.returncode != 0:
            warning = {
                "code": "ROUTE_APPLY_FAILED",
                "message": warning_error or "Route update failed",
                "action": action,
                "rule": rule.name,
                "ip": ip,
                "host": host,
            }
            return {
                "ip": ip,
                "status": "warn",
                "action": action,
                "gateway": desired_gateway,
                "interface": desired_interface,
                "current_route": current,
                "warning": warning,
            }

        return {
            "ip": ip,
            "status": "ok",
            "action": action,
            "gateway": desired_gateway,
            "interface": desired_interface,
            "current_route": current,
        }

    @staticmethod
    def _is_desired_route(current: dict[str, str], desired_gateway: str | None, desired_interface: str | None) -> bool:
        if not desired_gateway:
            return False
        if current.get("gateway") != desired_gateway:
            return False
        if desired_interface and current.get("interface") and current.get("interface") != desired_interface:
            return False
        return True

    @staticmethod
    def _parse_route_output(output: str) -> dict[str, str]:
        route: dict[str, str] = {}
        match_gateway = re.search(r"^\s*gateway:\s*(\S+)", output, re.M)
        match_interface = re.search(r"^\s*interface:\s*(\S+)", output, re.M)
        if match_gateway:
            route["gateway"] = match_gateway.group(1)
        if match_interface:
            route["interface"] = match_interface.group(1)
        return route

    def _get_default_route(self) -> dict[str, str]:
        result = self._run_route(["route", "-n", "get", "default"])
        if result.returncode != 0:
            return {}
        return self._parse_route_output(result.stdout or "")

    def _get_route(self, ip: str) -> dict[str, str] | None:
        result = self._run_route(["route", "-n", "get", ip])
        if result.returncode != 0:
            return None
        route = self._parse_route_output(result.stdout or "")
        return route if route else None

    @staticmethod
    def _resolve_host(host: str) -> list[str]:
        try:
            infos = socket.getaddrinfo(host, None)
        except OSError:
            return []
        resolved: list[str] = []
        for family, _, _, _, sockaddr in infos:
            if family not in (socket.AF_INET, socket.AF_INET6):
                continue
            ip = sockaddr[0]
            if ip and ip not in resolved:
                resolved.append(ip)
        return resolved

    @staticmethod
    def _is_supported_platform() -> bool:
        return sys.platform.startswith("darwin")

    @staticmethod
    def _run_route(cmd: list[str]) -> subprocess.CompletedProcess[str]:
        return subprocess.run(cmd, text=True, capture_output=True, check=False)

    def _load_or_create_config(self) -> EgressRouteConfig:
        return self._reload_config()

    def _reload_config(self) -> EgressRouteConfig:
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        if not self.config_path.exists():
            self._write_json(self.config_path, DEFAULT_EGRESS_ROUTES)
            return EgressRouteConfig.model_validate(DEFAULT_EGRESS_ROUTES)
        try:
            raw = self._read_json_or_default(self.config_path, DEFAULT_EGRESS_ROUTES)
        except (OSError, json.JSONDecodeError):
            raw = DEFAULT_EGRESS_ROUTES
            self._write_json(self.config_path, DEFAULT_EGRESS_ROUTES)
        return EgressRouteConfig.model_validate(raw)

    @staticmethod
    def _read_json_or_default(path: Path, default: dict[str, Any]) -> dict[str, Any]:
        if not path.exists():
            return default
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            return default
        return payload

    def _load_state(self) -> dict[str, Any]:
        if not self.state_path.exists():
            return {"updated_at": 0, "rules": {}}
        try:
            payload = self._read_json_or_default(self.state_path, {"updated_at": 0, "rules": {}})
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return {"updated_at": 0, "rules": {}}
        if not isinstance(payload, dict):
            return {"updated_at": 0, "rules": {}}
        payload.setdefault("updated_at", 0)
        payload.setdefault("rules", {})
        return payload

    def _save_state(self, state: dict[str, Any]) -> None:
        self._write_json(self.state_path, state)

    @staticmethod
    def _write_json(path: Path, payload: Any) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)

    def status(self) -> dict[str, Any]:
        return {
            "config": self._reload_config().model_dump(),
            "state": self._load_state(),
            "config_path": str(self.config_path),
            "state_path": str(self.state_path),
        }


def main() -> None:
    parser = argparse.ArgumentParser(prog="hive-web-egress-routes")
    parser.add_argument("--config", dest="config_path", default=None, help="Path to egress-routes config")
    parser.add_argument("--state", dest="state_path", default=None, help="Path to egress-routes state cache")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ensure = subparsers.add_parser("ensure")
    ensure.add_argument("--url", required=True, help="URL to ensure route gate for")
    ensure.add_argument("--force", action="store_true", help="Force DNS resolve and route reapplication")

    subparsers.add_parser("status")
    args = parser.parse_args()

    manager = EgressRouteManager(config_path=args.config_path, state_path=args.state_path)
    if args.command == "ensure":
        print(json.dumps(manager.ensure_for_url(args.url, force=args.force), ensure_ascii=False, indent=2))
    else:
        print(json.dumps(manager.status(), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
