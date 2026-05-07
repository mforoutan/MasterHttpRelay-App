from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path


def _default_config_path() -> Path:
    candidates = [
        Path(__file__).resolve().parents[2] / "config.example.json",
        Path.cwd() / "config.example.json",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return Path()


def load_default_config() -> dict:
    path = _default_config_path()
    if path:
        try:
            with path.open(encoding="utf-8") as handle:
                return json.load(handle)
        except Exception:
            pass
    return {
        "google_ip": "216.239.38.120",
        "front_domain": "www.google.com",
        "front_domains": ["www.google.com", "mail.google.com", "accounts.google.com"],
        "script_id": "YOUR_APPS_SCRIPT_DEPLOYMENT_ID",
        "auth_key": "CHANGE_ME_TO_A_STRONG_SECRET",
        "listen_host": "127.0.0.1",
        "http_port": 8085,
        "socks5_port": 1080,
        "verify_ssl": True,
        "lan_sharing": False,
        "relay_timeout": 25,
        "tls_connect_timeout": 15,
        "tcp_connect_timeout": 10,
        "parallel_relay": 1,
        "h2_connections": 2,
        "enable_sub_batch": True,
        "block_hosts": [],
        "direct_hosts": [],
        "youtube_via_relay": False,
        "hosts": {},
        "exit_node": {
            "enabled": False,
            "provider": "cloudflare",
            "url": "",
            "psk": "",
            "mode": "full",
            "hosts": [],
        },
        "log_level": "INFO",
        "adblock_lists": [],
    }


class ConfigStore:
    def __init__(self, app_name: str = "masterhttprelayvpn"):
        self.app_name = app_name
        base_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
        self.root = base_dir / app_name
        self.profiles_dir = self.root / "profiles"
        self.runtime_dir = self.root / "runtime"
        self.state_file = self.root / "state.json"
        self.runtime_config_file = self.runtime_dir / "active.json"
        self.default_profile_name = "default"
        self.ensure_layout()

    def ensure_layout(self) -> None:
        self.profiles_dir.mkdir(parents=True, exist_ok=True)
        self.runtime_dir.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _sanitize_name(name: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", name.strip())
        cleaned = cleaned.strip("._-")
        return cleaned or "profile"

    def profile_path(self, name: str) -> Path:
        return self.profiles_dir / f"{self._sanitize_name(name)}.json"

    def list_profiles(self) -> list[str]:
        profiles = sorted(path.stem for path in self.profiles_dir.glob("*.json"))
        if self.default_profile_name not in profiles:
            profiles.insert(0, self.default_profile_name)
        return profiles

    def read_profile(self, name: str) -> dict:
        path = self.profile_path(name)
        if not path.exists() and name == self.default_profile_name:
            profile = load_default_config()
            self.write_profile(name, profile)
            return copy.deepcopy(profile)
        if not path.exists():
            raise FileNotFoundError(path)
        with path.open(encoding="utf-8") as handle:
            return json.load(handle)

    def write_profile(self, name: str, config: dict) -> Path:
        path = self.profile_path(name)
        with path.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        return path

    def delete_profile(self, name: str) -> None:
        if name == self.default_profile_name:
            raise ValueError("default profile cannot be deleted")
        path = self.profile_path(name)
        if path.exists():
            path.unlink()

    def active_profile_name(self) -> str:
        if self.state_file.exists():
            try:
                with self.state_file.open(encoding="utf-8") as handle:
                    data = json.load(handle)
                name = str(data.get("active_profile") or "").strip()
                if name:
                    return name
            except Exception:
                pass
        return self.default_profile_name

    def set_active_profile_name(self, name: str) -> None:
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        with self.state_file.open("w", encoding="utf-8") as handle:
            json.dump({"active_profile": name}, handle, indent=2)
            handle.write("\n")

    def ensure_active_profile(self) -> str:
        name = self.active_profile_name()
        try:
            self.read_profile(name)
        except FileNotFoundError:
            name = self.default_profile_name
            self.write_profile(name, load_default_config())
        self.set_active_profile_name(name)
        return name

    def load_active_profile(self) -> tuple[str, dict]:
        name = self.ensure_active_profile()
        return name, self.read_profile(name)

    def save_runtime_config(self, config: dict) -> Path:
        with self.runtime_config_file.open("w", encoding="utf-8") as handle:
            json.dump(config, handle, indent=2)
            handle.write("\n")
        return self.runtime_config_file
