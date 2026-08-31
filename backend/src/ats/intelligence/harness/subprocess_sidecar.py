"""Pinned DeepSeek Harness ACP subprocess with bounded NDJSON queues."""

from __future__ import annotations

import json
import os
import subprocess
import threading
from collections import defaultdict
from collections.abc import Mapping
from queue import Empty, Full, Queue
from typing import Any

from pydantic import SecretStr

from .models import HarnessRuntimeConfiguration, HarnessRuntimeError

_ALLOWED_ENVIRONMENT = (
    "APPDATA",
    "COMSPEC",
    "HOMEDRIVE",
    "HOMEPATH",
    "LOCALAPPDATA",
    "NODE_PATH",
    "PATH",
    "PATHEXT",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "WINDIR",
)
_ALLOWED_CREDENTIAL_ENVIRONMENT = frozenset({"DEEPSEEK_API_KEY", "OPENROUTER_API_KEY"})


class AcpSubprocessSidecar:
    """One local ACP process. Stdout is protocol-only; stderr is never surfaced."""

    def __init__(
        self,
        configuration: HarnessRuntimeConfiguration,
        *,
        credential_environment: Mapping[str, SecretStr] | None = None,
    ) -> None:
        self._configuration = configuration
        supplied = dict(credential_environment or {})
        if not set(supplied).issubset(_ALLOWED_CREDENTIAL_ENVIRONMENT):
            raise ValueError("unsupported Harness credential environment name")
        self._credential_environment = supplied
        self._process: subprocess.Popen[str] | None = None
        self._frames: Queue[dict[str, Any]] = Queue(maxsize=configuration.maximum_pending_frames)
        self._writer_lock = threading.Lock()
        self._request_lock = threading.Lock()
        self._next_id = 1
        self._updates: dict[str, list[str]] = defaultdict(list)
        self._reader: threading.Thread | None = None
        self._protocol_fault = False

    def start(self) -> None:
        if self.healthy():
            raise HarnessRuntimeError("ALREADY_RUNNING")
        environment = {
            key: value for key in _ALLOWED_ENVIRONMENT if (value := os.environ.get(key)) is not None
        }
        environment["DSH_PERMISSION_MODE"] = "read-only"
        environment.update(
            {key: value.get_secret_value() for key, value in self._credential_environment.items()}
        )
        creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
        try:
            self._process = subprocess.Popen(
                self._configuration.command,
                cwd=self._configuration.cwd,
                env=environment,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                encoding="utf-8",
                bufsize=1,
                creationflags=creation_flags,
            )
        except OSError as error:
            raise HarnessRuntimeError("PROCESS_START_FAILED") from error
        self._reader = threading.Thread(target=self._read_frames, daemon=True)
        self._reader.start()
        result = self._request(
            "initialize",
            {
                "protocolVersion": self._configuration.acp_protocol_version,
                "clientCapabilities": {},
            },
            self._configuration.startup_timeout_ms,
        )
        if result.get("protocolVersion") != self._configuration.acp_protocol_version:
            self.stop()
            raise HarnessRuntimeError("ACP_VERSION_MISMATCH")

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None:
            return
        if process.stdin is not None:
            process.stdin.close()
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=2)

    def healthy(self) -> bool:
        return (
            self._process is not None and self._process.poll() is None and not self._protocol_fault
        )

    def create_session(self, *, cwd: str) -> str:
        result = self._request(
            "session/new",
            {"cwd": os.path.abspath(cwd), "mcpServers": []},
            self._configuration.request_timeout_ms,
        )
        session_id = result.get("sessionId")
        if not isinstance(session_id, str) or not session_id:
            raise HarnessRuntimeError("MALFORMED_SESSION_RESPONSE")
        return session_id

    def prompt(self, *, provider_session_id: str, prompt: str) -> str:
        self._updates[provider_session_id].clear()
        self._request(
            "session/prompt",
            {
                "sessionId": provider_session_id,
                "prompt": [{"type": "text", "text": prompt}],
            },
            self._configuration.request_timeout_ms,
        )
        return "".join(self._updates.pop(provider_session_id, []))

    def cancel(self, *, provider_session_id: str) -> None:
        self._notify("session/cancel", {"sessionId": provider_session_id})

    def _request(self, method: str, params: dict[str, object], timeout_ms: int) -> dict[str, Any]:
        with self._request_lock:
            request_id = self._next_id
            self._next_id += 1
            self._write({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
            while True:
                try:
                    frame = self._frames.get(timeout=timeout_ms / 1000)
                except Empty as error:
                    raise TimeoutError("Harness ACP response timed out") from error
                if frame.get("id") != request_id:
                    continue
                if "error" in frame:
                    raise HarnessRuntimeError("ACP_REQUEST_REJECTED")
                result = frame.get("result")
                if not isinstance(result, dict):
                    raise HarnessRuntimeError("MALFORMED_ACP_RESPONSE")
                return result

    def _notify(self, method: str, params: dict[str, object]) -> None:
        self._write({"jsonrpc": "2.0", "method": method, "params": params})

    def _write(self, frame: dict[str, object]) -> None:
        process = self._process
        if process is None or process.stdin is None or process.poll() is not None:
            raise HarnessRuntimeError("PROCESS_NOT_RUNNING")
        encoded = json.dumps(frame, separators=(",", ":"), ensure_ascii=False)
        with self._writer_lock:
            try:
                process.stdin.write(encoded + "\n")
                process.stdin.flush()
            except OSError as error:
                raise HarnessRuntimeError("ACP_WRITE_FAILED") from error

    def _read_frames(self) -> None:
        process = self._process
        if process is None or process.stdout is None:
            self._protocol_fault = True
            return
        for line in process.stdout:
            try:
                frame = json.loads(line)
                if not isinstance(frame, dict):
                    raise ValueError
                if frame.get("method") == "session/update":
                    self._record_update(frame)
                    continue
                self._frames.put_nowait(frame)
            except (ValueError, json.JSONDecodeError, Full):
                self._protocol_fault = True
                return

    def _record_update(self, frame: dict[str, Any]) -> None:
        params = frame.get("params")
        if not isinstance(params, dict):
            raise ValueError
        session_id = params.get("sessionId")
        update = params.get("update")
        if not isinstance(session_id, str) or not isinstance(update, dict):
            raise ValueError
        content = update.get("content")
        if update.get("sessionUpdate") != "agent_message_chunk" or not isinstance(content, dict):
            return
        if content.get("type") == "text" and isinstance(content.get("text"), str):
            self._updates[session_id].append(content["text"])


__all__ = ["AcpSubprocessSidecar"]
