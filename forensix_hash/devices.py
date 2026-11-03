"""Discos y volúmenes del equipo: listado, tamaño real y apertura en solo lectura.

En Windows los discos se leen como \\\\.\\PhysicalDriveN (disco entero) o \\\\.\\X:
(un volumen); hace falta ejecutar como administrador. En Linux, /dev/sdX.
También se aceptan imágenes de disco (.dd, .raw, .img, .iso...), que son
archivos normales y no necesitan permisos especiales.
"""

import ctypes
import json
import os
import re
import subprocess
import sys
from pathlib import Path

DEFAULT_SECTOR = 512
_PHYSICAL = re.compile(r"^\\\\\.\\PhysicalDrive(\d+)$", re.IGNORECASE)
_VOLUME = re.compile(r"^\\\\\.\\([A-Z]):$", re.IGNORECASE)


def is_admin() -> bool:
    if os.name == "nt":
        try:
            return bool(ctypes.windll.shell32.IsUserAnAdmin())
        except (AttributeError, OSError):
            return False
    return hasattr(os, "geteuid") and os.geteuid() == 0


def is_raw_device(path: str) -> bool:
    if os.name == "nt":
        return bool(_PHYSICAL.match(path) or _VOLUME.match(path))
    return path.startswith("/dev/")


# --- Tamaño y apertura ----------------------------------------------------------

def device_size(path: str) -> tuple[int, int]:
    """(tamaño en bytes, tamaño de sector) de un disco, volumen o imagen."""

    if not is_raw_device(path):
        return Path(path).stat().st_size, DEFAULT_SECTOR
    if os.name == "nt":
        return _windows_device_size(path)
    return _linux_device_size(path)


def open_device(path: str):
    """Abre en solo lectura y sin búfer (las lecturas van directas al disco)."""

    try:
        return open(path, "rb", buffering=0)
    except PermissionError as error:
        if is_raw_device(path) and not is_admin():
            raise PermissionError(
                "Leer un disco completo necesita permisos de administrador."
            ) from error
        raise


def _windows_device_size(path: str) -> tuple[int, int]:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.CreateFileW.restype = wintypes.HANDLE
    kernel32.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                     wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel32.DeviceIoControl.argtypes = [wintypes.HANDLE, wintypes.DWORD, ctypes.c_void_p, wintypes.DWORD,
                                         ctypes.c_void_p, wintypes.DWORD, ctypes.POINTER(wintypes.DWORD),
                                         ctypes.c_void_p]
    kernel32.CloseHandle.argtypes = [wintypes.HANDLE]

    GENERIC_READ, FILE_SHARE_READ_WRITE, OPEN_EXISTING = 0x80000000, 0x3, 3
    IOCTL_DISK_GET_LENGTH_INFO = 0x0007405C
    IOCTL_DISK_GET_DRIVE_GEOMETRY_EX = 0x000700A0
    INVALID_HANDLE = wintypes.HANDLE(-1).value

    handle = kernel32.CreateFileW(path, GENERIC_READ, FILE_SHARE_READ_WRITE, None, OPEN_EXISTING, 0, None)
    if handle in (None, INVALID_HANDLE):
        error = ctypes.get_last_error()
        if error == 5:  # ERROR_ACCESS_DENIED
            raise PermissionError("Leer un disco completo necesita permisos de administrador.")
        raise OSError(error, ctypes.FormatError(error), path)
    try:
        returned = wintypes.DWORD()
        length = ctypes.c_longlong()
        if not kernel32.DeviceIoControl(handle, IOCTL_DISK_GET_LENGTH_INFO, None, 0, ctypes.byref(length),
                                        ctypes.sizeof(length), ctypes.byref(returned), None):
            error = ctypes.get_last_error()
            raise OSError(error, ctypes.FormatError(error), path)

        sector = DEFAULT_SECTOR
        geometry = ctypes.create_string_buffer(256)
        if kernel32.DeviceIoControl(handle, IOCTL_DISK_GET_DRIVE_GEOMETRY_EX, None, 0, geometry,
                                    len(geometry), ctypes.byref(returned), None):
            # DISK_GEOMETRY: Cylinders(8) MediaType(4) TracksPerCylinder(4) SectorsPerTrack(4) BytesPerSector(4)
            sector = int.from_bytes(geometry.raw[20:24], "little") or DEFAULT_SECTOR
        return length.value, sector
    finally:
        kernel32.CloseHandle(handle)


def _linux_device_size(path: str) -> tuple[int, int]:
    with open(path, "rb", buffering=0) as handle:
        size = handle.seek(0, os.SEEK_END)
    name = Path(os.path.realpath(path)).name
    sector_file = Path(f"/sys/class/block/{name}/queue/logical_block_size")
    try:
        sector = int(sector_file.read_text().strip())
    except (OSError, ValueError):
        sector = DEFAULT_SECTOR
    return size, sector


# --- Listado ---------------------------------------------------------------------

