"""Path construction for tdrive_sync's storage tiers.

Resolves between T: (the shared drive), the DATA_VERSION local cache (a
mirror of T:), and the TTDRIVE_SYNC_LOCAL_VERSION local cache (a purely local
working area).
"""

from pathlib import Path

from tdrive_sync import _config, _copy


def _relative_base_dir(base_dir: Path) -> Path:
    """Strip the drive/UNC anchor so the local cache mirrors base_dir's layout."""
    parts = base_dir.parts
    return Path(*parts[1:]) if len(parts) > 1 else Path()


def get_base_path(*, fname: str, sub_dirs: list[str] | None = None) -> Path:
    """Return the T: path for a file, ignoring local-only working mode.

    Args:
        fname: The file's name.
        sub_dirs: Subdirectories under the configured DATA_VERSION.

    Returns:
        The path on T:.
    """
    config = _config.load_config()
    return config.base_dir / config.data_version / Path(*(sub_dirs or [])) / fname


def get_local_path(*, fname: str, sub_dirs: list[str] | None = None) -> Path:
    """Return the local cache mirror of get_base_path, ignoring local-only mode.

    Args:
        fname: The file's name.
        sub_dirs: Subdirectories under the configured DATA_VERSION.

    Returns:
        The path in the local cache, under the configured DATA_VERSION.
    """
    config = _config.load_config()
    settings = _config.load_local_mode_settings()
    return (
        settings.cache_dir
        / _relative_base_dir(config.base_dir)
        / config.data_version
        / Path(*(sub_dirs or []))
        / fname
    )


def local_version_cache_path(
    config: _config.TdriveSyncConfig,
    settings: _config.LocalModeSettings,
    *,
    fname: str,
    sub_dirs: list[str],
) -> Path:
    """Return the purely-local path for a file, under TTDRIVE_SYNC_LOCAL_VERSION.

    Args:
        config: The loaded tdrive_sync_config.py settings.
        settings: The loaded TTDRIVE_SYNC_* environment settings.
        fname: The file's name.
        sub_dirs: Subdirectories under the local version.

    Returns:
        The path in the local cache, under TTDRIVE_SYNC_LOCAL_VERSION.

    Raises:
        ValueError: If TTDRIVE_SYNC_LOCAL_VERSION is not set.
    """
    if settings.local_version is None:
        msg = "TTDRIVE_SYNC_LOCAL_VERSION must be set to resolve a local-mode path."
        raise ValueError(msg)

    return (
        settings.cache_dir
        / _relative_base_dir(config.base_dir)
        / settings.local_version
        / Path(*sub_dirs)
        / fname
    )


def get_path(
    *, fname: str, sub_dirs: list[str] | None = None, copy_to_local: bool = True
) -> Path:
    """Resolve the path to read a file from, refreshing the local cache if needed.

    Ignores local-only working mode -- this is the "normal", DATA_VERSION-only
    resolution, ported from the National Liquefaction Model's ``get_path``.

    Args:
        fname: The file's name.
        sub_dirs: Subdirectories under the configured DATA_VERSION.
        copy_to_local: Whether to refresh the local cache from T: when it is
            missing or stale.

    Returns:
        The resolved path: the local cache copy if it exists (and, if
        ``copy_to_local``, is now up to date), otherwise the T: path.

    Raises:
        ValueError: If the file exists at neither location.
    """
    local_path = get_local_path(fname=fname, sub_dirs=sub_dirs)
    base_path = get_base_path(fname=fname, sub_dirs=sub_dirs)

    if copy_to_local and base_path.exists() and not local_path.exists():
        _copy.copy_to(src_path=base_path, dst_path=local_path)

    if not base_path.exists():
        if local_path.exists():
            return local_path
        msg = f"Cannot find file: {base_path}"
        raise ValueError(msg)

    if not local_path.exists():
        return base_path

    stat_local = local_path.stat()
    stat_base = base_path.stat()
    matches = (
        stat_local.st_size == stat_base.st_size
        and stat_local.st_mtime == stat_base.st_mtime
        and stat_local.st_mode == stat_base.st_mode
    )
    if not matches and copy_to_local:
        _copy.copy_to(src_path=base_path, dst_path=local_path)

    return local_path
