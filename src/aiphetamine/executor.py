"""Fixed resume command construction and injectable process launching."""

from __future__ import annotations

import subprocess
import ctypes
from dataclasses import dataclass
import os
from pathlib import Path
import sys
from typing import Callable, Mapping

from .domain import ResumeLaunchResult, ResumeRequest
from .filesystem_security import (
    open_private_directory,
    open_trusted_directory,
    open_verified_executable,
)


@dataclass(frozen=True)
class ResumeCommandSpec:
    args: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str] | None = None
    expected_cwd_device: int | None = None
    expected_cwd_inode: int | None = None

    @property
    def shell(self) -> bool:
        return False

    @property
    def start_new_session(self) -> bool:
        return True

    @property
    def devnull_streams(self) -> bool:
        return True


class _PosixSpawnProcess:
    """Small Popen-compatible wait handle for the macOS posix_spawn path."""

    def __init__(self, pid: int) -> None:
        self.pid = pid
        self._returncode: int | None = None

    def wait(self) -> int:
        if self._returncode is not None:
            return self._returncode
        while True:
            try:
                _, status = os.waitpid(self.pid, 0)
                self._returncode = os.waitstatus_to_exitcode(status)
                return self._returncode
            except InterruptedError:
                continue


def _ctypes_function(library, name: str, *, restype, argtypes):
    function = getattr(library, name)
    function.restype = restype
    function.argtypes = argtypes
    return function


def _assert_path_matches_descriptor(path: Path, descriptor: int, *, label: str) -> None:
    """Fail closed when the pathname no longer names the validated object."""

    try:
        path_stat = os.stat(path, follow_symlinks=False)
        descriptor_stat = os.fstat(descriptor)
    except OSError as error:
        raise OSError(f"unsafe_{label}") from error
    if (path_stat.st_dev, path_stat.st_ino) != (
        descriptor_stat.st_dev,
        descriptor_stat.st_ino,
    ):
        raise OSError(f"unsafe_{label}")


