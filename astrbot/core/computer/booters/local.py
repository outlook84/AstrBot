from __future__ import annotations

import asyncio
import locale
import os
import shutil
import subprocess
import sys
import venv
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from astrbot.api import logger
from astrbot.core.utils.astrbot_path import (
    get_astrbot_data_path,
    get_astrbot_root,
    get_astrbot_temp_path,
)

from ..olayer import FileSystemComponent, PythonComponent, ShellComponent
from .base import ComputerBooter

if os.name == "posix":
    import pwd

_BLOCKED_COMMAND_PATTERNS = [
    " rm -rf ",
    " rm -fr ",
    " rm -r ",
    " mkfs",
    " dd if=",
    " shutdown",
    " reboot",
    " poweroff",
    " halt",
    " sudo ",
    ":(){:|:&};:",
    " kill -9 ",
    " killall ",
]

_NATIVE_PATH_CLS = type(Path("."))


def _native_path(*segments: str | os.PathLike[str]) -> Path:
    return _NATIVE_PATH_CLS(*segments)


def _is_safe_command(command: str) -> bool:
    cmd = f" {command.strip().lower()} "
    return not any(pat in cmd for pat in _BLOCKED_COMMAND_PATTERNS)


def _get_allowed_roots() -> list[Path]:
    return [
        _native_path(get_astrbot_root()).resolve(),
        _native_path(get_astrbot_data_path()).resolve(),
        _native_path(get_astrbot_temp_path()).resolve(),
    ]


def _ensure_safe_path(path: str | Path, base_dir: str | Path | None = None) -> str:
    candidate = _native_path(path)
    if not candidate.is_absolute():
        if base_dir:
            base_path = _native_path(base_dir).resolve()
        else:
            base_path = _native_path(os.getcwd()).resolve()
        candidate = base_path / candidate
    abs_path = candidate.resolve()
    if not any(
        abs_path == root or root in abs_path.parents for root in _get_allowed_roots()
    ):
        raise PermissionError("Path is outside the allowed computer roots.")
    return str(abs_path)


@dataclass(slots=True)
class LocalRuntimeConfig:
    workspace_path: Path
    venv_path: Path
    execution_timeout: int = 30
    uid: int | None = None
    gid: int | None = None

    @classmethod
    def from_dict(cls, raw: dict[str, Any] | None = None) -> LocalRuntimeConfig:
        local_cfg = raw or {}
        workspace_path = (
            _native_path(get_astrbot_data_path()) / "computer" / "workspace"
        ).resolve()
        venv_path = (workspace_path / ".venv").resolve()

        uid = local_cfg.get("uid")
        gid = local_cfg.get("gid")
        execution_timeout = local_cfg.get("execution_timeout", 30)
        execution_timeout_value = (
            int(execution_timeout) if execution_timeout not in (None, "") else 30
        )
        if execution_timeout_value <= 0:
            raise ValueError("local.execution_timeout must be greater than 0.")
        return cls(
            workspace_path=workspace_path,
            venv_path=venv_path,
            execution_timeout=execution_timeout_value,
            uid=int(uid) if uid not in (None, "") else None,
            gid=int(gid) if gid not in (None, "") else None,
        )

    @property
    def venv_bin_dir(self) -> Path:
        return self.venv_path / ("Scripts" if os.name == "nt" else "bin")

    @property
    def python_executable(self) -> str:
        name = "python.exe" if os.name == "nt" else "python"
        return str(self.venv_bin_dir / name)


def _assert_identity_switch_allowed(uid: int | None, gid: int | None) -> None:
    if os.name != "posix" or (uid is None and gid is None):
        return

    current_uid = os.getuid()
    current_gid = os.getgid()
    if uid not in (None, current_uid) and os.geteuid() != 0:
        raise PermissionError("Configured local uid requires running AstrBot as root.")
    if gid not in (None, current_gid) and os.geteuid() != 0:
        raise PermissionError("Configured local gid requires running AstrBot as root.")


