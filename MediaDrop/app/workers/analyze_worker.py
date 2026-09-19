"""Asynchronous worker for URL metadata analysis."""

from PySide6.QtCore import QThread, Signal

from app.database.models import MediaMetadata
from app.services.media_service import media_service
from app.utils.logger import logger


class AnalyzeWorker(QThread):
    """Worker thread that extracts media metadata without blocking the UI."""

    analysis_finished = Signal(object)  # MediaMetadata
    analysis_error = Signal(str, str)   # friendly_message, technical_details

    def __init__(self, url: str, parent=None):
        super().__init__(parent)
        self.url = url.strip()

    def run(self):
        logger.info(f"Starting analysis for URL: {self.url}")
        try:
            metadata = media_service.analyze_url(self.url)
            self.analysis_finished.emit(metadata)
        except RuntimeError as re:
            err_text = str(re)
            if "|||" in err_text:
                friendly, detail = err_text.split("|||", 1)
            else:
                friendly = "Unable to analyze media"
                detail = err_text
            self.analysis_error.emit(friendly, detail)
        except Exception as e:
            logger.error(f"Unexpected error in AnalyzeWorker: {e}")
            self.analysis_error.emit("Unable to analyze URL", str(e))
