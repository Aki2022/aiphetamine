"""Fixed resume command construction and injectable process launching."""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
import os
from pathlib import Path
from typing import Callable, Mapping

from .domain import ResumeLaunchResult, ResumeRequest
from .filesystem_security import open_private_directory, open_verified_executable


@dataclass(frozen=True)
class ResumeCommandSpec:
    args: tuple[str, ...]
    cwd: Path
    environment: Mapping[str, str] | None = None

    @property
    def shell(self) -> bool:
        return False

    @property
    def start_new_session(self) -> bool:
        return True

    @property
    def devnull_streams(self) -> bool:
        return True


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
        if not os.path.isdir("/dev/fd"):
            raise OSError("fd_exec_unavailable")
        executable_fd = -1
        config_fd = -1
        cwd_fd = -1
        try:
            executable_fd = open_verified_executable(Path(spec.args[0]))
            args = list(spec.args)
            args[0] = f"/dev/fd/{executable_fd}"
            cwd_fd = open_private_directory(spec.cwd)
            cwd_path = f"/dev/fd/{cwd_fd}"
            environment = dict(spec.environment) if spec.environment is not None else None
            pass_fds = [executable_fd, cwd_fd]
            if environment is not None:
                config_dir = environment.get("CLAUDE_CONFIG_DIR")
                if config_dir is None:
                    raise OSError("unsafe_account_directory")
                config_fd = open_private_directory(Path(config_dir))
                environment["CLAUDE_CONFIG_DIR"] = f"/dev/fd/{config_fd}"
                pass_fds.append(config_fd)
            for descriptor in pass_fds:
                os.set_inheritable(descriptor, True)
            return subprocess.Popen(
                args,
                cwd=cwd_path,
                shell=False,
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                start_new_session=True,
                env=environment,
                pass_fds=tuple(pass_fds),
            )
        finally:
            if config_fd >= 0:
                os.close(config_fd)
            if cwd_fd >= 0:
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