def _build_identity_preexec(uid: int | None, gid: int | None) -> Any | None:
    if os.name != "posix" or (uid is None and gid is None):
        return None
    current_uid = os.getuid()
    current_gid = os.getgid()
    if uid in (None, current_uid) and gid in (None, current_gid):
        return None
    _assert_identity_switch_allowed(uid, gid)

    def _set_identity() -> None:
        if uid is not None:
            try:
                user_entry = pwd.getpwuid(uid)
            except KeyError:
                user_entry = None
            if user_entry is not None:
                os.initgroups(user_entry.pw_name, gid or user_entry.pw_gid)
            elif gid is not None:
                os.setgroups([gid])
            else:
                os.setgroups([])
        elif gid is not None:
            os.setgroups([gid])
        if gid is not None:
            os.setgid(gid)
        if uid is not None:
            os.setuid(uid)

    return _set_identity


def _permission_hint(message: str, target: Path) -> PermissionError:
    return PermissionError(
        f"{message}: {target}. "
        "Please pre-create the path with the required permissions, or leave uid/gid empty to use the AstrBot process user."
    )


def _run_with_identity(
    command: list[str],
    uid: int | None,
    gid: int | None,
    error_message: str,
    target: Path,
    treat_any_failure_as_permission: bool = False,
) -> None:
    preexec_fn = _build_identity_preexec(uid, gid)
    try:
        subprocess.run(
            command,
            check=True,
            capture_output=True,
            text=True,
            preexec_fn=preexec_fn,
        )
    except PermissionError as exc:
        raise _permission_hint(error_message, target) from exc
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").lower()
        if (
            treat_any_failure_as_permission
            or "permission denied" in stderr
            or "permissionerror" in stderr
        ):
            raise _permission_hint(error_message, target) from exc
        raise RuntimeError(
            f"{error_message}: {target}. {exc.stderr.strip() or exc.stdout.strip() or exc}"
        ) from exc


def _verify_path_access(
    path: Path,
    uid: int | None,
    gid: int | None,
    error_message: str,
    mode: str,
) -> None:
    if os.name != "posix" or (uid is None and gid is None):
        return
    _run_with_identity(
        [
            sys.executable,
            "-c",
            (
                "import os, sys; "
                "target=sys.argv[1]; "
                "mode=int(sys.argv[2]); "
                "raise SystemExit(0 if os.access(target, mode) else 1)"
            ),
            str(path),
            str(mode),
        ],
        uid,
        gid,
        error_message,
        path,
        treat_any_failure_as_permission=True,
    )


def _verify_python_access(
    python_executable: Path,
    workspace_path: Path,
    uid: int | None,
    gid: int | None,
) -> None:
    if os.name != "posix" or (uid is None and gid is None):
        return
    _run_with_identity(
        [str(python_executable), "-c", "print('astrbot-local-runtime-ok')"],
        uid,
        gid,
        "Local runtime cannot access venv_path",
        python_executable,
    )
    _verify_path_access(
        workspace_path,
        uid,
        gid,
        "Local runtime cannot access workspace_path",
        os.R_OK | os.W_OK | os.X_OK,
    )


def _build_runtime_env(
    runtime: LocalRuntimeConfig, env: dict[str, str] | None = None
) -> dict[str, str]:
    run_env = os.environ.copy()
    run_env["VIRTUAL_ENV"] = str(runtime.venv_path)
    run_env["HOME"] = str(runtime.workspace_path)
    run_env["XDG_CACHE_HOME"] = str(runtime.workspace_path / ".cache")
    run_env["XDG_CONFIG_HOME"] = str(runtime.workspace_path / ".config")
    run_env["XDG_DATA_HOME"] = str(runtime.workspace_path / ".local" / "share")
    run_env["PIP_CACHE_DIR"] = str(runtime.workspace_path / ".cache" / "pip")
    extra_path = str(env["PATH"]) if env and "PATH" in env else ""
    run_env["PATH"] = os.pathsep.join(
        [str(runtime.venv_bin_dir), run_env.get("PATH", ""), extra_path]
    ).strip(os.pathsep)
    run_env["ASTRBOT_LOCAL_WORKSPACE"] = str(runtime.workspace_path)
    run_env["ASTRBOT_LOCAL_VENV_PATH"] = str(runtime.venv_path)
    run_env["ASTRBOT_LOCAL_VENV_BIN"] = str(runtime.venv_bin_dir)
    run_env["ASTRBOT_LOCAL_PYTHON"] = runtime.python_executable
    if env:
        safe_env = {
            str(k): str(v)
            for k, v in env.items()
            if str(k)
            not in {
                "PATH",
                "VIRTUAL_ENV",
                "HOME",
                "XDG_CACHE_HOME",
                "XDG_CONFIG_HOME",
                "XDG_DATA_HOME",
                "PIP_CACHE_DIR",
                "ASTRBOT_LOCAL_WORKSPACE",
                "ASTRBOT_LOCAL_VENV_PATH",
                "ASTRBOT_LOCAL_VENV_BIN",
                "ASTRBOT_LOCAL_PYTHON",
            }
        }
        run_env.update(safe_env)
    return run_env


