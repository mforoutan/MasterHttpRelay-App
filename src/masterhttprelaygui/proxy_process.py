from __future__ import annotations

import os
import sys
from pathlib import Path

from PyQt6.QtCore import QProcess, QObject, pyqtSignal


class ProxyProcess(QObject):
    started = pyqtSignal()
    stopped = pyqtSignal(int)
    output = pyqtSignal(str)
    error = pyqtSignal(str)

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._process = QProcess(self)
        self._process.setProcessChannelMode(QProcess.ProcessChannelMode.SeparateChannels)
        self._process.readyReadStandardOutput.connect(self._read_stdout)
        self._process.readyReadStandardError.connect(self._read_stderr)
        self._process.started.connect(self.started)
        self._process.errorOccurred.connect(self._on_error)
        self._process.finished.connect(self._on_finished)

    def is_running(self) -> bool:
        return self._process.state() != QProcess.ProcessState.NotRunning

    def start(self, config_path: Path) -> None:
        if self.is_running():
            return

        project_root = Path(__file__).resolve().parents[2]
        arguments = ["-u", "-m", "masterhttprelaygui.proxy_entry", "--config", str(config_path)]

        environment = self._process.processEnvironment()
        if environment.isEmpty():
            environment = QProcess.systemEnvironment()
        environment.insert("PYTHONUNBUFFERED", "1")
        self._process.setProcessEnvironment(environment)
        self._process.setWorkingDirectory(str(project_root))
        self._process.start(sys.executable, arguments)

    def stop(self) -> None:
        if self._process.state() == QProcess.ProcessState.NotRunning:
            return
        self._process.terminate()
        if not self._process.waitForFinished(3000):
            self._process.kill()

    def _read_stdout(self) -> None:
        data = bytes(self._process.readAllStandardOutput()).decode("utf-8", "replace")
        if data:
            self.output.emit(data)

    def _read_stderr(self) -> None:
        data = bytes(self._process.readAllStandardError()).decode("utf-8", "replace")
        if data:
            self.output.emit(data)

    def _on_error(self, error: QProcess.ProcessError) -> None:
        self.error.emit(f"proxy process error: {error.name}")

    def _on_finished(self, exit_code: int, _exit_status) -> None:
        self.stopped.emit(exit_code)
