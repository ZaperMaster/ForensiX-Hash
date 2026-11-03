"""Cálculo de varios hashes a la vez sobre un mismo flujo de datos.

Cada algoritmo se calcula en su propio hilo: hashlib libera el GIL con bloques
grandes, así que MD5, SHA-1 y SHA-256 se calculan en paralelo mientras se lee el
siguiente bloque. Los hilos se reutilizan entre archivos para que hashear miles
de archivos pequeños no cueste un hilo por archivo.
"""

import hashlib
from queue import Queue
from threading import Event, Thread

# Nombre interno -> (nombre para mostrar, constructor de hashlib)
ALGORITHMS = {
    "md5": "MD5",
    "sha1": "SHA-1",
    "sha256": "SHA-256",
    "sha512": "SHA-512",
    "sha3_256": "SHA3-256",
    "blake2b": "BLAKE2b",
}
DEFAULT_ALGORITHMS = ("md5", "sha1", "sha256")
CHUNK_SIZE = 4 * 1024 * 1024  # Múltiplo de cualquier tamaño de sector (512, 4096)

_FINISH = object()
_STOP = object()


class Cancelled(Exception):
    """El usuario canceló la operación."""


def normalize_algorithms(algorithms) -> tuple[str, ...]:
    """Valida y ordena los algoritmos pedidos (sin repetidos, orden de ALGORITHMS)."""

    requested = {str(a).lower().replace("-", "") for a in (algorithms or DEFAULT_ALGORITHMS)}
    requested = {"sha3_256" if a in {"sha3256", "sha3_256"} else a for a in requested}
    unknown = requested - ALGORITHMS.keys()
    if unknown:
        raise ValueError(f"Algoritmo no soportado: {', '.join(sorted(unknown))}")
    if not requested:
        raise ValueError("Elige al menos un algoritmo.")
    return tuple(a for a in ALGORITHMS if a in requested)


class _Worker(Thread):
    def __init__(self, algorithm: str):
        super().__init__(daemon=True, name=f"hash-{algorithm}")
        self.algorithm = algorithm
        self.inbox: Queue = Queue(maxsize=8)
        self.results: Queue = Queue()

    def run(self) -> None:
        digest = hashlib.new(self.algorithm)
        while True:
            item = self.inbox.get()
            if item is _STOP:
                return
            if item is _FINISH:
                self.results.put(digest.hexdigest())
                digest = hashlib.new(self.algorithm)
            else:
                digest.update(item)


class MultiHasher:
    """Calcula varios algoritmos a la vez. Uso:

        with MultiHasher(["md5", "sha256"]) as hasher:
            hasher.update(b"...")
            hashes = hasher.digest()   # y queda listo para el siguiente flujo
    """

    def __init__(self, algorithms):
        self.algorithms = normalize_algorithms(algorithms)
        self._workers = [_Worker(a) for a in self.algorithms]
        for worker in self._workers:
            worker.start()

    def update(self, data: bytes) -> None:
        if data:
            for worker in self._workers:
                worker.inbox.put(data)

    def digest(self) -> dict[str, str]:
        for worker in self._workers:
            worker.inbox.put(_FINISH)
        return {worker.algorithm: worker.results.get() for worker in self._workers}

    def close(self) -> None:
        for worker in self._workers:
            worker.inbox.put(_STOP)
        for worker in self._workers:
            worker.join(timeout=5)

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def check_cancel(cancel: Event | None) -> None:
    if cancel is not None and cancel.is_set():
        raise Cancelled()


def hash_bytes(data: bytes, algorithms=DEFAULT_ALGORITHMS) -> dict[str, str]:
    """Hashes de unos bytes en memoria (para tests y comprobaciones rápidas)."""

    return {a: hashlib.new(a, data).hexdigest() for a in normalize_algorithms(algorithms)}