def _launch_macos_process(spec: ResumeCommandSpec) -> _PosixSpawnProcess:
    """Spawn with macOS's descriptor-relative fchdir file action.

    macOS's ``/dev/fd/N`` cannot be supplied as ``subprocess.Popen(cwd=...)``
    and cannot execute an O_RDONLY descriptor.  ``posix_spawn`` gives us the
    native fchdir action while the executable remains open and validated until
    the spawn call completes.
    """

    libc = ctypes.CDLL(None, use_errno=True)
    void_pointer = ctypes.c_void_p
    pointer = ctypes.POINTER(void_pointer)
    integer = ctypes.c_int
    functions = {
        alias: _ctypes_function(libc, symbol, restype=integer, argtypes=args)
        for alias, symbol, args in (
            ("actions_init", "posix_spawn_file_actions_init", [pointer]),
            ("actions_fchdir", "posix_spawn_file_actions_addfchdir_np", [pointer, integer]),
            ("actions_dup2", "posix_spawn_file_actions_adddup2", [pointer, integer, integer]),
            ("actions_close", "posix_spawn_file_actions_addclose", [pointer, integer]),
            ("actions_destroy", "posix_spawn_file_actions_destroy", [pointer]),
            ("attributes_init", "posix_spawnattr_init", [pointer]),
            ("attributes_setflags", "posix_spawnattr_setflags", [pointer, ctypes.c_short]),
            ("attributes_destroy", "posix_spawnattr_destroy", [pointer]),
        )
    }
    spawn = _ctypes_function(
        libc,
        "posix_spawn",
        restype=integer,
        argtypes=[
            ctypes.POINTER(integer),
            ctypes.c_char_p,
            pointer,
            pointer,
            ctypes.POINTER(ctypes.c_char_p),
            ctypes.POINTER(ctypes.c_char_p),
        ],
    )

    executable_fd = -1
    cwd_fd = -1
    config_fd = -1
    null_fd = -1
    actions = void_pointer()
    attributes = void_pointer()
    actions_initialized = False
    attributes_initialized = False
    try:
        executable_fd = open_verified_executable(Path(spec.args[0]))
        cwd_fd = open_trusted_directory(spec.cwd)
        if spec.expected_cwd_device is not None or spec.expected_cwd_inode is not None:
            if (spec.expected_cwd_device, spec.expected_cwd_inode) != (
                os.fstat(cwd_fd).st_dev,
                os.fstat(cwd_fd).st_ino,
            ):
                raise OSError("unsafe_project_directory")
        environment = dict(spec.environment) if spec.environment is not None else dict(os.environ)
        if spec.environment is not None:
            config_dir = environment.get("CLAUDE_CONFIG_DIR")
            if config_dir is None:
                raise OSError("unsafe_account_directory")
            config_fd = open_private_directory(Path(config_dir))
            # macOS fdescfs exposes the descriptor itself but does not support
            # resolving child names beneath /dev/fd/N.  Keep the directory
            # open through spawn for validation, while passing its validated
            # absolute path to Claude for normal directory traversal.
            environment["CLAUDE_CONFIG_DIR"] = str(config_dir)

        _assert_path_matches_descriptor(Path(spec.args[0]), executable_fd, label="executable")
        _assert_path_matches_descriptor(spec.cwd, cwd_fd, label="project_directory")
        if config_fd >= 0:
            _assert_path_matches_descriptor(
                Path(environment["CLAUDE_CONFIG_DIR"]),
                config_fd,
                label="account_directory",
            )

        null_fd = os.open(
            "/dev/null",
            os.O_RDWR | getattr(os, "O_CLOEXEC", 0),
        )
        if functions["actions_init"](ctypes.byref(actions)) != 0:
            raise OSError("spawn_file_actions_init")
        actions_initialized = True
        if functions["actions_fchdir"](ctypes.byref(actions), cwd_fd) != 0:
            raise OSError("spawn_fchdir")
        for target in (0, 1, 2):
            if functions["actions_dup2"](ctypes.byref(actions), null_fd, target) != 0:
                raise OSError("spawn_stdio")
        if null_fd not in (0, 1, 2):
            if functions["actions_close"](ctypes.byref(actions), null_fd) != 0:
                raise OSError("spawn_devnull_close")

        if functions["attributes_init"](ctypes.byref(attributes)) != 0:
            raise OSError("spawn_attributes_init")
        attributes_initialized = True
        # POSIX_SPAWN_SETSID is Darwin-specific and is the equivalent of
        # Popen(start_new_session=True) for this native path.
        if functions["attributes_setflags"](ctypes.byref(attributes), 0x0400) != 0:
            raise OSError("spawn_setsid")

        encoded_args = [os.fsencode(argument) for argument in spec.args]
        argv = (ctypes.c_char_p * (len(encoded_args) + 1))(
            *encoded_args,
            None,
        )
        encoded_environment = [
            os.fsencode(f"{key}={value}") for key, value in environment.items()
        ]
        envp = (ctypes.c_char_p * (len(encoded_environment) + 1))(
            *encoded_environment,
            None,
        )
        pid = ctypes.c_int()
        result = spawn(
            ctypes.byref(pid),
            os.fsencode(spec.args[0]),
            ctypes.byref(actions),
            ctypes.byref(attributes),
            argv,
            envp,
        )
        if result != 0:
            raise OSError(result, os.strerror(result))
        return _PosixSpawnProcess(pid.value)
    finally:
        if actions_initialized:
            functions["actions_destroy"](ctypes.byref(actions))
        if attributes_initialized:
            functions["attributes_destroy"](ctypes.byref(attributes))
        for descriptor in (null_fd, config_fd, cwd_fd, executable_fd):
            if descriptor >= 0:
                os.close(descriptor)


