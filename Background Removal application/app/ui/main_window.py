"""Main application window: single-image processing + manual refinement."""
from __future__ import annotations

from pathlib import Path

import numpy as np
from PySide6.QtCore import Qt, QSignalBlocker
from PySide6.QtGui import QAction, QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from app.batch.worker import BatchSettings, discover_images
from app.image.info import analyze
from app.image.io import export_transparent_png
from app.image.loader import LoadedImage, load
from app.metadata.bundle import MetadataBundle
from app.processing.background import (
    BLACK,
    CUSTOM_COLOR,
    OPTIONS,
    TRANSPARENT,
    WHITE,
    compose,
)
from app.processing.pipeline import PipelineResult
from app.processing.verify import verify_file, verify_floats
from app.ui.compareview import CompareView
from app.ui.imageview import ZoomableImageView
from app.ui.style import DARK_PALETTE, QSS
from app.ui.worker_thread import BatchWorker, RefineWorker, SingleProcessWorker
from app.utils.config import AppSettings, models_dir, output_dir
from app.utils.log import get_logger, setup_logging
from app.utils.system import detect_hardware

log = get_logger("ui.main")

MODEL_PRESETS = ["Auto", "Fast", "High Quality", "Human", "Product", "Hair/Fur"]
QUALITY_LEVELS = ["Ultra Quality", "High Quality", "Standard"]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        setup_logging(app_dir=str(models_dir().parent / "logs"))
        self.settings = AppSettings.defaults().load()
        self.setWindowTitle("BG REMOVE — AI Background Removal")
        self.resize(1440, 860)
        self.setAcceptDrops(True)

        self.loaded: LoadedImage | None = None
        self.result: PipelineResult | None = None
        self._workspace_alpha: np.ndarray | None = None   # current (possibly edited) alpha
        self._ai_alpha: np.ndarray | None = None          # untouched AI output (for Restore)
        self._undo_stack: list[np.ndarray] = []
        self._redo_stack: list[np.ndarray] = []
        self._worker: SingleProcessWorker | None = None
        self._refiner: RefineWorker | None = None
        self._bg_mode = TRANSPARENT
        self._bg_color = (1.0, 1.0, 1.0)
        self._bg_image: np.ndarray | None = None
        self.batch_worker: BatchWorker | None = None

        self._build_ui()
        self.setStyleSheet(QSS)
        self._apply_settings()
        win = detect_hardware(prefer_cuda=self.settings.prefer_cuda)
        self.statusBar().showMessage(
            f"Device: {win.device_label}  |  CPU cores: {win.cpu_count}"
        )

    # ------------------------------------------------------------------ UI
    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ---------- left: content area ----------
        left = QWidget()
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)

        title = QLabel(" BG REMOVE")
        title.setObjectName("appTitle")
        left_layout.addWidget(title)

        self.stack = QStackedWidget()
        left_layout.addWidget(self.stack, stretch=1)
        self._build_drop_zone()
        self._build_tabs()
        self.stack.addWidget(self._drop_widget)
        self.stack.addWidget(self._tabs)
        self.stack.setCurrentWidget(self._drop_widget)

        root.addWidget(left, stretch=1)

        # ---------- right: sidebar ----------
        self._build_sidebar()
        root.addWidget(self._sidebar, 0)

        # ---------- status / progress ----------
        self.progress = QProgressBar()
        self.progress.setMaximum(1000)
        self.progress.setValue(0)
        self.progress.setTextVisible(True)
        self.progress.hide()
        self.statusBar().addPermanentWidget(self.progress, 1)

    def _build_drop_zone(self):
        self._drop_widget = QWidget()
        v = QVBoxLayout(self._drop_widget)

        self.hint = QLabel(" Drag & Drop Image Here \n\n or")
        self.hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.hint.setStyleSheet(
            f"font-size: 26px; color: {DARK_PALETTE['text']}; border: 2px dashed "
            f"{DARK_PALETTE['border']}; border-radius: 14px; padding: 60px;"
        )
        v.addWidget(self.hint, 2)

        row = QHBoxLayout()
        row.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.btn_pick = QPushButton("Select Image")
        self.btn_pick.setObjectName("primary")
        self.btn_pick.clicked.connect(self._pick_single)
        row.addWidget(self.btn_pick)

        self.btn_batch = QPushButton("Batch Folder")
        self.btn_batch.clicked.connect(self._open_batch)
        row.addWidget(self.btn_batch)
        v.addLayout(row)

        info = QLabel("JPG / PNG / WEBP / TIFF / BMP  —  fully local, no uploads")
        info.setAlignment(Qt.AlignmentFlag.AlignCenter)
        info.setStyleSheet(f"color: {DARK_PALETTE['muted']};")
        v.addWidget(info)
        v.addStretch()

    def _build_tabs(self):
        self._tabs = QTabWidget()

        self.compare_view = CompareView()
        self._tabs.addTab(self.compare_view, "Compare")

        self.result_view = ZoomableImageView()
        self.result_view.on_edit.connect(self._on_mask_edited)
        self.result_view.image_dropped.connect(self._load_new_image)
        self._tabs.addTab(self.result_view, "Result")

        self.original_view = ZoomableImageView()
        self.original_view.image_dropped.connect(self._load_new_image)
        self._tabs.addTab(self.original_view, "Original")

        self._tabs.currentChanged.connect(self._on_tab_changed)

    def _build_sidebar(self):
        sidebar = QWidget()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(330)
        lay = QVBoxLayout(sidebar)
        lay.setContentsMargins(14, 14, 14, 14)
        lay.setSpacing(8)

        def section(text):
            lbl = QLabel(text)
            lbl.setObjectName("section")
            return lbl

        lay.addWidget(section("Image"))
        self.lbl_info = QLabel("no image loaded")
        self.lbl_info.setWordWrap(True)
        self.lbl_info.setStyleSheet(f"color: {DARK_PALETTE['muted']};")
        lay.addWidget(self.lbl_info)

        lay.addWidget(section("Model"))
        form = QFormLayout()
        self.combo_model = QComboBox()
        self.combo_model.addItems(MODEL_PRESETS)
        self.combo_model.setCurrentText(self.settings.model_preset)
        self.combo_quality = QComboBox()
        self.combo_quality.addItems(QUALITY_LEVELS)
        self.combo_quality.setCurrentText(self.settings.quality)
        form.addRow("Preset", self.combo_model)
        form.addRow("Quality", self.combo_quality)

        self.chk_metadata = QCheckBox("Preserve metadata")
        self.chk_metadata.setChecked(self.settings.preserve_metadata)
        self.lbl_engine = QLabel("engine: -")
        self.lbl_engine.setStyleSheet(f"color: {DARK_PALETTE['muted']};")
        lay.addLayout(form)
        lay.addWidget(self.chk_metadata)
        lay.addWidget(self.lbl_engine)

        lay.addWidget(section("Processing"))
        self.btn_process = QPushButton("REMOVE BACKGROUND")
        self.btn_process.setObjectName("primary")
        self.btn_process.clicked.connect(self._process_current)
        lay.addWidget(self.btn_process)

        self.lbl_verify = QLabel("")
        self.lbl_verify.setStyleSheet(
            f"color: {DARK_PALETTE['muted']}; font-family: Consolas; font-size: 11px;"
        )
        self.lbl_verify.setWordWrap(True)
        lay.addWidget(self.lbl_verify)

        lay.addWidget(section("Background Replacement"))
        self.combo_bg = QComboBox()
        self.combo_bg.addItems(list(OPTIONS))
        self.combo_bg.currentTextChanged.connect(self._bg_option_changed)
        lay.addWidget(self.combo_bg)

        self.btn_color = QPushButton("")
        self.btn_color.setFixedHeight(30)
        self.btn_color.clicked.connect(self._pick_color)
        lay.addWidget(self.btn_color)

        self.spin_blur = QDoubleSpinBox()
        self.spin_blur.setRange(3.0, 120.0)
        self.spin_blur.setValue(self.settings.blur_radius)
        self.spin_blur.setPrefix("blur radius: ")
        lay.addWidget(self.spin_blur)

        self.btn_bg_image = QPushButton("Choose Background Image")
        self.btn_bg_image.clicked.connect(self._pick_bg_image)
        lay.addWidget(self.btn_bg_image)

        lay.addWidget(section("Manual Refinement"))
        self.toggle_edit = QCheckBox("Edit Mask")
        self.toggle_edit.toggled.connect(self._toggle_edit)
        lay.addWidget(self.toggle_edit)

        tool_row = QHBoxLayout()
        self.btn_add = QPushButton("Add FG")
        self.btn_add.setCheckable(True)
        self.btn_add.setChecked(True)
        self.btn_remove = QPushButton("Remove")
        self.btn_remove.setCheckable(True)
        for b in (self.btn_add, self.btn_remove):
            tb = tool_row.addWidget(b)
        tool_row2 = QHBoxLayout()
        self.btn_restore = QPushButton("Restore")
        self.btn_refine = QPushButton("Refine Edge")
        self.btn_hair = QPushButton("Hair")
        for b in (self.btn_restore, self.btn_refine, self.btn_hair):
            b.clicked.connect(self._refinement_action)
            tool_row2.addWidget(b)
        lay.addLayout(tool_row)
        lay.addLayout(tool_row2)

        brush_form = QFormLayout()
        self.sld_size = QSlider(Qt.Orientation.Horizontal)
        self.sld_size.setRange(2, 400)
        self.sld_size.setValue(30)
        self.sld_hardness = QSlider(Qt.Orientation.Horizontal)
        self.sld_hardness.setRange(0, 100)
        self.sld_hardness.setValue(85)
        self.sld_opacity = QSlider(Qt.Orientation.Horizontal)
        self.sld_opacity.setRange(5, 100)
        self.sld_opacity.setValue(90)
        brush_form.addRow("Size", self.sld_size)
        brush_form.addRow("Hardness", self.sld_hardness)
        brush_form.addRow("Opacity", self.sld_opacity)
        lay.addLayout(brush_form)
        for s in (self.sld_size, self.sld_hardness, self.sld_opacity):
            s.valueChanged.connect(lambda _: self._sync_brush())

        undo_row = QHBoxLayout()
        self.btn_undo = QPushButton("Undo")
        self.btn_redo = QPushButton("Redo")
        self.btn_undo.clicked.connect(self._undo)
        self.btn_redo.clicked.connect(self._redo)
        undo_row.addWidget(self.btn_undo)
        undo_row.addWidget(self.btn_redo)
        lay.addLayout(undo_row)
        self._sync_undo_buttons()

        lay.addWidget(section("Export"))
        self.btn_export = QPushButton("Export PNG")
        self.btn_export.setObjectName("success")
        self.btn_export.clicked.connect(self._export_png)
        lay.addWidget(self.btn_export)

        self.btn_new = QPushButton("New Image")
        self.btn_new.clicked.connect(self._pick_single)
        lay.addWidget(self.btn_new)
        lay.addStretch(1)
        self._sidebar = sidebar

    # ------------------------------------------------------- settings sync
    def _apply_settings(self):
        self.combo_model.setCurrentText(self.settings.model_preset)
        self.combo_quality.setCurrentText(self.settings.quality)
        self.chk_metadata.setChecked(self.settings.preserve_metadata)
        self.spin_blur.setValue(self.settings.blur_radius)

    def _save_settings(self):
        self.settings.model_preset = self.combo_model.currentText()
        self.settings.quality = self.combo_quality.currentText()
        self.settings.preserve_metadata = self.chk_metadata.isChecked()
        self.settings.blur_radius = float(self.spin_blur.value())
        self.settings.save()

    def closeEvent(self, event: QCloseEvent):
        self._save_settings()
        super().closeEvent(event)

    # ------------------------------------------------------------- loading
    def _pick_single(self):
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image",
            self.settings.last_input_folder,
            "Images (*.jpg *.jpeg *.png *.webp *.tif *.tiff *.bmp)",
        )
        if path:
            self._load_new_image(path)

    def dragEnterEvent(self, event):
        if any("image" in str(u).lower() for u in event.mimeData().urls()):
            event.acceptProposedAction()

    def dropEvent(self, event):
        for url in event.mimeData().urls():
            p = url.toLocalFile()
            if p and Path(p).suffix.lower() in (".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp"):
                self._load_new_image(p)
                break
        event.acceptProposedAction()

    def _load_new_image(self, path: str):
        if self._worker and self._worker.isRunning():
            QMessageBox.information(self, "BG REMOVE", "Processing already in progress.")
            return
        try:
            self.loaded = load(path)
        except Exception as exc:
            QMessageBox.critical(self, "Load error", str(exc))
            return

        self.settings.last_input_folder = str(Path(path).parent)
        self.result = None
        self._workspace_alpha = None
        self._ai_alpha = None
        self._undo_stack.clear()
        self._redo_stack.clear()
        self.progress.setValue(0)
        self.progress.hide()

        info = self.loaded.info
        lines = [
            info.describe(),
            f"Orientation: {info.orientation}",
        ]
        self.lbl_info.setText("\n".join(lines))

        self.original_view.set_content(self.loaded.rgb.copy(), None, checker=False)
        self.compare_view.set_pair(self.loaded.rgb.copy(), None, None)
        self.result_view.set_content(self.loaded.rgb.copy(), None, checker=False)
        self.stack.setCurrentWidget(self._tabs)
        self._tabs.setCurrentIndex(2)
        self.lbl_verify.setText("")
        self.edit_dirty = False

    # ----------------------------------------------------------- processing
    def _process_current(self):
        if self.loaded is None:
            QMessageBox.information(self, "BG REMOVE", "Load an image first.")
            return
        if self._worker and self._worker.isRunning():
            return
        self._save_settings()
        self.btn_process.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.progress.setValue(0)
        self.progress.show()
        self.lbl_verify.setText("Running segmentation + matting...")

        rgb = self.loaded.rgb.copy()
        self._worker = SingleProcessWorker(
            rgb,
            preset=self.combo_model.currentText(),
            quality=self.combo_quality.currentText(),
            max_inference_side=self.settings.max_inference_side,
        )
        self._worker.progress.connect(self._on_progress)
        self._worker.finished_ok.connect(self._on_process_done)
        self._worker.failed.connect(self._on_process_failed)
        self._worker.start()

    def _on_progress(self, value: float, label: str):
        self.progress.setValue(int(value * 1000))
        self.progress.setFormat(f"{label}  {int(value*100)}%")

    def _on_process_done(self, result: PipelineResult):
        self.btn_process.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.progress.hide()
        self.result = result
        self._workspace_alpha = result.alpha.copy()
        self._ai_alpha = result.alpha.copy()
        self._undo_stack.clear()
        self._redo_stack.clear()
        self._sync_undo_buttons()

        self.lbl_engine.setText(f"engine: {result.engine_name}")
        self.lbl_verify.setText(result.verification.summary())
        self._render_views(activate_compare=True)

    def _on_process_failed(self, message: str):
        self.btn_process.setEnabled(True)
        self.progress.hide()
        self.lbl_verify.setText("FAILED")
        QMessageBox.critical(self, "Processing failed", message)

    # --------------------------------------------------------------- render
    def _render_views(self, activate_compare: bool = False):
        if self.result is None:
            return
        comp_rgb, comp_alpha = self._composite()
        self.compare_view.set_pair(self.loaded.rgb.copy(), comp_rgb.copy(), comp_alpha.copy())
        self.result_view.set_content(comp_rgb.copy(), comp_alpha.copy(), checker=True)
        if activate_compare:
            self._tabs.setCurrentIndex(0)

    def _composite(self) -> tuple[np.ndarray, np.ndarray]:
        """Current view composite honoring the background replacement mode."""
        rgb = self.result.rgb
        alpha = self._workspace_alpha
        if alpha is None:
            return rgb, alpha
        if self._bg_mode == TRANSPARENT:
            return rgb, alpha
        return compose(
            rgb,
            alpha,
            mode=self._bg_mode,
            color=self._bg_color,
            background_image=self._bg_image,
            blur_radius=float(self.spin_blur.value()),
        )

    def _on_tab_changed(self, _idx):
        self._sync_brush()

    # ------------------------------------------------- background options
    def _bg_option_changed(self, text: str):
        self._bg_mode = text
        show_color = text == CUSTOM_COLOR
        show_blur = text == "Blurred Background"
        show_img = text == "Custom Image"
        self.btn_color.setVisible(show_color)
        self.spin_blur.setVisible(show_blur)
        self.btn_bg_image.setVisible(show_img)
        self._render_views()

    def _pick_color(self):
        from PySide6.QtWidgets import QColorDialog

        col = QColorDialog.getColor()
        if col.isValid():
            self._bg_color = (col.redF(), col.greenF(), col.blueF())
            self._set_color_swatch()
            self._render_views()

    def _set_color_swatch(self):
        c = self._bg_color
        r, g, b = int(c[0] * 255), int(c[1] * 255), int(c[2] * 255)
        self.btn_color.setStyleSheet(f"background-color: rgb({r},{g},{b}); border: 1px solid #555;")

    def _pick_bg_image(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Background Image", "", "Images (*.png *.jpg *.jpeg *.webp *.tif *.tiff *.bmp)"
        )
        if not path:
            return
        try:
            from app.image.loader import load

            bg = load(path)
            self._bg_image = bg.rgb
            self._render_views()
        except Exception as exc:
            QMessageBox.warning(self, "Background image", str(exc))

    # ------------------------------------------------------- manual refine
    def _toggle_edit(self, enabled: bool):
        self.result_view.set_edit_enabled(enabled)
        if enabled and self.result is not None:
            self._tabs.setCurrentWidget(self.result_view)
            self._sync_brush()
        else:
            self._sync_brush()

    def _sync_brush(self):
        if self.result is None:
            return
        add = self.btn_add.isChecked()
        self.result_view.set_brush(
            radius=float(self.sld_size.value()),
            hardness=self.sld_hardness.value() / 100.0,
            opacity=self.sld_opacity.value() / 100.0,
            additive=add,
        )

    def _on_mask_edited(self):
        if self._ai_alpha is None:
            return
        previous = self.result_view.pop_previous_alpha()
        if previous is not None:
            self._undo_stack.append(previous)
            del self._redo_stack[:]
            if len(self._undo_stack) > 40:
                self._undo_stack.pop(0)
        self._sync_undo_buttons()
        self._render_views()

    def _undo(self):
        if not self._undo_stack or self._workspace_alpha is None:
            return
        self._redo_stack.append(self.result_view.current_alpha().copy())
        self._workspace_alpha = self._undo_stack.pop()
        self._sync_undo_buttons()
        self._render_views()

    def _redo(self):
        if not self._redo_stack or self._workspace_alpha is None:
            return
        self._undo_stack.append(self._workspace_alpha.copy())
        self._workspace_alpha = self._redo_stack.pop()
        self._sync_undo_buttons()
        self._render_views()

    def _sync_undo_buttons(self):
        self.btn_undo.setEnabled(bool(self._undo_stack))
        self.btn_redo.setEnabled(bool(self._redo_stack))

    def _refinement_action(self):
        btn = self.sender()
        if self.result is None or self._workspace_alpha is None:
            return
        if btn is self.btn_restore:
            self._undo_stack.append(self._workspace_alpha.copy())
            del self._redo_stack[:]
            self._workspace_alpha = self._ai_alpha.copy()
            self._sync_undo_buttons()
            self._render_views()
            return

        if btn is self.btn_refine:
            quality = "Ultra Quality" if self.combo_quality.currentText() == "Ultra Quality" else "High Quality"
            self._run_refine(quality)
        elif btn is self.btn_hair:
            from app.matting.matting import apply_matting

            self._undo_stack.append(self._workspace_alpha.copy())
            del self._redo_stack[:]
            try:
                self._workspace_alpha = apply_matting(
                    self.result.rgb, self._workspace_alpha, level="ultra"
                )
                self._sync_undo_buttons()
                self._render_views()
            except Exception as exc:
                QMessageBox.warning(self, "Hair refinement", str(exc))

    def _run_refine(self, quality: str):
        if self._refiner and self._refiner.isRunning():
            return
        old = self._workspace_alpha.copy()
        self._refiner = RefineWorker(self.result.rgb, old, quality=quality)
        self._refiner.finished_ok.connect(lambda ref: self._refine_done(ref, old))
        self._refiner.start()
        self.statusBar().showMessage("Refining edges...")

    def _refine_done(self, refined, old_before):
        self._undo_stack.append(old_before)
        del self._redo_stack[:]
        self._workspace_alpha = refined
        self._sync_undo_buttons()
        self._render_views()
        self.statusBar().showMessage("Edge refinement done.", 4000)

    # ---------------------------------------------------------------- export
    def _export_png(self):
        if self.result is None or self._workspace_alpha is None:
            return
        default_name = self.loaded.info.path
        stem = Path(default_name).stem
        suggested = str((self.settings.last_output_folder and Path(self.settings.last_output_folder)) or output_dir() / f"{stem}.png")
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Export Transparent PNG",
            str(suggested),
            "PNG Image (*.png)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"
        try:
            comp_rgb, comp_alpha = self._composite()
            meta = MetadataBundle.from_loaded(self.loaded)
            export_transparent_png(
                comp_rgb,
                comp_alpha,
                path,
                bit_depth=8 if self._bg_mode != TRANSPARENT else self.loaded.bit_depth,
                metadata=meta,
                preserve_metadata=self.chk_metadata.isChecked(),
            )
            check = verify_file(self.loaded.info.effective_size, path)
            self.settings.last_output_folder = str(Path(path).parent)
            self.settings.save()
            if not check.passed:
                QMessageBox.warning(self, "Export verification", check.summary())
            else:
                QMessageBox.information(
                    self, "Export complete",
                    f"Saved:\n{path}\n\n{check.summary()}\n\nLossless PNG, original resolution preserved.",
                )
        except Exception as exc:
            QMessageBox.critical(self, "Export failed", str(exc))

    # -------------------------------------------------------------- batch
    def _open_batch(self):
        from app.ui.batch_dialog import BatchDialog

        dlg = BatchDialog(self, settings=self.settings)
        dlg.exec()