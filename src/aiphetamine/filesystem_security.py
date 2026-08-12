"""Small, cross-platform filesystem boundaries for local AIphetamine state."""

from __future__ import annotations

import os
import secrets
import stat
from pathlib import Path


def _absolute(path: Path) -> Path:
    raw_path = Path(os.fspath(path))
    if ".." in raw_path.parts:
        # Do not collapse parent components before O_NOFOLLOW validation: a
        # symlink followed by ``..`` has different kernel semantics from the
        # lexical path and can otherwise escape the checked directory.
        raise OSError("parent_traversal_not_allowed")
    absolute = Path(os.path.abspath(os.fspath(path)))
    # macOS exposes these root-owned system directories through symlinks.  The
    # aliases are fixed platform boundaries, so normalize only the exact
    # known targets instead of resolving arbitrary user-controlled components.
    for alias, target in (
        (Path("/var"), Path("/private/var")),
        (Path("/tmp"), Path("/private/tmp")),
    ):
        if absolute != alias and alias not in absolute.parents:
            continue
        try:
            if not os.path.islink(alias) or Path(os.path.realpath(alias)) != target:
                continue
        except OSError:
            continue
        suffix = absolute.relative_to(alias)
        return target / suffix
    return absolute


def _owner_is_trusted(st: os.stat_result, *, allow_root_owner: bool = True) -> bool:
    current_uid = getattr(os, "geteuid", os.getuid)()
    return st.st_uid == current_uid or (allow_root_owner and st.st_uid == 0)


def _directory_is_trusted(
    st: os.stat_result,
    *,
    leaf: bool,
    allow_root_owner: bool = True,
    require_owner_only: bool = False,
) -> bool:
    if not stat.S_ISDIR(st.st_mode) or not _owner_is_trusted(st, allow_root_owner=allow_root_owner):
        return False
    if leaf and require_owner_only and stat.S_IMODE(st.st_mode) & 0o077:
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


def _open_trusted_directory(
    path: Path, *, leaf_owner_current: bool = True, require_owner_only: bool = False
) -> int:
    """Open every directory component with O_NOFOLLOW and validate its owner."""

    absolute = _absolute(path)
    if not absolute.is_absolute():
        raise OSError("absolute_path_required")
    if leaf_owner_current and absolute == Path(absolute.anchor or os.sep):
        raise OSError("unsafe_directory")
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
                require_owner_only=require_owner_only,
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


def ensure_trusted_directory(path: Path) -> Path:
    """Create a directory if needed without changing an existing mode."""

    path = _absolute(path)
    _check_no_symlink_components(path)
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    _check_no_symlink_components(path)
    fd = _open_trusted_directory(path)
    os.close(fd)
    return path


def is_secure_account_directory(path: Path) -> bool:
    """Return whether an existing account root is private and non-symlinked."""

    try:
        fd = _open_trusted_directory(
            _absolute(path), leaf_owner_current=True, require_owner_only=True
        )
    except OSError:
        return False
    try:
        st = os.fstat(fd)
        return stat.S_IMODE(st.st_mode) & 0o077 == 0
    finally:
        os.close(fd)


def open_private_directory(path: Path) -> int:
    """Open an owner-controlled directory without following any component."""

    return _open_trusted_directory(
        _absolute(path), leaf_owner_current=True, require_owner_only=True
    )


def open_trusted_directory(path: Path) -> int:
    """Open a trusted directory whose leaf may be publicly readable."""

    return _open_trusted_directory(_absolute(path), leaf_owner_current=True)