def build_resume_spec(
    claude_path: str | Path,
    request: ResumeRequest,
    *,
    config_dir: str | Path | None = None,
) -> ResumeCommandSpec:
    executable = str(claude_path)
    environment = None
    if config_dir is not None:
        environment = os.environ.copy()
        environment["CLAUDE_CONFIG_DIR"] = str(config_dir)
    return ResumeCommandSpec(
        args=(executable, "-p", "--resume", request.session_id, request.message),
        cwd=request.project_path,
        environment=environment,
        expected_cwd_device=request.expected_project_device,
        expected_cwd_inode=request.expected_project_inode,
    )


class ClaudeResumeExecutor:
    def __init__(
        self,
        claude_path: str | Path,
        *,
        config_dir: str | Path | None = None,
        process_factory: Callable[[ResumeCommandSpec], object] | None = None,
    ) -> None:
        self._claude_path = claude_path
        self._config_dir = config_dir
        self._process_factory = process_factory or self._launch_process

    def launch(self, request: ResumeRequest) -> ResumeLaunchResult:
        spec = build_resume_spec(self._claude_path, request, config_dir=self._config_dir)
        try:
            process = self._process_factory(spec)
            returncode = process.wait()
        except OSError:
            return ResumeLaunchResult(False, None, "os_error")
        if returncode != 0:
            return ResumeLaunchResult(False, None, "nonzero_exit")
        pid = getattr(process, "pid", None)
        return ResumeLaunchResult(True, pid if isinstance(pid, int) else None, None)

    @staticmethod
    def _launch_process(spec: ResumeCommandSpec) -> subprocess.Popen[bytes]:
        if not spec.args:
            raise OSError("unsafe_executable")
        if sys.platform == "darwin":
            return _launch_macos_process(spec)
        executable_fd = -1
        cwd_fd = open_trusted_directory(spec.cwd)
        config_fd = -1
        try:
            executable_fd = open_verified_executable(Path(spec.args[0]))
            if spec.expected_cwd_device is not None or spec.expected_cwd_inode is not None:
                if (spec.expected_cwd_device, spec.expected_cwd_inode) != (
                    os.fstat(cwd_fd).st_dev,
                    os.fstat(cwd_fd).st_ino,
                ):
                    raise OSError("unsafe_project_directory")
            _assert_path_matches_descriptor(
                Path(spec.args[0]), executable_fd, label="executable"
            )
            _assert_path_matches_descriptor(spec.cwd, cwd_fd, label="project_directory")
            if spec.environment is not None:
                config_dir = spec.environment.get("CLAUDE_CONFIG_DIR")
                if config_dir is None:
                    raise OSError("unsafe_account_directory")
                config_fd = open_private_directory(Path(config_dir))
                _assert_path_matches_descriptor(
                    Path(config_dir), config_fd, label="account_directory"
                )
            return subprocess.Popen(
                spec.args,
                cwd=spec.cwd,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=dict(spec.environment) if spec.environment is not None else None,
            )
        finally:
            if config_fd >= 0:
                os.close(config_fd)
            os.close(cwd_fd)
            if executable_fd >= 0:
                os.close(executable_fd)


class AccountRoutedResumeExecutor:
    """Choose an isolated Claude config directory from the request account."""

    def __init__(
        self,
        accounts: Mapping[str, tuple[str | Path, str | Path]],
        *,
        process_factory: Callable[[ResumeCommandSpec], object] | None = None,
    ) -> None:
        self._executors = {
            name: ClaudeResumeExecutor(
                claude_path,
                config_dir=config_dir,
                process_factory=process_factory,
            )
            for name, (claude_path, config_dir) in accounts.items()
        }

    def launch(self, request: ResumeRequest) -> ResumeLaunchResult:
        if request.account_name is None:
            return ResumeLaunchResult(False, None, "account_unknown")
        executor = self._executors.get(request.account_name)
        if executor is None:
            return ResumeLaunchResult(False, None, "account_unknown")
        return executor.launch(request)


class DisabledResumeExecutor:
    """Safe fallback used when validated resume configuration is unavailable."""

    def launch(self, request: ResumeRequest) -> ResumeLaunchResult:
        del request
        return ResumeLaunchResult(False, None, "launch_disabled")