_WINDOWS_QUERY = r"""
$ErrorActionPreference = 'SilentlyContinue'
$parts = @(Get-Partition | Where-Object DriveLetter | Select-Object DiskNumber, @{n='Letter';e={[string]$_.DriveLetter}})
$vols = @(Get-Volume | Where-Object DriveLetter | Select-Object @{n='Letter';e={[string]$_.DriveLetter}}, FileSystemLabel, FileSystem, Size)
$disks = @(Get-Disk | Select-Object Number, FriendlyName, SerialNumber, BusType, Size, PartitionStyle,
    IsBoot, IsSystem, IsReadOnly, LogicalSectorSize, PhysicalSectorSize, @{n='Bus';e={[string]$_.BusType}},
    @{n='Style';e={[string]$_.PartitionStyle}})
@{ disks = $disks; partitions = $parts; volumes = $vols } | ConvertTo-Json -Depth 4 -Compress
"""


def list_devices() -> list[dict]:
    """Discos físicos con sus volúmenes (letra, etiqueta, sistema de archivos)."""

    if os.name == "nt":
        return _list_windows()
    if sys.platform.startswith("linux"):
        return _list_linux()
    return []


def _list_windows() -> list[dict]:
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", _WINDOWS_QUERY],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        data = json.loads(completed.stdout or "{}")
    except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
        return []

    def as_list(value):
        return value if isinstance(value, list) else ([value] if value else [])

    volumes = {v["Letter"]: v for v in as_list(data.get("volumes"))}
    letters_by_disk: dict[int, list[str]] = {}
    for part in as_list(data.get("partitions")):
        letters_by_disk.setdefault(part["DiskNumber"], []).append(part["Letter"])

    devices = []
    for disk in sorted(as_list(data.get("disks")), key=lambda d: d["Number"]):
        number = disk["Number"]
        vols = []
        for letter in sorted(letters_by_disk.get(number, [])):
            info = volumes.get(letter, {})
            vols.append({
                "path": f"\\\\.\\{letter}:",
                "letter": f"{letter}:",
                "label": info.get("FileSystemLabel") or "",
                "filesystem": info.get("FileSystem") or "",
                "size": info.get("Size") or 0,
            })
        devices.append({
            "path": f"\\\\.\\PhysicalDrive{number}",
            "number": number,
            "model": (disk.get("FriendlyName") or "").strip(),
            "serial": (disk.get("SerialNumber") or "").strip(),
            "bus": disk.get("Bus") or "",
            "size": disk.get("Size") or 0,
            "partition_style": disk.get("Style") or "",
            "sector_size": disk.get("LogicalSectorSize") or DEFAULT_SECTOR,
            "system": bool(disk.get("IsBoot") or disk.get("IsSystem")),
            "read_only": bool(disk.get("IsReadOnly")),
            "volumes": vols,
        })
    return devices


def _list_linux() -> list[dict]:
    devices = []
    for block in sorted(Path("/sys/block").glob("*")):
        if block.name.startswith(("loop", "ram", "zram")):
            continue

        def read(name: str, default: str = "") -> str:
            try:
                return (block / name).read_text().strip()
            except OSError:
                return default

        sectors = int(read("size", "0") or 0)
        devices.append({
            "path": f"/dev/{block.name}",
            "number": None,
            "model": read("device/model"),
            "serial": read("device/serial"),
            "bus": "USB" if "usb" in os.path.realpath(block) else "",
            "size": sectors * 512,
            "partition_style": "",
            "sector_size": int(read("queue/logical_block_size", "512") or 512),
            "system": False,
            "read_only": read("ro") == "1",
            "volumes": [{"path": f"/dev/{p.name}", "letter": "", "label": "", "filesystem": "",
                         "size": int((p / "size").read_text().strip() or 0) * 512}
                        for p in sorted(block.glob(f"{block.name}*")) if (p / "size").exists()],
        })
    return devices


def describe_device(path: str) -> dict:
    """Datos del disco o volumen para el informe (modelo, número de serie, bus...)."""

    if not is_raw_device(path):
        info = Path(path).stat()
        return {"kind": "image", "path": str(Path(path).resolve()), "name": Path(path).name, "size": info.st_size}

    for disk in list_devices():
        if disk["path"].lower() == path.lower():
            return {"kind": "disk", **{k: v for k, v in disk.items() if k != "volumes"}, "volumes": disk["volumes"]}
        for volume in disk["volumes"]:
            if volume["path"].lower() == path.lower():
                return {"kind": "volume", **volume, "disk": {k: disk[k] for k in ("path", "model", "serial", "bus", "size")}}
    return {"kind": "disk", "path": path}


def relaunch_as_admin() -> bool:
    """Vuelve a abrir la app pidiendo permisos de administrador (UAC). Windows."""

    if os.name != "nt":
        return False
    if getattr(sys, "frozen", False):
        executable, params = sys.executable, ""
    else:
        executable = sys.executable.replace("python.exe", "pythonw.exe")
        params = "-m desktop"
    workdir = os.getcwd()
    result = ctypes.windll.shell32.ShellExecuteW(None, "runas", executable, params, workdir, 1)
    return result > 32