def ensure_private_file(path: Path) -> None:
    """Validate an existing managed file without following a symlink."""

    path = _absolute(path)
    parent_fd = _open_trusted_directory(path.parent, leaf_owner_current=True)
    descriptor = -1
    try:
        flags = os.O_RDWR | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        try:
            descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        except FileNotFoundError:
            return
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or not _owner_is_trusted(
            file_stat, allow_root_owner=False
        ):
            raise OSError("unsafe_file")
        if stat.S_IMODE(file_stat.st_mode) != 0o600:
            os.fchmod(descriptor, 0o600)
        file_stat = os.fstat(descriptor)
        if stat.S_IMODE(file_stat.st_mode) != 0o600:
            raise OSError("unsafe_file_permissions")
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def read_private_text(path: Path, *, repair_permissions: bool = True) -> str:
    """Read a managed text file through a no-follow parent/file boundary."""

    path = _absolute(path)
    parent_fd = _open_trusted_directory(path.parent, leaf_owner_current=True)
    descriptor = -1
    try:
        flags = (
            os.O_RDONLY
            | getattr(os, "O_NOFOLLOW", 0)
            | getattr(os, "O_NONBLOCK", 0)
            | getattr(os, "O_CLOEXEC", 0)
        )
        descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        file_stat = os.fstat(descriptor)
        if not stat.S_ISREG(file_stat.st_mode) or not _owner_is_trusted(
            file_stat, allow_root_owner=False
        ):
            raise OSError("unsafe_file")
        if stat.S_IMODE(file_stat.st_mode) & 0o077 and not repair_permissions:
            raise OSError("unsafe_file_permissions")
        if stat.S_IMODE(file_stat.st_mode) & 0o077:
            os.fchmod(descriptor, 0o600)
            file_stat = os.fstat(descriptor)
        if stat.S_IMODE(file_stat.st_mode) != 0o600:
            raise OSError("unsafe_file_permissions")
        with os.fdopen(descriptor, "r", encoding="utf-8") as stream:
            descriptor = -1
            return stream.read()
    finally:
        if descriptor >= 0:
            os.close(descriptor)
        os.close(parent_fd)


def validate_external_executable(path: Path) -> bool:
    """Validate an executable and every non-writable ancestor directory."""

    descriptor = -1
    try:
        descriptor = open_verified_executable(path)
    except (OSError, ValueError):
        return False
    os.close(descriptor)
    return True


def validate_external_entrypoint(path: Path) -> bool:
    """Validate a non-executable script passed as a Python entrypoint."""

    descriptor = -1
    try:
        path = _absolute(path)
        parent_fd = _open_trusted_directory(path.parent, leaf_owner_current=False)
        try:
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
            descriptor = os.open(path.name, flags, dir_fd=parent_fd)
            file_stat = os.fstat(descriptor)
            if not (
                stat.S_ISREG(file_stat.st_mode)
                and _owner_is_trusted(file_stat, allow_root_owner=True)
                and not stat.S_IMODE(file_stat.st_mode) & 0o022
            ):
                return False
            return True
        finally:
            os.close(parent_fd)
    except (OSError, ValueError):
        return False
    finally:
        if descriptor >= 0:
            os.close(descriptor)


def open_verified_executable(path: Path) -> int:
    """Open and validate an executable, keeping the checked file stable."""

    path = _absolute(path)
    parent_fd = _open_trusted_directory(path.parent, leaf_owner_current=False)
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_CLOEXEC", 0)
        descriptor = os.open(path.name, flags, dir_fd=parent_fd)
        file_stat = os.fstat(descriptor)
        if not (
            stat.S_ISREG(file_stat.st_mode)
            and _owner_is_trusted(file_stat, allow_root_owner=True)
            and not stat.S_IMODE(file_stat.st_mode) & 0o022
            and bool(file_stat.st_mode & 0o111)
        ):
            os.close(descriptor)
            raise OSError("unsafe_executable")
        return descriptor
    finally:
        os.close(parent_fd)


def atomic_write_bytes(
    target: Path, payload: bytes, *, repair_parent_permissions: bool = True
) -> None:
    """Write a managed file atomically using one stable directory descriptor."""

    target = _absolute(target)
    if repair_parent_permissions:
        ensure_private_directory(target.parent)
    else:
        ensure_trusted_directory(target.parent)
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
        os.fsync(parent_fd)
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
        entry_stat = os.stat(path.name, dir_fd=parent_fd, follow_symlinks=False)
        if not stat.S_ISREG(entry_stat.st_mode) or not _owner_is_trusted(
            entry_stat, allow_root_owner=False
        ):
            raise OSError("unsafe_file")
        os.unlink(path.name, dir_fd=parent_fd)
        os.fsync(parent_fd)
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
        try:
            destination_stat = os.stat(destination.name, dir_fd=parent_fd, follow_symlinks=False)
        except FileNotFoundError:
            destination_stat = None
        if destination_stat is not None and (
            not stat.S_ISREG(destination_stat.st_mode)
            or not _owner_is_trusted(destination_stat, allow_root_owner=False)
        ):
            raise OSError("unsafe_destination")
        os.replace(
            source.name,
            destination.name,
            src_dir_fd=parent_fd,
            dst_dir_fd=parent_fd,
        )
        os.fsync(parent_fd)
    finally:
        os.close(parent_fd)
