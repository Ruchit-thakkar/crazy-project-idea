"""Hardware capability detection (CPU / NVIDIA CUDA / Apple MPS)."""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass

from app.utils.log import get_logger

log = get_logger("system")


@dataclass
class HardwareProfile:
    device: str  # "cuda" | "mps" | "cpu"
    device_name: str
    gpu_available: bool
    cpu_count: int
    supports_fp16: bool

    @property
    def device_label(self) -> str:
        return f"{self.device_name} ({self.device})"


_CACHED: HardwareProfile | None = None


def _torch_importable() -> bool:
    try:
        import torch  # noqa: F401

        return True
    except ImportError:
        return False


def detect_hardware(prefer_cuda: bool = True) -> HardwareProfile:
    """Auto-detect the best compute device.

    Returns a cached profile; call :func:`invalidate` to force a re-scan.
    """
    global _CACHED
    if _CACHED is not None:
        return _CACHED

    cpu_count = max(1, os.cpu_count() or 1)

    if not _torch_importable():
        prof = HardwareProfile(
            device="cpu",
            device_name="CPU (PyTorch not installed)",
            gpu_available=False,
            cpu_count=cpu_count,
            supports_fp16=False,
        )
        _CACHED = prof
        return prof

    import torch

    cuda_ok = torch.cuda.is_available() and torch.cuda.device_count() > 0
    mps_ok = hasattr(torch.backends, "mps") and torch.backends.mps.is_available()

    if cuda_ok and prefer_cuda:
        name = torch.cuda.get_device_name(0)
        cap = torch.cuda.get_device_capability(0)
        fp16 = cap >= (7, 0) if cap else False
        prof = HardwareProfile(
            device="cuda",
            device_name=f"{name} (CUDA)",
            gpu_available=True,
            cpu_count=cpu_count,
            supports_fp16=fp16,
        )
    elif mps_ok:
        prof = HardwareProfile(
            device="mps",
            device_name="Apple Silicon (MPS)",
            gpu_available=True,
            cpu_count=cpu_count,
            supports_fp16=True,
        )
    else:
        prof = HardwareProfile(
            device="cpu",
            device_name="CPU",
            gpu_available=True,  # CPU always available
            cpu_count=cpu_count,
            supports_fp16=False,
        )
    log.debug("hardware profile: %s", prof)
    _CACHED = prof
    return prof


def invalidate_hardware_cache() -> None:
    global _CACHED
    _CACHED = None


def estimate_available_ram_gb() -> float:
    """Return an estimate of system RAM in GB (best effort, works on win32/posix)."""
    try:
        import os

        if os.name == "nt":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            m = MEMORYSTATUSEX()
            m.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(m)):
                return m.ullAvailablePhys / (1024 ** 3)
    except OSError:
        pass

    try:
        import psutil

        return float(psutil.virtual_memory().available) / (1024 ** 3)
    except ImportError:
        pass

    return 4.0  # conservative default


def bytes_to_megapixels(nbytes: int) -> float:
    return nbytes / (1024.0 ** 2)