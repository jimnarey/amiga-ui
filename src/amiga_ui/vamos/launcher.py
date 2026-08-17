"""In-process launcher for vamos with repo-owned extension hooks."""

from __future__ import annotations

from pathlib import Path
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

from amiga_ui.config import PROJECT_ROOT

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
    """Run one vamos session with repo-owned bootstrap hooks."""

    @staticmethod
    def create_main_parser() -> VamosMainParser:
        """Create the top-level vamos config parser."""

        return VamosMainParser()

    @staticmethod
    def get_app_root_for_probe() -> Path | None:
        """Return the extracted application root for PROGDIR: mapping."""

        app_root = PROJECT_ROOT / "amiga_apps/itidy1classic/binary/extracted"
        return app_root if app_root.is_dir() else None

    @staticmethod
    def add_progdir_volume(args: list[str]) -> list[str]:
        """Add a PROGDIR: volume for extracted app resources when available."""

        app_root = VamosSessionRunner.get_app_root_for_probe()
        if app_root is None:
            return args
        if any(arg.lower().startswith("progdir:") for arg in args):
            return args
        return ["-V", f"progdir:{app_root}", *args]

    @staticmethod
    def parse_main_parser(mp: VamosMainParser, args: list[str]) -> bool:
        """Parse the provided vamos CLI arguments."""

        return mp.parse(
            paths=None,
            args=VamosSessionRunner.add_progdir_volume(args),
            cfg_dict=None,
        )

    @staticmethod
    def setup_logging(mp: VamosMainParser) -> bool:
        """Configure vamos logging from the parsed config."""

        log_cfg = mp.get_log_dict().logging
        if log_setup(log_cfg):
            return True
        log_help()
        return False

    @staticmethod
    def create_main_profiler(mp: VamosMainParser) -> MainProfiler:
        """Create and configure the main vamos profiler."""

        main_profiler = MainProfiler()
        prof_cfg = mp.get_profile_dict().profile
        main_profiler.parse_config(prof_cfg)
        return main_profiler

    @staticmethod
    def create_machine(mp: VamosMainParser) -> Machine | None:
        """Create the vamos machine from config."""

        machine_cfg = mp.get_machine_dict().machine
        use_labels = mp.get_trace_dict().trace.labels
        return Machine.from_cfg(machine_cfg, use_labels)

    @staticmethod
    def create_memory_map(machine: Machine, mp: VamosMainParser) -> MemoryMap | None:
        """Create and configure the memory map."""

        mem_map_cfg = mp.get_machine_dict().memmap
        mem_map = MemoryMap(machine)
        if not mem_map.parse_config(mem_map_cfg):
            log_main.error("memory map setup failed!")
            return None
        return mem_map

    @staticmethod
    def create_trace_manager(machine: Machine, mp: VamosMainParser) -> TraceManager | None:
        """Create and configure the trace manager."""

        trace_mgr_cfg = mp.get_trace_dict().trace
        trace_mgr = TraceManager(machine)
        if not trace_mgr.parse_config(trace_mgr_cfg):
            log_main.error("tracing setup failed!")
            return None
        return trace_mgr

    @staticmethod
    def create_path_manager() -> VamosPathManager:
        """Create the vamos path manager."""

        return VamosPathManager()

    @staticmethod
    def create_scheduler(machine: Machine) -> Scheduler:
        """Create the vamos scheduler."""

        return Scheduler(machine)

    @staticmethod
    def create_lib_manager(
        machine: Machine,
        mem_map: MemoryMap,
        scheduler: Scheduler,
        path_mgr: VamosPathManager,
        main_profiler: MainProfiler,
    ) -> ProjectSetupLibManager:
        """Create the repo-owned library manager wrapper."""

        return ProjectSetupLibManager(
            machine,
            mem_map,
            scheduler,
            path_mgr,
            main_profiler=main_profiler,
        )

    @staticmethod
    def require_run_state(task: Any) -> Any:
        """Return the task run state or ``None`` if scheduling produced no result."""

        return task.get_run_state()

    def __init__(self, args: list[str]):
        self.args = args
        self.mp: VamosMainParser | None = None
        self.main_profiler: MainProfiler | None = None
        self.machine: Machine | None = None
        self.mem_map: MemoryMap | None = None
        self.trace_mgr: TraceManager | None = None
        self.path_mgr: VamosPathManager | None = None
        self.scheduler: Scheduler | None = None
        self.slm: ProjectSetupLibManager | None = None
        self.main_proc: Process | None = None
        self.ok = False
        self.exit_code = RET_CODE_CONFIG_ERROR
        self.profiler_started = False

    def run(self) -> int:
        """Run a full vamos session and return the target exit code."""

        if not self.parse_config():
            return RET_CODE_CONFIG_ERROR
        if not self.configure_logging():
            return RET_CODE_CONFIG_ERROR
        self.main_profiler = self.create_configured_profiler()
        if not self.create_core_runtime():
            return RET_CODE_CONFIG_ERROR

        try:
            if not self.configure_paths():
                return self.exit_code
            self.create_scheduler_runtime()
            if not self.configure_lib_manager():
                return self.exit_code
            self.start_profiler()
            self.open_base_libs()
            if not self.create_main_process():
                return self.exit_code
            task = self.schedule_main_process()
            self.exit_code = self.evaluate_task_result(task)
            return self.exit_code
        finally:
            self.cleanup()

    def parse_config(self) -> bool:
        """Parse the provided arguments into a configured parser."""

        self.mp = self.create_main_parser()
        return self.parse_main_parser(self.mp, self.args)

    def configure_logging(self) -> bool:
        """Set up logging from the parsed config."""

        mp = self._require_parser()
        return self.setup_logging(mp)

    def create_configured_profiler(self) -> MainProfiler:
        """Create the configured profiler instance."""

        mp = self._require_parser()
        return self.create_main_profiler(mp)

    def create_core_runtime(self) -> bool:
        """Create the core machine, memory, trace, and path managers."""

        mp = self._require_parser()
        machine = self.create_machine(mp)
        if machine is None:
            return False
        self.machine = machine

        mem_map = self.create_memory_map(machine, mp)
        if mem_map is None:
            return False
        self.mem_map = mem_map

        trace_mgr = self.create_trace_manager(machine, mp)
        if trace_mgr is None:
            return False
        self.trace_mgr = trace_mgr
        self.path_mgr = self.create_path_manager()
        return True

    def configure_paths(self) -> bool:
        """Parse and set up vamos path handling."""

        mp = self._require_parser()
        path_mgr = self._require_path_manager()
        if not path_mgr.parse_config(mp.get_path_dict()):
            log_main.error("path config failed!")
            return False
        if not path_mgr.setup():
            log_main.error("path setup failed!")
            return False
        return True

    def create_scheduler_runtime(self) -> None:
        """Create the scheduler after the machine is ready."""

        machine = self._require_machine()
        self.scheduler = self.create_scheduler(machine)

    def configure_lib_manager(self) -> bool:
        """Create, configure, and set up the library manager."""

        mp = self._require_parser()
        machine = self._require_machine()
        mem_map = self._require_memory_map()
        scheduler = self._require_scheduler()
        path_mgr = self._require_path_manager()
        main_profiler = self._require_profiler()

        slm = self.create_lib_manager(machine, mem_map, scheduler, path_mgr, main_profiler)
        lib_cfg = mp.get_libs_dict()
        if not slm.parse_config(lib_cfg):
            log_main.error("lib manager setup failed!")
            return False
        slm.setup()
        self.slm = slm
        return True

    def start_profiler(self) -> None:
        """Start the main profiler before opening libraries."""

        main_profiler = self._require_profiler()
        main_profiler.setup()
        self.profiler_started = True

    def open_base_libs(self) -> None:
        """Open the base libraries needed for process creation."""

        slm = self._require_lib_manager()
        slm.open_base_libs()

    def create_main_process(self) -> bool:
        """Create the main Amiga process to run."""

        mp = self._require_parser()
        path_mgr = self._require_path_manager()
        slm = self._require_lib_manager()
        proc_cfg = mp.get_proc_dict().process
        self.main_proc = Process.create_main_proc(proc_cfg, path_mgr, slm.dos_ctx)
        if self.main_proc is None:
            log_main.error("main proc setup failed!")
            return False
        return True

    def schedule_main_process(self) -> Any:
        """Schedule the created process and return its task."""

        scheduler = self._require_scheduler()
        main_proc = self._require_main_process()
        task = main_proc.get_task()
        scheduler.add_task(task)
        scheduler.schedule()
        return task

    def evaluate_task_result(self, task: Any) -> int:
        """Translate the task run state into the final exit code."""

        run_state = self.require_run_state(task)
        if run_state is None:
            log_main.error("task finished without a run state")
            return 1
        if not run_state.done:
            return self.handle_stopped_task()
        if run_state.error:
            log_main.error("vamos failed!")
            return 1
        return self.handle_completed_task(run_state)

    def handle_stopped_task(self) -> int:
        """Handle the case where execution stopped before completion."""

        machine_cfg = self._require_parser().get_machine_dict().machine
        log_main.info(
            "vamos was stopped after %d cycles. ignoring result",
            machine_cfg.max_cycles,
        )
        return 0

    def handle_completed_task(self, run_state: Any) -> int:
        """Handle a completed task with a successful run state."""

        self.ok = True
        exit_code = run_state.regs[REG_D0] & 0xFF
        log_main.info("done. exit code=%d", exit_code)
        log_main.info("total cycles: %d", run_state.cycles)
        return exit_code

    def cleanup(self) -> None:
        """Release resources accumulated during session setup and execution."""

        if self.ok and self.main_proc is not None:
            self.main_proc.free()
        if self.slm is not None:
            self.slm.close_base_libs()
        if self.profiler_started and self.main_profiler is not None:
            self.main_profiler.shutdown()
        if self.slm is not None:
            self.slm.cleanup()
        if self.path_mgr is not None:
            self.path_mgr.shutdown()
        if self.ok and self.mem_map is not None:
            self.mem_map.cleanup()
        if self.machine is not None:
            self.machine.cleanup()
        log_main.info("vamos is exiting: code=%d", self.exit_code)

    def _require_parser(self) -> VamosMainParser:
        if self.mp is None:
            raise RuntimeError("vamos parser is not available")
        return self.mp

    def _require_profiler(self) -> MainProfiler:
        if self.main_profiler is None:
            raise RuntimeError("main profiler is not available")
        return self.main_profiler

    def _require_machine(self) -> Machine:
        if self.machine is None:
            raise RuntimeError("machine is not available")
        return self.machine

    def _require_memory_map(self) -> MemoryMap:
        if self.mem_map is None:
            raise RuntimeError("memory map is not available")
        return self.mem_map

    def _require_path_manager(self) -> VamosPathManager:
        if self.path_mgr is None:
            raise RuntimeError("path manager is not available")
        return self.path_mgr

    def _require_scheduler(self) -> Scheduler:
        if self.scheduler is None:
            raise RuntimeError("scheduler is not available")
        return self.scheduler

    def _require_lib_manager(self) -> ProjectSetupLibManager:
        if self.slm is None:
            raise RuntimeError("library manager is not available")
        return self.slm

    def _require_main_process(self) -> Process:
        if self.main_proc is None:
            raise RuntimeError("main process is not available")
        return self.main_proc


def run_vamos_in_process(*, args: list[str]) -> int:
    """Run vamos in-process with project bootstrap hooks."""

    with apply_runtime_patches():
        runner = VamosSessionRunner(args)
        return runner.run()
