"""Repository-owned FD-aware vamos library creator.

Vamos resolves a library's jump-table layout from a FD table. When a FD for a
library is missing from the bundled amitools data set (gadtools, diskfont,
workbench, asl, ...), vamos silently generates a *fake* FD that only contains
the standard library calls. The result is a jump table that lacks the
library-specific entries the target program expects, so calls such as
``GetVisualInfo`` never reach the jump table and return NULL.

:class:`RepoFdLibCreator` falls back to the repository's NDK FD material for
any library that has no bundled FD, before vamos would generate a fake one.
Libraries that do have a bundled FD keep using it unchanged, so the layout of
the libraries that already work is not disturbed.
"""

from __future__ import annotations

import logging
from pathlib import Path

from amitools.fd import read_lib_fd
from amitools.vamos.libcore import LibCreator
from amitools.vamos.log import log_lib

from amiga_ui.config import PROJECT_ROOT

# NDK 3.2 FD tables bundled with the repository. The target (AmigaOS 3.0-3.1)
# uses the same function indices as the NDK 3.2 tables; the 3.2-only functions
# simply occupy higher indices the target never calls.
DEFAULT_REPO_FD_DIR = PROJECT_ROOT / "assets/docs/ndk/NDK3.2/FD"


class RepoFdLibCreator(LibCreator):
    """LibCreator that resolves missing FDs from the repository's NDK tables."""

    def __init__(self, *args, repo_fd_dir=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.repo_fd_dir = str(repo_fd_dir) if repo_fd_dir else None

    def _generate_fake_fd(self, name, lib_cfg):
        # Before falling back to a fake FD, try the repository's NDK FD tables.
        if self.repo_fd_dir:
            fd = read_lib_fd(name, self.repo_fd_dir)
            if fd is not None:
                return fd
        return super()._generate_fake_fd(name, lib_cfg)


def get_repo_fd_dir() -> Path | None:
    """Return the repository NDK FD directory when it is present."""

    if DEFAULT_REPO_FD_DIR.is_dir():
        return DEFAULT_REPO_FD_DIR
    return None


def install_repo_fd_creator(vlib_mgr, repo_fd_dir: Path | None = None) -> RepoFdLibCreator:
    """Replace ``vlib_mgr.creator`` with a repo-FD-aware creator.

    The creator is created lazily by ``VLibManager`` and is only consulted when
    a library is actually opened, so replacing it before any library is opened
    (i.e. during launcher setup) is safe.
    """
    repo_fd_dir = repo_fd_dir or get_repo_fd_dir()
    if repo_fd_dir is None:
        raise RuntimeError("repository NDK FD directory is not available")
    old = vlib_mgr.creator
    log_missing = log_lib if log_lib.isEnabledFor(logging.WARNING) else None
    log_valid = log_lib if log_lib.isEnabledFor(logging.INFO) else None
    creator = RepoFdLibCreator(
        old.alloc,
        old.traps,
        fd_dir=old.fd_dir,
        log_missing=log_missing,
        log_valid=log_valid,
        lib_profiler=old.profiler,
        repo_fd_dir=repo_fd_dir,
    )
    vlib_mgr.creator = creator
    return creator
