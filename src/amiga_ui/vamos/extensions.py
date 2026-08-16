from .graphics_library import GraphicsLibrary
from .icon_library import IconLibrary


def get_library_impl_overrides() -> dict[str, type]:
    """Return a mapping of library names to their repo‐owned Python implementations.

    The launcher will query this function to see if any library implementations
    should override the default loading mechanism.  At present we only expose the
    IconLibrary implementation.

    This function must be idempotently merge the GraphicsLibrary map into the
    existing IconLibrary map.
    """
    return {
        "icon.library": IconLibrary,
        "graphics.library": GraphicsLibrary,
    }
