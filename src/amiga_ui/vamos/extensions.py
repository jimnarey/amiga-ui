from .asllibrary import ASLLibrary
from .diskfont_library import DiskFontLibrary
from .dos_library import RepoDosLibrary
from .exec_library import RepoExecLibrary
from .gadtools_library import GadToolsLibrary
from .graphics_library import GraphicsLibrary
from .icon_library import IconLibrary
from .iffparse_library import IffParseLibrary
from .intuition_library import IntuitionLibrary
from .timer_device import RepoTimerDevice
from .workbench_library import WorkbenchLibrary


def get_library_impl_overrides() -> dict[str, type]:
    """Return a mapping of library names to their repo–owned Python implementations.

    The launcher will query this function to see if any library implementations
    should override the default loading mechanism. At present we expose the
    ASLLibrary, DiskFontLibrary, RepoDosLibrary, RepoExecLibrary,
    GadToolsLibrary, GraphicsLibrary, IconLibrary, IffParseLibrary,
    RepoTimerDevice, WorkbenchLibrary, and IntuitionLibrary implementations.
    """
    return {
        "asl.library": ASLLibrary,
        "diskfont.library": DiskFontLibrary,
        "dos.library": RepoDosLibrary,
        "exec.library": RepoExecLibrary,
        "gadtools.library": GadToolsLibrary,
        "icon.library": IconLibrary,
        "graphics.library": GraphicsLibrary,
        "intuition.library": IntuitionLibrary,
        "iffparse.library": IffParseLibrary,
        "timer.device": RepoTimerDevice,
        "workbench.library": WorkbenchLibrary,
    }
