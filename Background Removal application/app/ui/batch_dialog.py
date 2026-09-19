"""Batch processing dialog."""
from __future__ import annotations

import os
import time
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QPlainTextEdit,
    QSpinBox,
    QVBoxLayout,
)

from app.batch.worker import BatchSettings, discover_images
from app.ui.style import DARK_PALETTE
from app.ui.worker_thread import BatchWorker
from app.utils.config import AppSettings

PRESETS = ["Auto", "Fast", "High Quality", "Human", "Product", "Hair/Fur"]
QUALITY = ["Ultra Quality", "High Quality", "Standard"]
BG_MODES = ["Transparent", "White", "Black", "Custom Color", "Custom Image", "Blurred Background", "Checkerboard"]


class BatchDialog(QDialog):
    def __init__(self, parent=None, settings: AppSettings | None = None):
        super().__init__(parent)
        self.setWindowTitle("Batch Background Removal")
        self.resize(760, 620)
        self.settings = settings or AppSettings.defaults()
        self.files: list[Path] = []
        self.worker: BatchWorker | None = None
        self.started = False
        self._build_ui()

    def _build_ui(self):
        v = QVBoxLayout(self)

        # inputs
        grp = QGroupBox("Input / Output")
        inner = QFormLayout(grp)

        row = QHBoxLayout()
        self.txt_input = QLineEdit(self.settings.last_input_folder or "")
        self.btn_browse_in = QPushButton("Browse...")
        self.btn_browse_in.clicked.connect(self._browse_input)
        row.addWidget(self.txt_input, 1)
        row.addWidget(self.btn_browse_in)
        inner.addRow("Input folder", row)

        row2 = QHBoxLayout()
        self.txt_output = QLineEdit("")
        self.btn_browse_out = QPushButton("Browse...")
        self.btn_browse_out.clicked.connect(self._browse_output)
        row2.addWidget(self.txt_output, 1)
        row2.addWidget(self.btn_browse_out)
        inner.addRow("Output folder", row2)
        self.lbl_count = QLabel("")
        self.lbl_count.setStyleSheet(f"color: {DARK_PALETTE['muted']};")
        inner.addRow("", self.lbl_count)
        v.addWidget(grp)

        # settings
        grp2 = QGroupBox("Settings")
        f2 = QFormLayout(grp2)
        self.cmb_preset = QComboBox()
        self.cmb_preset.addItems(PRESETS)
        self.cmb_preset.setCurrentText(self.settings.model_preset)
        self.cmb_quality = QComboBox()
        self.cmb_quality.addItems(QUALITY)
        self.cmb_quality.setCurrentText(self.settings.quality)
        self.cmb_bg = QComboBox()
        self.cmb_bg.addItems(BG_MODES)
        self.cmb_bg.setCurrentText("Transparent")
        self.spin_workers = QSpinBox()
        self.spin_workers.setRange(1, 32)
        self.spin_workers.setValue(max(1, self.settings.workers or 1))
        self.chk_meta = QCheckBox("Preserve metadata")
        self.chk_meta.setChecked(self.settings.preserve_metadata)
        self.chk_overwrite = QCheckBox("Overwrite existing outputs")
        self.txt_prefix = QLineEdit("")
        self.txt_prefix.setPlaceholderText("optional output prefix")
        f2.addRow("Preset", self.cmb_preset)
        f2.addRow("Quality", self.cmb_quality)
        f2.addRow("Background", self.cmb_bg)
        f2.addRow("Workers", self.spin_workers)
        f2.addRow("", self.chk_meta)
        f2.addRow("", self.chk_overwrite)
        f2.addRow("Prefix", self.txt_prefix)
        v.addWidget(grp2)

        # progress
        self.progress = QProgressBar()
        self.progress.setRange(0, 1000)
        v.addWidget(self.progress)
        self.lbl_progress = QLabel("Ready.")
        self.lbl_progress.setStyleSheet(f"color: {DARK_PALETTE['muted']};")
        v.addWidget(self.lbl_progress)

        self.log = QPlainTextEdit()
        self.log.setReadOnly(True)
        self.log.setMaximumBlockCount(2000)
        v.addWidget(self.log, 1)

        # buttons
        row3 = QHBoxLayout()
        self.btn_run = QPushButton("Start Batch")
        self.btn_run.setObjectName("primary")
        self.btn_run.clicked.connect(self._start)
        self.btn_pause = QPushButton("Pause")
        self.btn_pause.clicked.connect(self._pause)
        self.btn_resume = QPushButton("Resume")
        self.btn_resume.clicked.connect(self._resume)
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("danger")
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_retry = QPushButton("Retry Failed")
        self.btn_retry.clicked.connect(self._retry)
        self.btn_open = QPushButton("Open Output")
        self.btn_open.clicked.connect(self._open_output)
        for b in (self.btn_run, self.btn_pause, self.btn_resume, self.btn_cancel, self.btn_retry, self.btn_open):
            row3.addWidget(b)
        v.addLayout(row3)

        self._set_running(False)

    # ------------------------------------------------------------- helpers
    def _browse_input(self):
        folder = QFileDialog.getExistingDirectory(self, "Input folder", self.txt_input.text())
        if folder:
            self.txt_input.setText(folder)
            self._refresh_files()

    def _browse_output(self):
        folder = QFileDialog.getExistingDirectory(self, "Output folder", self.txt_output.text())
        if folder:
            self.txt_output.setText(folder)

    def _refresh_files(self):
        folder = self.txt_input.text()
        if not folder or not Path(folder).exists():
            self.files = []
            self.lbl_count.setText("")
            return
        self.files = discover_images(Path(folder))
        if not self.files:
            self.files = []
            self.lbl_count.setText("no supported images found")
            return
        self.lbl_count.setText(f"{len(self.files)} image(s) found")
        self.txt_output.setText(str(Path(folder) / "bg_remove_output"))
        self.settings.last_input_folder = folder

    def _make_settings(self) -> BatchSettings:
        out = self.txt_output.text().strip() or str(Path(self.txt_input.text()) / "bg_remove_output")
        return BatchSettings(
            preset=self.cmb_preset.currentText(),
            quality=self.cmb_quality.currentText(),
            output_folder=out,
            preserve_metadata=self.chk_meta.isChecked(),
            background_mode=self.cmb_bg.currentText(),
            overwrite=self.chk_overwrite.isChecked(),
            output_prefix=self.txt_prefix.text(),
            workers=self.spin_workers.value(),
            save_to_source_dir=False,
        )

    def _set_running(self, running: bool):
        self.btn_run.setEnabled(not running)
        self.btn_pause.setEnabled(running)
        self.btn_resume.setEnabled(False)
        self.btn_cancel.setEnabled(running)
        self.btn_retry.setEnabled(running)
        self.started = running

    def _log(self, msg: str):
        self.log.appendPlainText(msg)

    # ------------------------------------------------------------- actions
    def _start(self):
        if not self.txt_input.text() or not Path(self.txt_input.text()).exists():
            self._log("Input folder not found.")
            return
        if not self.files:
            self._refresh_files()
        if not self.files:
            self._log("No images to process.")
            return

        self.settings.workers = self.spin_workers.value()
        self.settings.save()
        settings = self._make_settings()
        self.worker = BatchWorker(self.files, settings, parent=self)
        self.worker.progress.connect(self._on_progress)
        self.worker.complete.connect(self._on_complete)
        self.worker.cancelled.connect(self._on_cancelled)
        self.worker.error.connect(self._on_error)
        self.log.clear()
        self.progress.setValue(0)
        self._set_running(True)
        self._log(f"Starting {len(self.files)} image(s) -> {settings.output_folder}")
        self._t0 = time.perf_counter()
        self._done = 0
        self.worker.start()

    def _on_progress(self, result, done, total, eta, fps):
        self._done = done
        self.progress.setValue(int(done / max(1, total) * 1000))
        self.lbl_progress.setText(
            f"{done}/{total}  |  {fps:.2f} img/s  |  ETA {self._fmt_eta(eta)}  |  {Path(result.input_path).name} -> {result.status}"
        )
        if result.status != "ok":
            self._log(f"  [{result.status}] {Path(result.input_path).name}: {result.error}")

    def _on_complete(self, results):
        ok = sum(1 for r in results if r.status == "ok")
        fail = sum(1 for r in results if r.status == "failed")
        skip = sum(1 for r in results if r.status == "skipped")
        elapsed = time.perf_counter() - self._t0
        self.progress.setValue(1000)
        self.lbl_progress.setText(f"Done in {elapsed:.1f}s — ok: {ok}  failed: {fail}  skipped: {skip}")
        self._set_running(False)
        self._log(f"Batch finished: {ok} ok, {fail} failed, {skip} skipped.")

    def _on_cancelled(self, results):
        self._set_running(False)
        self.lbl_progress.setText("Cancelled by user.")
        self._log("Batch cancelled.")

    def _on_error(self, message):
        self._set_running(False)
        self._log(f"ERROR: {message}")

    def _pause(self):
        if self.worker:
            self.worker.pause()
            self.btn_pause.setEnabled(False)
            self.btn_resume.setEnabled(True)
            self._log("Paused.")

    def _resume(self):
        if self.worker:
            self.worker.resume()
            self._log("Resumed.")
            self._set_running(True)

    def _cancel(self):
        if self.worker:
            self.worker.cancel()
            self._log("Cancelling...")

    def _retry(self):
        if self.worker is None:
            return
        failed = self.worker.failed_paths()
        if not failed:
            self._log("No failed files to retry.")
            return
        self.files = failed
        self._log(f"Retrying {len(failed)} failed file(s)...")
        self._start()

    def _open_output(self):
        folder = self.txt_output.text()
        if folder and Path(folder).exists():
            QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(folder))))
        else:
            self._log("Output folder does not exist yet.")

    @staticmethod
    def _fmt_eta(seconds: float) -> str:
        if seconds < 0:
            return "--"
        m, s = divmod(int(seconds), 60)
        if m >= 60:
            h, m = divmod(m, 60)
            return f"{h}h{m:02d}m"
        return f"{m}m{s:02d}s"