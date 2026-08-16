"""In-process launcher for vamos with repo-owned extension hooks.

Extends vamos to auto-register PROGDIR: volumes before dos runs begin,
so das.library's CreateDir('PROGDIR:logs/') can succeed.
"""

from __future__ import annotations

import os
from typing import Any

from amitools.vamos.cfg import VamosMainParser
from amitools.vamos.lib.dos.Process import Process
from amitools.vamos.libmgr.setup import SetupLibManager
from amitools.vamos.log import log_help, log_main, log_setup
from amitools.vamos.machine import Machine, MemoryMap
from amitools.vamos.machine.regs import REG_D0
from amitools.vamos.main import RET_CODE_CONFIG_ERROR
from amitools.vamos.path import VamosPathManager
from amitools.vamos.profiler import MainProfiler
from amitools.vamos.schedule import Scheduler
from amitools.vamos.trace import TraceManager

from .bootstrap import apply_runtime_patches
from .extensions import get_library_impl_overrides


class ProjectSetupLibManager(SetupLibManager):
    """Setup manager that layers repo-owned library overrides onto vamos."""

    def setup(self):
        lib_mgr = super().setup()
        for name, impl_cls in get_library_impl_overrides().items():
            lib_mgr.add_impl_cls(name, impl_cls)
        return lib_mgr


class VamosSessionRunner:
    """Run one vamos session with repo-owned extension hooks."""

    @staticmethod
    def get_app_root_for_probe() -> str:
        """Return the app root directory for automatic PROGDIR volume registration.
        
        This auto-registers the PROGDIR:volume that holds extracted binary artifacts,
        allowing das.library's CreateDir(lock, 'PROGDIR:logs/') to succeed.
        Uses PROJECT_ROOT relative paths since the launcher runs from repo root.
        """
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
        app_root = "amiga_apps/itidy1classic/binary/extracted"
        return os.path.normpath(os.path.join(project_root, app_root))

    @staticmethod
    def create_main_parser() -> str:
        """Create the top-level vamos config parser."""

        return VamosMainParser()

    @staticmethod
    def parse_main_parser(mp: VamosMainParser, args: list[str]) -> bool:
        """Parse the provided vamos CLI arguments.
        
        Auto-registers PROGDIR: volume pointing to extracted binary artifacts
        so das.library can create 'PROGDIR:logs/' successfully.
        """
        app_root = VamosSessionRunner.get_app_root_for_probe()
        if app_root and os.path.isdir(app_root):
            mp.parse(paths=[f"prog:{app_root}"], args=args, cfg_dict=None)
        else:
            mp.parse(paths=None, args=args, cfg_dict=None)
        return True

    @staticmethod
    def setup_logging(mp:`.VamosMainParser`) -> bool: