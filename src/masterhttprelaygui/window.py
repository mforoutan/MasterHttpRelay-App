from __future__ import annotations

import copy
import json
from pathlib import Path

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QAction, QIcon
from PyQt6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QMenu,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QStyle,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from .config_store import ConfigStore, load_default_config
from .proxy_process import ProxyProcess
from .system_proxy import SystemProxyManager


def _as_csv(value) -> str:
    if isinstance(value, list):
        return ", ".join(str(item) for item in value if str(item).strip())
    return str(value or "")


def _split_csv(text: str) -> list[str]:
    return [item.strip() for item in text.split(",") if item.strip()]


def _copy_base_config(config: dict) -> dict:
    base = load_default_config()
    base.update(copy.deepcopy(config or {}))
    exit_node = copy.deepcopy(base.get("exit_node") or {})
    exit_node.update(copy.deepcopy((config or {}).get("exit_node") or {}))
    base["exit_node"] = exit_node
    return base


class ProfileEditor(QWidget):
    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._base_config = load_default_config()
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QFormLayout(self)

        self.google_ip = QLineEdit()
        self.front_domain = QLineEdit()
        self.front_domains = QLineEdit()
        # Deployment ID and auth_key are sensitive — use password fields with toggle
        self.script_id_edit = QLineEdit()
        self.script_id_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.script_id_toggle = QPushButton("Show")
        self.script_id_toggle.setCheckable(True)
        self.script_id_toggle.clicked.connect(lambda: self._toggle_echo(self.script_id_edit, self.script_id_toggle))

        self.auth_key = QLineEdit()
        self.auth_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.auth_key_toggle = QPushButton("Show")
        self.auth_key_toggle.setCheckable(True)
        self.auth_key_toggle.clicked.connect(lambda: self._toggle_echo(self.auth_key, self.auth_key_toggle))
        self.listen_host = QLineEdit()
        self.http_port = QLineEdit()
        self.socks5_port = QLineEdit()
        self.verify_ssl = QCheckBox("Verify upstream TLS")
        self.lan_sharing = QCheckBox("Enable LAN sharing")
        self.relay_timeout = QLineEdit()
        self.tls_connect_timeout = QLineEdit()
        self.tcp_connect_timeout = QLineEdit()
        self.log_level = QComboBox()
        self.log_level.addItems(["DEBUG", "INFO", "WARNING", "ERROR"])
        self.youtube_via_relay = QCheckBox("Route YouTube through relay")

        self.exit_enabled = QCheckBox("Enable exit node")
        self.exit_provider = QComboBox()
        self.exit_provider.setEditable(True)
        self.exit_provider.addItems(["cloudflare", "deno", "vps"])
        self.exit_url = QLineEdit()
        self.exit_psk = QLineEdit()
        self.exit_psk.setEchoMode(QLineEdit.EchoMode.Password)
        self.exit_mode = QComboBox()
        self.exit_mode.addItems(["full", "selective"])
        self.exit_hosts = QLineEdit()

        layout.addRow("Google IP", self.google_ip)
        layout.addRow("Front domain", self.front_domain)
        layout.addRow("Front domains (comma-separated)", self.front_domains)
        # compose widgets with toggle buttons
        sid_box = QWidget()
        sid_layout = QHBoxLayout(sid_box)
        sid_layout.setContentsMargins(0, 0, 0, 0)
        sid_layout.addWidget(self.script_id_edit)
        sid_layout.addWidget(self.script_id_toggle)

        auth_box = QWidget()
        auth_layout = QHBoxLayout(auth_box)
        auth_layout.setContentsMargins(0, 0, 0, 0)
        auth_layout.addWidget(self.auth_key)
        auth_layout.addWidget(self.auth_key_toggle)

        layout.addRow("Apps Script deployment ID", sid_box)
        layout.addRow("Auth key", auth_box)
        layout.addRow("Listen host", self.listen_host)
        layout.addRow("HTTP port", self.http_port)
        layout.addRow("SOCKS5 port", self.socks5_port)
        layout.addRow(self.verify_ssl)
        layout.addRow(self.lan_sharing)
        layout.addRow("Relay timeout", self.relay_timeout)
        layout.addRow("TLS connect timeout", self.tls_connect_timeout)
        layout.addRow("TCP connect timeout", self.tcp_connect_timeout)
        layout.addRow("Log level", self.log_level)
        layout.addRow(self.youtube_via_relay)

        exit_box = QGroupBox("Exit node")
        exit_layout = QFormLayout(exit_box)
        exit_layout.addRow(self.exit_enabled)
        exit_layout.addRow("Provider", self.exit_provider)
        exit_layout.addRow("URL", self.exit_url)
        exit_layout.addRow("PSK", self.exit_psk)
        exit_layout.addRow("Mode", self.exit_mode)
        exit_layout.addRow("Hosts (comma-separated)", self.exit_hosts)
        layout.addRow(exit_box)

    def _toggle_echo(self, line_edit: QLineEdit, button: QPushButton) -> None:
        if button.isChecked():
            line_edit.setEchoMode(QLineEdit.EchoMode.Normal)
            button.setText("Hide")
        else:
            line_edit.setEchoMode(QLineEdit.EchoMode.Password)
            button.setText("Show")

    def set_config(self, config: dict) -> None:
        self._base_config = _copy_base_config(config)
        cfg = self._base_config
        exit_node = cfg.get("exit_node") or {}

        self.google_ip.setText(str(cfg.get("google_ip", "")))
        self.front_domain.setText(str(cfg.get("front_domain", "")))
        self.front_domains.setText(_as_csv(cfg.get("front_domains", [])))
        self.script_id_edit.setText(str(cfg.get("script_id", "")))
        self.auth_key.setText(str(cfg.get("auth_key", "")))
        self.listen_host.setText(str(cfg.get("listen_host", "127.0.0.1")))
        self.http_port.setText(str(cfg.get("http_port", 8085)))
        self.socks5_port.setText(str(cfg.get("socks5_port", 1080)))
        self.verify_ssl.setChecked(bool(cfg.get("verify_ssl", True)))
        self.lan_sharing.setChecked(bool(cfg.get("lan_sharing", False)))
        self.relay_timeout.setText(str(cfg.get("relay_timeout", 25)))
        self.tls_connect_timeout.setText(str(cfg.get("tls_connect_timeout", 15)))
        self.tcp_connect_timeout.setText(str(cfg.get("tcp_connect_timeout", 10)))
        self.log_level.setCurrentText(str(cfg.get("log_level", "INFO")))

        self.exit_enabled.setChecked(bool(exit_node.get("enabled", False)))
        self.exit_provider.setCurrentText(str(exit_node.get("provider", "cloudflare")))
        self.exit_url.setText(str(exit_node.get("url", "")))
        self.exit_psk.setText(str(exit_node.get("psk", "")))
        self.exit_mode.setCurrentText(str(exit_node.get("mode", "full")))
        self.exit_hosts.setText(_as_csv(exit_node.get("hosts", [])))
        self.youtube_via_relay.setChecked(bool(cfg.get("youtube_via_relay", False)))

    def get_config(self) -> dict:
        cfg = copy.deepcopy(self._base_config)
        cfg["google_ip"] = self.google_ip.text().strip() or cfg.get("google_ip", "216.239.38.120")
        cfg["front_domain"] = self.front_domain.text().strip() or cfg.get("front_domain", "www.google.com")
        cfg["front_domains"] = _split_csv(self.front_domains.text())
        script_id = self.script_id_edit.text().strip()
        if script_id:
            cfg["script_id"] = script_id
            cfg.pop("script_ids", None)
        cfg["auth_key"] = self.auth_key.text().strip()
        cfg["listen_host"] = self.listen_host.text().strip() or "127.0.0.1"
        cfg["http_port"] = self._as_int(self.http_port.text(), 8085)
        cfg["socks5_port"] = self._as_int(self.socks5_port.text(), 1080)
        cfg["verify_ssl"] = self.verify_ssl.isChecked()
        cfg["lan_sharing"] = self.lan_sharing.isChecked()
        cfg["relay_timeout"] = self._as_int(self.relay_timeout.text(), 25)
        cfg["tls_connect_timeout"] = self._as_int(self.tls_connect_timeout.text(), 15)
        cfg["tcp_connect_timeout"] = self._as_int(self.tcp_connect_timeout.text(), 10)
        cfg["log_level"] = self.log_level.currentText()
        cfg["youtube_via_relay"] = bool(self.youtube_via_relay.isChecked())

        exit_node = copy.deepcopy(cfg.get("exit_node") or {})
        exit_node["enabled"] = self.exit_enabled.isChecked()
        exit_node["provider"] = self.exit_provider.currentText().strip() or "cloudflare"
        exit_node["url"] = self.exit_url.text().strip()
        exit_node["psk"] = self.exit_psk.text().strip()
        exit_node["mode"] = self.exit_mode.currentText().strip() or "full"
        exit_node["hosts"] = _split_csv(self.exit_hosts.text())
        cfg["exit_node"] = exit_node
        return cfg

    @staticmethod
    def _as_int(value: str, default: int) -> int:
        try:
            return int(value.strip())
        except Exception:
            return default


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.store = ConfigStore()
        self.proxy = ProxyProcess(self)
        self.system_proxy = SystemProxyManager()
        self.current_profile = self.store.ensure_active_profile()
        self.is_proxy_running = False
        self.is_system_proxy_enabled = False
        self._build_ui()
        self._wire_events()
        self._load_initial_profile()
        self._sync_system_proxy_status()

    def _build_ui(self) -> None:
        self.setWindowTitle("MasterHttpRelayVPN")
        self.resize(1100, 820)

        central = QWidget()
        root = QVBoxLayout(central)

        profile_row = QHBoxLayout()
        self.profile_combo = QComboBox()
        self.reload_profiles_button = QPushButton("Reload Profiles")
        self.new_profile_button = QPushButton("New Profile")
        self.save_profile_button = QPushButton("Save Profile")
        self.delete_profile_button = QPushButton("Delete Profile")
        profile_row.addWidget(QLabel("Profile"))
        profile_row.addWidget(self.profile_combo, 1)
        profile_row.addWidget(self.reload_profiles_button)
        profile_row.addWidget(self.new_profile_button)
        profile_row.addWidget(self.save_profile_button)
        profile_row.addWidget(self.delete_profile_button)

        self.editor = ProfileEditor()

        controls = QGroupBox("Connection")
        control_row = QHBoxLayout(controls)
        self.connect_button = QPushButton("Connect")
        self.disconnect_button = QPushButton("Disconnect")
        self.restart_button = QPushButton("Restart Proxy")
        self.system_proxy_button = QPushButton("Enable System Proxy")
        self.system_proxy_checkbox = QCheckBox("Enable system proxy after connect")
        self.system_proxy_checkbox.setChecked(True)
        control_row.addWidget(self.connect_button)
        control_row.addWidget(self.disconnect_button)
        control_row.addWidget(self.restart_button)
        control_row.addWidget(self.system_proxy_button)
        control_row.addWidget(self.system_proxy_checkbox)

        status_box = QGroupBox("Status")
        status_layout = QVBoxLayout(status_box)
        self.status_label = QLabel("Idle")
        self.proxy_status_label = QLabel("Proxy process: stopped")
        self.system_status_label = QLabel("System proxy: unknown")
        self.path_label = QLabel(f"Runtime config: {self.store.runtime_config_file}")
        self.path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        status_layout.addWidget(self.status_label)
        status_layout.addWidget(self.proxy_status_label)
        status_layout.addWidget(self.system_status_label)
        status_layout.addWidget(self.path_label)

        self.logs = QPlainTextEdit()
        self.logs.setReadOnly(True)
        self.logs.setPlaceholderText("Proxy output will appear here.")

        log_box = QGroupBox("Logs")
        log_layout = QVBoxLayout(log_box)
        log_layout.addWidget(self.logs)

        form_scroll = QScrollArea()
        form_scroll.setWidgetResizable(True)
        form_scroll.setWidget(self.editor)

        root.addLayout(profile_row)
        root.addWidget(form_scroll, 2)
        root.addWidget(controls)
        root.addWidget(status_box)
        root.addWidget(log_box, 1)
        self.setCentralWidget(central)

        self.tray = QSystemTrayIcon(self._build_icon(), self)
        self.tray_menu = self._build_tray_menu()
        self.tray.setContextMenu(self.tray_menu)
        self.tray.activated.connect(self._tray_activated)
        self.tray.show()

        self._refresh_profiles()

    def _build_icon(self) -> QIcon:
        icon = QIcon.fromTheme("network-server")
        if not icon.isNull():
            return icon
        icon = QIcon.fromTheme("network-workgroup")
        if not icon.isNull():
            return icon
        return QApplication.style().standardIcon(QStyle.StandardPixmap.SP_ComputerIcon)

    def _build_tray_menu(self):
        menu = QMenu("MasterHttpRelayVPN", self)
        show_action = QAction("Show Window", self)
        connect_action = QAction("Connect", self)
        disconnect_action = QAction("Disconnect", self)
        toggle_action = QAction("Toggle System Proxy", self)
        quit_action = QAction("Quit", self)
        show_action.triggered.connect(self.show_window)
        connect_action.triggered.connect(self.connect_proxy)
        disconnect_action.triggered.connect(self.disconnect_proxy)
        toggle_action.triggered.connect(self.toggle_system_proxy)
        quit_action.triggered.connect(self.quit_app)
        menu.addAction(show_action)
        menu.addAction(connect_action)
        menu.addAction(disconnect_action)
        menu.addAction(toggle_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        return menu

    def _wire_events(self) -> None:
        self.reload_profiles_button.clicked.connect(self._refresh_profiles)
        self.new_profile_button.clicked.connect(self.create_profile)
        self.save_profile_button.clicked.connect(self.save_profile)
        self.delete_profile_button.clicked.connect(self.delete_profile)
        self.profile_combo.currentTextChanged.connect(self._profile_changed)
        self.connect_button.clicked.connect(self.connect_proxy)
        self.disconnect_button.clicked.connect(self.disconnect_proxy)
        self.restart_button.clicked.connect(self.restart_proxy)
        self.system_proxy_button.clicked.connect(self.toggle_system_proxy)
        self.proxy.started.connect(self._on_proxy_started)
        self.proxy.stopped.connect(self._on_proxy_stopped)
        self.proxy.output.connect(self.append_log)
        self.proxy.error.connect(self.append_log)

    def _load_initial_profile(self) -> None:
        name, config = self.store.load_active_profile()
        self.current_profile = name
        self.editor.set_config(config)
        self._refresh_profiles(select=name)

    def _refresh_profiles(self, select: str | None = None) -> None:
        current = select or self.current_profile or self.profile_combo.currentText()
        self.profile_combo.blockSignals(True)
        self.profile_combo.clear()
        for name in self.store.list_profiles():
            self.profile_combo.addItem(name)
        if current:
            index = self.profile_combo.findText(current)
            if index >= 0:
                self.profile_combo.setCurrentIndex(index)
        self.profile_combo.blockSignals(False)

    def _profile_changed(self, name: str) -> None:
        if not name:
            return
        try:
            config = self.store.read_profile(name)
        except FileNotFoundError:
            return
        self.current_profile = name
        self.store.set_active_profile_name(name)
        self.editor.set_config(config)
        self.status_label.setText(f"Loaded profile: {name}")
        self.append_log(f"Loaded profile {name}")

    def current_config(self) -> dict:
        return self.editor.get_config()

    def save_profile(self) -> None:
        name = self.profile_combo.currentText().strip() or self.current_profile or self.store.default_profile_name
        try:
            config = self.current_config()
            self.store.write_profile(name, config)
            self.store.set_active_profile_name(name)
            self.current_profile = name
            self.status_label.setText(f"Saved profile: {name}")
            self.append_log(f"Saved profile {name}")
            self._refresh_profiles(select=name)
        except Exception as exc:
            self._show_error("Could not save profile", str(exc))

    def create_profile(self) -> None:
        name, ok = QInputDialog.getText(self, "New profile", "Profile name:")
        if not ok or not name.strip():
            return
        try:
            self.store.write_profile(name, self.current_config())
            self.store.set_active_profile_name(name)
            self.current_profile = name
            self._refresh_profiles(select=name)
            self.status_label.setText(f"Created profile: {name}")
            self.append_log(f"Created profile {name}")
        except Exception as exc:
            self._show_error("Could not create profile", str(exc))

    def delete_profile(self) -> None:
        name = self.profile_combo.currentText().strip()
        if not name or name == self.store.default_profile_name:
            self._show_error("Delete profile", "The default profile cannot be deleted.")
            return
        answer = QMessageBox.question(self, "Delete profile", f"Delete profile '{name}'?", QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_profile(name)
            self.current_profile = self.store.default_profile_name
            self._refresh_profiles(select=self.current_profile)
            self._profile_changed(self.current_profile)
            self.status_label.setText(f"Deleted profile: {name}")
            self.append_log(f"Deleted profile {name}")
        except Exception as exc:
            self._show_error("Could not delete profile", str(exc))

    def connect_proxy(self) -> None:
        try:
            config = self.current_config()
            self.store.save_runtime_config(config)
            self.proxy.start(self.store.runtime_config_file)
            self.status_label.setText("Starting proxy...")
            self.append_log(f"Starting proxy with {self.store.runtime_config_file}")
        except Exception as exc:
            self._show_error("Could not start proxy", str(exc))

    def restart_proxy(self) -> None:
        self.disconnect_proxy()
        self.connect_proxy()

    def disconnect_proxy(self) -> None:
        if self.is_system_proxy_enabled:
            self._set_system_proxy(False)
        self.proxy.stop()
        self.status_label.setText("Stopping proxy...")

    def toggle_system_proxy(self) -> None:
        self._set_system_proxy(not self.is_system_proxy_enabled)

    def _set_system_proxy(self, enabled: bool) -> None:
        if enabled and not self.proxy.is_running():
            self.connect_proxy()
        try:
            host = self.editor.listen_host.text().strip() or "127.0.0.1"
            if host in {"0.0.0.0", "::", ""}:
                host = "127.0.0.1"
            port = int(self.editor.http_port.text().strip() or "8085")
            if enabled:
                self.system_proxy.enable(host, port)
                self.is_system_proxy_enabled = True
                self.system_proxy_button.setText("Disable System Proxy")
                self.system_proxy_checkbox.setChecked(True)
                self.status_label.setText(f"System proxy enabled via {self.system_proxy.backend.name}")
                self.append_log(f"System proxy enabled: {host}:{port} ({self.system_proxy.backend.name})")
            else:
                self.system_proxy.disable()
                self.is_system_proxy_enabled = False
                self.system_proxy_button.setText("Enable System Proxy")
                self.system_proxy_checkbox.setChecked(False)
                self.status_label.setText("System proxy disabled")
                self.append_log("System proxy disabled")
        except Exception as exc:
            self._show_error("System proxy error", str(exc))

    def _sync_system_proxy_status(self) -> None:
        status = self.system_proxy.status()
        self.is_system_proxy_enabled = status.enabled
        self.system_status_label.setText(f"System proxy: {status.backend} ({status.details or 'unknown'})")
        self.system_proxy_button.setText("Disable System Proxy" if status.enabled else "Enable System Proxy")
        self.system_proxy_checkbox.setChecked(status.enabled)

    def _on_proxy_started(self) -> None:
        self.is_proxy_running = True
        self.proxy_status_label.setText("Proxy process: running")
        self.status_label.setText("Proxy is running")
        self.append_log("Proxy started")
        if self.system_proxy_checkbox.isChecked() and not self.is_system_proxy_enabled:
            self._set_system_proxy(True)

    def _on_proxy_stopped(self, exit_code: int) -> None:
        self.is_proxy_running = False
        self.proxy_status_label.setText(f"Proxy process: stopped (exit code {exit_code})")
        self.status_label.setText("Proxy stopped")
        self.append_log(f"Proxy stopped with exit code {exit_code}")

    def append_log(self, text: str) -> None:
        if not text:
            return
        self.logs.appendPlainText(text.rstrip())
        self.logs.verticalScrollBar().setValue(self.logs.verticalScrollBar().maximum())

    def show_window(self) -> None:
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def quit_app(self) -> None:
        if self.is_system_proxy_enabled:
            try:
                self.system_proxy.disable()
            except Exception:
                pass
        self.proxy.stop()
        QApplication.instance().quit()

    def closeEvent(self, event) -> None:
        if self.tray.isVisible():
            event.ignore()
            self.hide()
            self.tray.showMessage("MasterHttpRelayVPN", "The app is still running in the system tray.", self.tray.icon(), 2000)
            return
        super().closeEvent(event)

    def _tray_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            if self.isVisible():
                self.hide()
            else:
                self.show_window()

    def _show_error(self, title: str, message: str) -> None:
        QMessageBox.critical(self, title, message)
        self.append_log(f"{title}: {message}")
