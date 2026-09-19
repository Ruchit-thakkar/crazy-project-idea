"""Application-specific exception types."""


class BgRemoveError(Exception):
    """Base exception for the application."""


class ImageLoadError(BgRemoveError):
    """Raised when an image file cannot be opened or decoded."""


class UnsupportedImageError(ImageLoadError):
    """Raised when the file format is not supported."""


class CorruptImageError(ImageLoadError):
    """Raised when a supported file turns out to be corrupt/undecodable."""


class ModelLoadError(BgRemoveError):
    """Raised when an AI model or its weights cannot be loaded."""


class ModelNotFoundError(ModelLoadError):
    """Raised when model weights have not been downloaded yet."""


class OutOfMemoryError(BgRemoveError):
    """Raised when a memory budget has been exceeded while processing."""


class HugeImageError(BgRemoveError):
    """Raised when an image exceeds the configured tile timeout budget."""


class ProcessingError(BgRemoveError):
    """Raised when image processing fails for image-specific reasons."""


class ExportError(BgRemoveError):
    """Raised when an output file cannot be written."""


class VerificationError(BgRemoveError):
    """Raised when quality verification of a result fails."""