def _decode_bytes_with_fallback(
    output: bytes | None,
    *,
    preferred_encoding: str | None = None,
) -> str:
    if output is None:
        return ""
    if isinstance(output, str):
        return output

    preferred = locale.getpreferredencoding(False) or "utf-8"
    attempted_encodings: list[str] = []

    def _try_decode(encoding: str) -> str | None:
        normalized = encoding.lower()
        if normalized in attempted_encodings:
            return None
        attempted_encodings.append(normalized)
        try:
            return output.decode(encoding)
        except (LookupError, UnicodeDecodeError):
            return None

    for encoding in filter(None, [preferred_encoding, "utf-8", "utf-8-sig"]):
        if decoded := _try_decode(encoding):
            return decoded

    if os.name == "nt":
        for encoding in ("mbcs", "cp936", "gbk", "gb18030", preferred):
            if decoded := _try_decode(encoding):
                return decoded
    elif decoded := _try_decode(preferred):
        return decoded

    return output.decode("utf-8", errors="replace")


def _decode_shell_output(output: bytes | None) -> str:
    return _decode_bytes_with_fallback(output, preferred_encoding="utf-8")


@dataclass
class LocalShellComponent(ShellComponent):
    runtime: LocalRuntimeConfig = field(
        default_factory=lambda: LocalRuntimeConfig.from_dict({})
    )

    async def exec(
        self,
        command: str,
        cwd: str | None = None,
        env: dict[str, str] | None = None,
        timeout: int | None = None,
        shell: bool = True,
        background: bool = False,
    ) -> dict[str, Any]:
        if not _is_safe_command(command):
            raise PermissionError("Blocked unsafe shell command.")

        def _run() -> dict[str, Any]:
            run_env = _build_runtime_env(self.runtime, env)
            working_dir = (
                _ensure_safe_path(cwd, base_dir=self.runtime.workspace_path)
                if cwd
                else str(self.runtime.workspace_path)
            )
            preexec_fn = _build_identity_preexec(self.runtime.uid, self.runtime.gid)
            if background:
                try:
                    # `command` is intentionally executed through the current shell so
                    # local computer-use behavior matches existing tool semantics.
                    # Safety relies on `_is_safe_command()` and the allowed-root checks.
                    proc = subprocess.Popen(  # noqa: S602  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
                        command,
                        shell=shell,
                        cwd=working_dir,
                        env=run_env,
                        preexec_fn=preexec_fn,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                except PermissionError as exc:
                    raise _permission_hint(
                        "Local runtime cannot start shell process",
                        _native_path(working_dir),
                    ) from exc
                return {"pid": proc.pid, "stdout": "", "stderr": "", "exit_code": None}
            effective_timeout = (
                self.runtime.execution_timeout if timeout is None else timeout
            )
            try:
                # `command` is intentionally executed through the current shell so
                # local computer-use behavior matches existing tool semantics.
                # Safety relies on `_is_safe_command()` and the allowed-root checks.
                result = subprocess.run(  # noqa: S602  # nosemgrep: python.lang.security.audit.dangerous-subprocess-use-audit
                    command,
                    shell=shell,
                    cwd=working_dir,
                    env=run_env,
                    timeout=effective_timeout,
                    preexec_fn=preexec_fn,
                    capture_output=True,
                )
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot start shell process",
                    _native_path(working_dir),
                ) from exc
            return {
                "stdout": _decode_shell_output(result.stdout),
                "stderr": _decode_shell_output(result.stderr),
                "exit_code": result.returncode,
            }

        return await asyncio.to_thread(_run)


