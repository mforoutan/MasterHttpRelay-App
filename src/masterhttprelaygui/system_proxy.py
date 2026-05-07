from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class SystemProxyStatus:
    backend: str
    enabled: bool
    details: str = ""


def _run(command: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(command, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _has_any(commands: list[str]) -> bool:
    return any(shutil.which(command) for command in commands)


class BaseProxyBackend:
    name = "unsupported"

    def is_available(self) -> bool:
        return False

    def enable(self, host: str, port: int) -> None:
        raise NotImplementedError

    def disable(self) -> None:
        raise NotImplementedError

    def status(self) -> SystemProxyStatus:
        return SystemProxyStatus(self.name, False, "unsupported")


class GSettingsProxyBackend(BaseProxyBackend):
    name = "gnome-gsettings"

    def is_available(self) -> bool:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        return _has_any(["gsettings"]) and ("gnome" in desktop or "unity" in desktop or "cinnamon" in desktop or desktop == "")

    def enable(self, host: str, port: int) -> None:
        _run(["gsettings", "set", "org.gnome.system.proxy", "mode", "manual"])
        _run(["gsettings", "set", "org.gnome.system.proxy.http", "host", host])
        _run(["gsettings", "set", "org.gnome.system.proxy.http", "port", str(port)])
        _run(["gsettings", "set", "org.gnome.system.proxy.https", "host", host])
        _run(["gsettings", "set", "org.gnome.system.proxy.https", "port", str(port)])
        _run(["gsettings", "set", "org.gnome.system.proxy", "ignore-hosts", "['localhost', '127.0.0.1', '::1']"])

    def disable(self) -> None:
        _run(["gsettings", "set", "org.gnome.system.proxy", "mode", "none"])

    def status(self) -> SystemProxyStatus:
        try:
            result = _run(["gsettings", "get", "org.gnome.system.proxy", "mode"])
            mode = result.stdout.strip().strip("'")
            enabled = mode == "manual"
            return SystemProxyStatus(self.name, enabled, mode)
        except Exception as exc:
            return SystemProxyStatus(self.name, False, str(exc))


class KdeProxyBackend(BaseProxyBackend):
    name = "kde-kioslave"

    def is_available(self) -> bool:
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        return _has_any(["kwriteconfig6", "kwriteconfig5"]) and ("kde" in desktop or "plasma" in desktop or desktop == "")

    def _kwriteconfig(self) -> str:
        return shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5") or "kwriteconfig6"

    def enable(self, host: str, port: int) -> None:
        writer = self._kwriteconfig()
        proxy = f"{host}:{port}"
        command = [writer, "--file", "kioslaverc", "--group", "Proxy Settings"]
        _run(command + ["--key", "ProxyType", "1"])
        _run(command + ["--key", "httpProxy", proxy])
        _run(command + ["--key", "httpsProxy", proxy])
        _run(command + ["--key", "ftpProxy", proxy])
        _run(command + ["--key", "socksProxy", proxy])
        _run(command + ["--key", "NoProxyFor", "localhost,127.0.0.1,::1"])

    def disable(self) -> None:
        writer = self._kwriteconfig()
        command = [writer, "--file", "kioslaverc", "--group", "Proxy Settings"]
        _run(command + ["--key", "ProxyType", "0"])

    def status(self) -> SystemProxyStatus:
        reader = shutil.which("kreadconfig6") or shutil.which("kreadconfig5")
        if not reader:
            return SystemProxyStatus(self.name, False, "missing kreadconfig")
        try:
            result = _run([reader, "--file", "kioslaverc", "--group", "Proxy Settings", "--key", "ProxyType"])
            value = result.stdout.strip()
            enabled = value == "1"
            return SystemProxyStatus(self.name, enabled, value)
        except Exception as exc:
            return SystemProxyStatus(self.name, False, str(exc))


class NullProxyBackend(BaseProxyBackend):
    name = "unsupported"


class SystemProxyManager:
    def __init__(self):
        self._backend = self._detect_backend()

    @staticmethod
    def _detect_backend() -> BaseProxyBackend:
        for backend in (GSettingsProxyBackend(), KdeProxyBackend()):
            if backend.is_available():
                return backend
        return NullProxyBackend()

    @property
    def backend(self) -> BaseProxyBackend:
        return self._backend

    def is_supported(self) -> bool:
        return not isinstance(self._backend, NullProxyBackend)

    def status(self) -> SystemProxyStatus:
        return self._backend.status()

    def enable(self, host: str, port: int) -> None:
        if not self.is_supported():
            raise RuntimeError("system proxy control is not supported on this desktop")
        self._backend.enable(host, port)

    def disable(self) -> None:
        if not self.is_supported():
            raise RuntimeError("system proxy control is not supported on this desktop")
        self._backend.disable()
