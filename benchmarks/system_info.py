"""Native Windows process peak working set and physical RAM, without extra dependencies."""

import ctypes
import platform
from ctypes import wintypes


class _MemoryStatus(ctypes.Structure):
    _fields_ = [
        ("length", wintypes.DWORD),
        ("load", wintypes.DWORD),
        ("total_physical", ctypes.c_ulonglong),
        ("available_physical", ctypes.c_ulonglong),
        ("total_page", ctypes.c_ulonglong),
        ("available_page", ctypes.c_ulonglong),
        ("total_virtual", ctypes.c_ulonglong),
        ("available_virtual", ctypes.c_ulonglong),
        ("available_extended", ctypes.c_ulonglong),
    ]


class _ProcessCounters(ctypes.Structure):
    _fields_ = [
        ("cb", wintypes.DWORD),
        ("page_faults", wintypes.DWORD),
        ("peak_working_set", ctypes.c_size_t),
        ("working_set", ctypes.c_size_t),
        ("peak_paged_pool", ctypes.c_size_t),
        ("paged_pool", ctypes.c_size_t),
        ("peak_nonpaged_pool", ctypes.c_size_t),
        ("nonpaged_pool", ctypes.c_size_t),
        ("pagefile", ctypes.c_size_t),
        ("peak_pagefile", ctypes.c_size_t),
    ]


def memory_snapshot() -> dict[str, int | str | None]:
    if platform.system() != "Windows":
        return {
            "method": "NOT MEASURED: native probe implemented for Windows only",
            "peak_working_set_bytes": None,
            "available_physical_bytes": None,
        }
    status = _MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    process = _ProcessCounters()
    process.cb = ctypes.sizeof(process)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.c_void_p(-1), ctypes.byref(process), ctypes.sizeof(process)
    ):
        raise OSError("GetProcessMemoryInfo failed")
    return {
        "method": "Windows GetProcessMemoryInfo PeakWorkingSetSize; process lifetime incl imports",
        "peak_working_set_bytes": int(process.peak_working_set),
        "working_set_bytes": int(process.working_set),
        "total_physical_bytes": int(status.total_physical),
        "available_physical_bytes": int(status.available_physical),
    }