@dataclass
class LocalPythonComponent(PythonComponent):
    runtime: LocalRuntimeConfig

    async def exec(
        self,
        code: str,
        kernel_id: str | None = None,
        timeout: int | None = None,
        silent: bool = False,
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            try:
                run_env = _build_runtime_env(self.runtime)
                effective_timeout = (
                    self.runtime.execution_timeout if timeout is None else timeout
                )
                try:
                    result = subprocess.run(
                        [self.runtime.python_executable, "-c", code],
                        timeout=effective_timeout,
                        capture_output=True,
                        text=True,
                        cwd=str(self.runtime.workspace_path),
                        env=run_env,
                        preexec_fn=_build_identity_preexec(
                            self.runtime.uid, self.runtime.gid
                        ),
                    )
                except PermissionError as exc:
                    raise _permission_hint(
                        "Local runtime cannot start python process",
                        self.runtime.workspace_path,
                    ) from exc
                stdout = "" if silent else result.stdout
                stderr = result.stderr if result.returncode != 0 else ""
                return {
                    "data": {
                        "output": {"text": stdout, "images": []},
                        "error": stderr,
                    }
                }
            except subprocess.TimeoutExpired:
                return {
                    "data": {
                        "output": {"text": "", "images": []},
                        "error": "Execution timed out.",
                    }
                }

        return await asyncio.to_thread(_run)


@dataclass
class LocalFileSystemComponent(FileSystemComponent):
    runtime: LocalRuntimeConfig = field(
        default_factory=lambda: LocalRuntimeConfig.from_dict({})
    )

    async def create_file(
        self, path: str, content: str = "", mode: int = 0o644
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            abs_path = _native_path(
                _ensure_safe_path(path, base_dir=self.runtime.workspace_path)
            )
            try:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot create parent directory", abs_path.parent
                ) from exc
            try:
                with abs_path.open("w", encoding="utf-8") as f:
                    f.write(content)
                os.chmod(abs_path, mode)
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot write file", abs_path
                ) from exc
            return {"success": True, "path": str(abs_path)}

        return await asyncio.to_thread(_run)

    async def read_file(self, path: str, encoding: str = "utf-8") -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            abs_path = _native_path(
                _ensure_safe_path(path, base_dir=self.runtime.workspace_path)
            )
            try:
                with abs_path.open("rb") as f:
                    raw_content = f.read()
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot read file", abs_path
                ) from exc
            content = _decode_bytes_with_fallback(
                raw_content,
                preferred_encoding=encoding,
            )
            return {"success": True, "content": content}

        return await asyncio.to_thread(_run)

    async def write_file(
        self, path: str, content: str, mode: str = "w", encoding: str = "utf-8"
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            abs_path = _native_path(
                _ensure_safe_path(path, base_dir=self.runtime.workspace_path)
            )
            try:
                abs_path.parent.mkdir(parents=True, exist_ok=True)
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot create parent directory", abs_path.parent
                ) from exc
            try:
                with abs_path.open(mode, encoding=encoding) as f:
                    f.write(content)
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot write file", abs_path
                ) from exc
            return {"success": True, "path": str(abs_path)}

        return await asyncio.to_thread(_run)

    async def delete_file(self, path: str) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            abs_path = _native_path(
                _ensure_safe_path(path, base_dir=self.runtime.workspace_path)
            )
            try:
                if abs_path.is_dir():
                    shutil.rmtree(abs_path)
                else:
                    abs_path.unlink()
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot delete path", abs_path
                ) from exc
            return {"success": True, "path": str(abs_path)}

        return await asyncio.to_thread(_run)

    async def list_dir(
        self, path: str = ".", show_hidden: bool = False
    ) -> dict[str, Any]:
        def _run() -> dict[str, Any]:
            abs_path = _native_path(
                _ensure_safe_path(path, base_dir=self.runtime.workspace_path)
            )
            try:
                entries = os.listdir(abs_path)
            except PermissionError as exc:
                raise _permission_hint(
                    "Local runtime cannot list directory", abs_path
                ) from exc
            if not show_hidden:
                entries = [e for e in entries if not e.startswith(".")]
            return {"success": True, "entries": entries}

        return await asyncio.to_thread(_run)


