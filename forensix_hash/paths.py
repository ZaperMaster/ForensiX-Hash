"""Rutas que la app acepta: solo unidades locales del equipo.

Las evidencias y los informes se eligen libremente, pero siempre en una unidad
local (C:, D:, un pendrive...). Se rechazan las rutas de red (\\\\servidor\\recurso,
unidades de red mapeadas): abrirlas haría que Windows se autentique contra ese
servidor y le entregue el hash NTLM del usuario.
"""

import ctypes
import os
import string

DRIVE_REMOTE = 4


def local_roots() -> list[str]:
    """Raíces de las unidades locales: ['C:\\\\', 'D:\\\\', ...] en Windows o ['/'] en Linux."""

    if os.name != "nt":
        return ["/"]
    roots = []
    for letter in string.ascii_uppercase:
        root = f"{letter}:\\"
        try:
            kind = ctypes.windll.kernel32.GetDriveTypeW(root)
        except (AttributeError, OSError):
            kind = 0
        if kind > 1 and kind != DRIVE_REMOTE:  # 0 desconocida, 1 no existe, 4 de red
            roots.append(root)
    return roots


def local_path(text: str) -> str:
    """Ruta absoluta y normalizada, solo si está en una unidad local."""

    text = str(text or "").strip().strip('"')
    if not text:
        raise ValueError("Falta la ruta.")
    path = os.path.normpath(os.path.abspath(os.path.expanduser(text)))
    folded = os.path.normcase(path)
    if not any(folded.startswith(os.path.normcase(root)) for root in local_roots()):
        raise ValueError("Solo se admiten rutas de unidades locales (no rutas de red).")
    return path
