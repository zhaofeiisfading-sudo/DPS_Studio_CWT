"""Native Windows RAM probes. Peaks refer to one worker's entire lifetime."""

import ctypes
import platform
from ctypes import wintypes


class _MemoryStatus(ctypes.Structure):
    _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD)] + [
        (name, ctypes.c_ulonglong)
        for name in (
            "total_physical",
            "available_physical",
            "total_page",
            "available_page",
            "total_virtual",
            "available_virtual",
            "available_extended",
        )
    ]


class _ProcessCounters(ctypes.Structure):
    _fields_ = [("cb", wintypes.DWORD), ("page_faults", wintypes.DWORD)] + [
        (name, ctypes.c_size_t)
        for name in (
            "peak_working_set",
            "working_set",
            "peak_paged_pool",
            "paged_pool",
            "peak_nonpaged_pool",
            "nonpaged_pool",
            "pagefile",
            "peak_pagefile",
        )
    ]


def memory_snapshot() -> dict[str, int | str | None]:
    if platform.system() != "Windows":
        return {
            "method": "NOT MEASURED: Windows native probe only",
            "peak_working_set_bytes": None,
            "available_physical_bytes": None,
        }
    status = _MemoryStatus()
    status.length = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise OSError("GlobalMemoryStatusEx failed")
    counters = _ProcessCounters()
    counters.cb = ctypes.sizeof(counters)
    if not ctypes.windll.psapi.GetProcessMemoryInfo(
        ctypes.c_void_p(-1), ctypes.byref(counters), ctypes.sizeof(counters)
    ):
        raise OSError("GetProcessMemoryInfo failed")
    return {
        "method": "Windows PeakWorkingSetSize; fresh worker lifetime incl imports/plots/CSV",
        "peak_working_set_bytes": int(counters.peak_working_set),
        "working_set_bytes": int(counters.working_set),
        "available_physical_bytes": int(status.available_physical),
        "total_physical_bytes": int(status.total_physical),
    }
