"""Local Windows DPAPI vault; user-bound ciphertext only is persisted."""

from __future__ import annotations

import ctypes
import json
import os
import re
from pathlib import Path
from typing import Protocol
from uuid import uuid4


class CredentialVault(Protocol):
    def store(self, login: str, password: str) -> str: ...
    def load(self, reference: str) -> tuple[str, str]: ...
    def delete(self, reference: str) -> None: ...


class _Blob(ctypes.Structure):
    _fields_ = [("length", ctypes.c_uint32), ("data", ctypes.POINTER(ctypes.c_ubyte))]


def _crypt(payload: bytes, *, decrypt: bool) -> bytes:
    if os.name != "nt":
        raise RuntimeError("WINDOWS_CREDENTIAL_VAULT_UNAVAILABLE")
    buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
    source = _Blob(len(payload), buffer)
    target = _Blob()
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    operation = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    operation.argtypes = [
        ctypes.POINTER(_Blob),
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_void_p,
        ctypes.c_uint32,
        ctypes.POINTER(_Blob),
    ]
    operation.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    # CRYPTPROTECT_UI_FORBIDDEN; no machine-wide key scope.
    if not operation(ctypes.byref(source), None, None, None, None, 1, ctypes.byref(target)):
        raise RuntimeError("CREDENTIAL_VAULT_OPERATION_FAILED")
    try:
        return ctypes.string_at(target.data, target.length)
    finally:
        kernel32.LocalFree(target.data)


class WindowsCredentialVault:
    def __init__(self, root: Path) -> None:
        self.root = root

    def _path(self, reference: str) -> Path:
        if re.fullmatch(r"credential-[0-9a-f]{32}", reference) is None:
            raise ValueError("INVALID_CREDENTIAL_REFERENCE")
        return self.root / (reference + ".dpapi")

    def store(self, login: str, password: str) -> str:
        encrypted = _crypt(json.dumps([login, password]).encode(), decrypt=False)
        reference = "credential-" + uuid4().hex
        self.root.mkdir(parents=True, exist_ok=True)
        with self._path(reference).open("xb") as stream:
            stream.write(encrypted)
            stream.flush()
            os.fsync(stream.fileno())
        return reference

    def load(self, reference: str) -> tuple[str, str]:
        result = json.loads(_crypt(self._path(reference).read_bytes(), decrypt=True))
        if (
            not isinstance(result, list)
            or len(result) != 2
            or not all(isinstance(x, str) for x in result)
        ):
            raise RuntimeError("CREDENTIAL_VAULT_RECORD_INVALID")
        return result[0], result[1]

    def delete(self, reference: str) -> None:
        self._path(reference).unlink(missing_ok=True)