class LocalBooter(ComputerBooter):
    def __init__(self, config: dict[str, Any] | None = None) -> None:
        self._runtime = LocalRuntimeConfig.from_dict(config)
        self._fs = LocalFileSystemComponent(self._runtime)
        self._python = LocalPythonComponent(self._runtime)
        self._shell = LocalShellComponent(self._runtime)

    async def boot(self, session_id: str) -> None:
        await asyncio.to_thread(self._ensure_runtime_ready)
        logger.info(f"Local computer booter initialized for session: {session_id}")

    async def shutdown(self) -> None:
        logger.info("Local computer booter shutdown complete.")

    @property
    def fs(self) -> FileSystemComponent:
        return self._fs

    @property
    def python(self) -> PythonComponent:
        return self._python

    @property
    def shell(self) -> ShellComponent:
        return self._shell

    async def upload_file(self, path: str, file_name: str) -> dict:
        raise NotImplementedError(
            "LocalBooter does not support upload_file operation. Use shell instead."
        )

    async def download_file(self, remote_path: str, local_path: str) -> None:
        raise NotImplementedError(
            "LocalBooter does not support download_file operation. Use shell instead."
        )

    async def available(self) -> bool:
        return True

    @property
    def runtime(self) -> LocalRuntimeConfig:
        return self._runtime

    def _ensure_runtime_ready(self) -> None:
        if not self._runtime.workspace_path.exists():
            if os.name == "posix" and (
                self._runtime.uid is not None or self._runtime.gid is not None
            ):
                _run_with_identity(
                    [
                        sys.executable,
                        "-c",
                        (
                            "from pathlib import Path; import sys; "
                            "Path(sys.argv[1]).mkdir(parents=True, exist_ok=True)"
                        ),
                        str(self._runtime.workspace_path),
                    ],
                    self._runtime.uid,
                    self._runtime.gid,
                    "Local runtime cannot create workspace_path",
                    self._runtime.workspace_path,
                )
            else:
                try:
                    self._runtime.workspace_path.mkdir(parents=True, exist_ok=True)
                except PermissionError as exc:
                    raise _permission_hint(
                        "Local runtime cannot create workspace_path",
                        self._runtime.workspace_path,
                    ) from exc
        _verify_path_access(
            self._runtime.workspace_path,
            self._runtime.uid,
            self._runtime.gid,
            "Local runtime cannot access workspace_path",
            os.R_OK | os.W_OK | os.X_OK,
        )
        if not _native_path(self._runtime.python_executable).exists():
            logger.info("Creating local computer venv at %s", self._runtime.venv_path)
            if os.name == "posix" and (
                self._runtime.uid is not None or self._runtime.gid is not None
            ):
                _run_with_identity(
                    [sys.executable, "-m", "venv", str(self._runtime.venv_path)],
                    self._runtime.uid,
                    self._runtime.gid,
                    "Local runtime cannot create venv_path",
                    self._runtime.venv_path,
                )
            else:
                try:
                    venv.EnvBuilder(with_pip=True).create(str(self._runtime.venv_path))
                except PermissionError as exc:
                    raise _permission_hint(
                        "Local runtime cannot create venv_path", self._runtime.venv_path
                    ) from exc
        _verify_python_access(
            _native_path(self._runtime.python_executable),
            self._runtime.workspace_path,
            self._runtime.uid,
            self._runtime.gid,
        )
