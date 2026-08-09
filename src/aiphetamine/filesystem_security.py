"""Small, cross-platform filesystem boundaries for local AIphetamine state."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _owner_is_trusted(st: os.stat_result, *, allow_root_owner: bool = True) -> bool:
    current_uid = getattr(os, "geteuid", os.getuid)()
    return st.st_uid == current_uid or (allow_root_owner and st.st_uid == 0)


def _directory_is_trusted(
    st: os.stat_result, *, leaf: bool, allow_root_owner: bool = True
) -> bool:
    if not stat.S_ISDIR(st.st_mode) or not _owner_is_trusted(st, allow_root_owner=allow_root_owner):
        return False
    writable = bool(st.st_mode & 0o022)
    if not writable:
        return True
    # A sticky shared ancestor such as /private/tmp is safe for per-user files;
    # a writable non-sticky ancestor is never a trusted boundary.
    return not leaf and bool(st.st_mode & stat.S_ISVTX)


def _directory_open_flags() -> int:
    flags = os.O_RDONLY | getattr(os, "O_DIRECTORY", 0) | getattr(os, "O_NOFOLLOW", 0)
    return flags | getattr(os, "O_CLOEXEC", 0)


def _open_trusted_directory(path: Path, *, leaf_owner_current: bool = True) -> int:
    """Open every directory component with O_NOFOLLOW and validate its owner."""

    absolute = _absolute(path)
    if not absolute.is_absolute():
        raise OSError("absolute_path_required")
    fd = os.open(absolute.anchor or os.sep, _directory_open_flags())
    try:
        root_stat = os.fstat(fd)
        if not _directory_is_trusted(root_stat, leaf=False):
            raise OSError("unsafe_directory_ancestor")
        for component in absolute.parts[1:]:
            if component in {"", "."}:
                continue
            child_fd = os.open(component, _directory_open_flags(), dir_fd=fd)
            os.close(fd)
            fd = child_fd
            child_stat = os.fstat(fd)
            is_leaf = component == absolute.parts[-1]
            if not _directory_is_trusted(
                child_stat,
                leaf=is_leaf,
                allow_root_owner=not (is_leaf and leaf_owner_current),
            ):
                raise OSError("unsafe_directory")
        return fd
    except BaseException:
        os.close(fd)
        raise


def _check_no_symlink_components(path: Path) -> None:
    """Reject symlinked components in a managed path before creating it."""

    absolute = _absolute(path)
    current = Path(absolute.anchor or os.sep)
    for component in absolute.parts[1:]:
        current /= component
        try:
            mode = os.lstat(current).st_mode
        except FileNotFoundError:
            break
        if stat.S_ISLNK(mode):
            raise OSError("symlink_path_component")


def ensure_private_directory(path: Path) -> Path:
    """Create or validate an owner-only managed directory."""

    path = _absolute(path)
    _check_no_symlink_components(path)
    try:
        path.mkdir(mode=0o700, parents=True, exist_ok=True)
    except OSError:
        raise
    _check_no_symlink_components(path)
    fd = _open_trusted_directory(path)
    try:
        st = os.fstat(fd)
        if stat.S_IMODE(st.st_mode) != 0o700:
            os.fchmod(fd, 0o700)
        if stat.S_IMODE(os.fstat(fd).st_mode) != 0o700:
            raise OSError("unsafe_directory_permissions")
    finally:
        os.close(fd)
    return path


def is_secure_account_directory(path: Path) -> bool:
    """Return whether an existing account root is private and non-symlinked."""

    try:
        fd = _open_trusted_directory(_absolute(path), leaf_owner_current=True)
    except OSError:
        return False
    try:
        st = os.fstat(fd)
        return stat.S_IMODE(st.st_mode) & 0o022 == 0
    finally:
        os.close(fd)


def open_private_directory(path: Path) -> int:
    """Open an owner-controlled directory without following any component."""

    return _open_trusted_directory(_absolute(path), leaf_owner_current=True)


def ensure_private_file(path: Path) -> None:
    """Validate an existing managed file without following a symlink."""

    path = _absolute(path)
    _check_no_symlink_components(path)
    try:
        st = os.stat(path, follow_symlinks=False)
    except FileNotFoundError:
        return
    if not stat.S_ISREG(st.st_mode) or not _owner_is_trusted(st, allow_root_owner=False):
        raise OSError("unsafe_file")
    if stat.S_IMODE(st.st_mode) != 0o600:
        os.chmod(path, 0o600)
    st = os.stat(path, follow_symlinks=False)
    if stat.S_IMODE(st.st_mode) != 0o600:
        raise OSError("unsafe_file_permissions")


def read_private_text(path: Path) -> str:
    """Read a managed text file through a no-follow parent/file boundary."""

    path = _absolute(path)
    parent_fd = _open_trusted_directory(path.parent, leaf_owner_current=True)
    descriptor = -1
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def validate_external_executable(path: Path) -> bool:
    """Validate an executable and every non-writable ancestor directory."""

    path = _absolute(path)
    try:
        parent_fd = _open_trusted_directory(path.parent, leaf_owner_current=False)
    except OSError:
        return False
    try:
        st = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
    except OSError:
        os.close(parent_fd)
        return False
    try:
        return (
            stat.S_ISREG(st.st_mode)
            and _owner_is_trusted(st, allow_root_owner=True)
            and bool(st.st_mode & 0o111)
        )
    finally:
        os.close(parent_fd)


def atomic_write_bytes(target: Path, payload: bytes) -> None:
    """Write a managed file atomically using one stable directory descriptor."""

    target = _absolute(target)
    ensure_private_directory(target.parent)
    parent_fd = _open_trusted_directory(target.parent, leaf_owner_current=True)
    temporary_name: str | None = None
    descriptor = -1
    try:
        flags = (
            os.O_WRONLY
            | os.O_CREAT
            | os.O_EXCL
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        for _ in range(32):
            candidate = f".{target.stem}.tmp.{secrets.token_hex(12)}"
            try:
                descriptor = os.open(candidate, flags, 0o600, dir_fd=parent_fd)
            except FileExistsError:
                continue
            temporary_name = candidate
            break
        if descriptor < 0 or temporary_name is None:
            raise OSError("temporary_file_unavailable")
        os.fchmod(descriptor, 0o600)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        # All path-sensitive operations below are relative to the descriptor
        # opened with O_NOFOLLOW, so a parent replacement cannot redirect the
        # rename into an attacker-controlled directory.
        try:
            existing = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            existing = None
        if existing is not None:
            if not stat.S_ISREG(existing.st_mode) or not _owner_is_trusted(
                existing, allow_root_owner=False
            ):
                raise OSError("unsafe_file")
        os.replace(
            temporary_name,
            target.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        temporary_name = None
        replaced = os.stat(target.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(replaced.st_mode) or stat.S_IMODE(replaced.st_mode) != 0o600:
            raise OSError("unsafe_file_permissions")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        if temporary_name is not None:
            try:
                os.unlink(temporary_name, dir_fd=parent_fd)
            except OSError:
                pass
        os.close(parent_fd)


def secure_unlink(path: Path) -> None:
    """Unlink a managed entry relative to its validated parent directory."""

    path = _absolute(path)
    parent_fd = _open_trusted_directory(path.parent, leaf_owner_current=True)
    try:
        os.unlink(path.name, dir_fd=parent_fd)
    finally:
        os.close(parent_fd)


def secure_replace(source: Path, destination: Path) -> None:
    """Replace two entries in one validated directory without path races."""

    source = _absolute(source)
    destination = _absolute(destination)
    if source.parent != destination.parent:
        raise OSError("same_directory_required")
    parent_fd = _open_trusted_directory(source.parent, leaf_owner_current=True)
    try:
        source_stat = os.stat(source.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(source_stat.st_mode) or not _owner_is_trusted(
            source_stat, allow_root_owner=False
        ):
            raise OSError("unsafe_file")
        os.replace(
            source.name,
            destination.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
    finally:
        os.close(parent_fd)
