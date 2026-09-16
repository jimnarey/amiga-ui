"""Qt-free tests for the EasyRequestArgs decode / result-code mapping.

These exercise the *Qt-free seam* of ``intuition.library``'s ``EasyRequestArgs``
(LVO 588) without Qt, iTidy, or a display: the compatibility layer must decode
the app's own ``EasyStruct`` (title, TextFormat body, pipe-separated GadgetFormat
button list) from emulated memory and map a clicked button to the classic result
code (positive -> nonzero, cancel -> 0). The Qt QMessageBox half (the actual
dialog round trip) is covered by ``tests/test_qt_easy_request_dialog.py`` and the
full real-iTidy LHA-not-found route by ``tests/run_interactive_lha_smoke_test.py``.

Everything here is synthetic (no dependency on the exact iTidy strings beyond the
LHA dialog, which is the accepted target); the decode mechanism is what is under
test, and the result-code mapping is settled from the AutoDocs EasyRequestArgs
example (``Retry|Cancel``, ``CANCEL 0``).
"""

import unittest
from types import SimpleNamespace

from amitools.vamos.error import UnsupportedFeatureError

from amiga_ui.vamos.intuition_library import (
    _EASY_OFF_GADGET_FORMAT,
    _EASY_OFF_TEXT_FORMAT,
    _EASY_OFF_TITLE,
    IntuitionLibrary,
)


class _FakeMem:
    """A minimal big-endian 68k memory model (unwritten bytes are 0)."""

    def __init__(self) -> None:
        self._bytes: dict[int, int] = {}

    def r8(self, addr: int) -> int:
        return self._bytes.get(addr, 0) & 0xFF

    def w8(self, addr: int, value: int) -> None:
        self._bytes[addr] = value & 0xFF

    def r32(self, addr: int) -> int:
        return (self.r8(addr) << 24) | (self.r8(addr + 1) << 16) | (self.r8(addr + 2) << 8) | self.r8(addr + 3)

    def w32(self, addr: int, value: int) -> None:
        value &= 0xFFFFFFFF
        self.w8(addr, (value >> 24) & 0xFF)
        self.w8(addr + 1, (value >> 16) & 0xFF)
        self.w8(addr + 2, (value >> 8) & 0xFF)
        self.w8(addr + 3, value & 0xFF)


def _write_c_string(mem, addr, s):
    for i, ch in enumerate(s):
        mem.w8(addr + i, ord(ch) & 0xFF)
    mem.w8(addr + len(s), 0)
    return len(s) + 1


def _write_easy_struct(mem, easy_struct, *, title, body, gadget_format):
    """Populate an EasyStruct block and its three C-string fields in memory."""
    title_addr = 0x0020_0000
    body_addr = 0x0020_0100
    gadget_addr = 0x0020_0200
    _write_c_string(mem, title_addr, title)
    _write_c_string(mem, body_addr, body)
    _write_c_string(mem, gadget_addr, gadget_format)
    mem.w32(easy_struct + _EASY_OFF_TITLE, title_addr)
    mem.w32(easy_struct + _EASY_OFF_TEXT_FORMAT, body_addr)
    mem.w32(easy_struct + _EASY_OFF_GADGET_FORMAT, gadget_addr)


class _FakeProjection:
    """Records the show_easy_request call and returns a fixed clicked index."""

    def __init__(self, clicked_index=0) -> None:
        self.clicked_index = clicked_index
        self.calls: list[tuple] = []

    def show_easy_request(self, window_addr, title, body, buttons):
        self.calls.append((window_addr, title, body, buttons))
        return self.clicked_index


class EasyStructDecodeTest(unittest.TestCase):
    def _lib_and_ctx(self):
        mem = _FakeMem()
        return IntuitionLibrary(), SimpleNamespace(mem=mem, host_projection=None), mem

    def test_decodes_lha_dialog_fields(self) -> None:
        lib, ctx, mem = self._lib_and_ctx()
        easy = 0x0030_0000
        _write_easy_struct(
            mem,
            easy,
            title="LHA Not Found",
            body="LHA archiver not found in C:, SYS:C/, or SYS:Tools/.",
            gadget_format="Continue|Cancel",
        )
        title, body, buttons = lib._decode_easy_struct(ctx, easy)
        self.assertEqual(title, "LHA Not Found")
        self.assertEqual(body, "LHA archiver not found in C:, SYS:C/, or SYS:Tools/.")
        self.assertEqual(buttons, ["Continue", "Cancel"])

    def test_empty_gadget_format_falls_back_to_single_ok(self) -> None:
        lib, ctx, mem = self._lib_and_ctx()
        easy = 0x0030_0000
        _write_easy_struct(mem, easy, title="T", body="B", gadget_format="")
        title, body, buttons = lib._decode_easy_struct(ctx, easy)
        self.assertEqual(title, "T")
        self.assertEqual(buttons, ["OK"])

    def test_null_strings_decode_to_empty(self) -> None:
        lib, ctx, mem = self._lib_and_ctx()
        # A zeroed EasyStruct: every STRPTR is 0, so every field decodes empty.
        easy = 0x0030_0000
        title, body, buttons = lib._decode_easy_struct(ctx, easy)
        self.assertEqual(title, "")
        self.assertEqual(body, "")
        self.assertEqual(buttons, ["OK"])


class EasyRequestCodeMappingTest(unittest.TestCase):
    def test_two_button_positive_is_nonzero_cancel_is_zero(self) -> None:
        # The accepted target (Continue|Cancel): first -> 1, second (cancel) -> 0.
        self.assertEqual(IntuitionLibrary._easy_request_code(0, 2), 1)
        self.assertEqual(IntuitionLibrary._easy_request_code(1, 2), 0)

    def test_single_button_is_positive(self) -> None:
        self.assertEqual(IntuitionLibrary._easy_request_code(0, 1), 1)

    def test_middle_button_uses_its_position(self) -> None:
        # 3 buttons: first -> 1, middle -> 2, last (cancel) -> 0.
        self.assertEqual(IntuitionLibrary._easy_request_code(0, 3), 1)
        self.assertEqual(IntuitionLibrary._easy_request_code(1, 3), 2)
        self.assertEqual(IntuitionLibrary._easy_request_code(2, 3), 0)


class EasyRequestArgsSeamTest(unittest.TestCase):
    """The full Qt-free path: decode -> projection call -> classic code."""

    def _run(self, clicked_index, gadget_format="Continue|Cancel"):
        mem = _FakeMem()
        lib = IntuitionLibrary()
        proj = _FakeProjection(clicked_index=clicked_index)
        ctx = SimpleNamespace(mem=mem, host_projection=proj)
        easy = 0x0030_0000
        _write_easy_struct(
            mem,
            easy,
            title="LHA Not Found",
            body="LHA archiver not found in C:, SYS:C/, or SYS:Tools/.",
            gadget_format=gadget_format,
        )
        return lib.EasyRequestArgs(ctx, 0x000A_0000, easy, None, None), proj

    def test_continue_returns_nonzero_and_passes_decoded_fields(self) -> None:
        code, proj = self._run(clicked_index=0)
        self.assertEqual(code, 1)
        window, title, body, buttons = proj.calls[0]
        self.assertEqual(window, 0x000A_0000)
        self.assertEqual(title, "LHA Not Found")
        self.assertEqual(buttons, ["Continue", "Cancel"])

    def test_cancel_returns_zero(self) -> None:
        code, _ = self._run(clicked_index=1)
        self.assertEqual(code, 0)

    def test_without_projection_fails_honestly(self) -> None:
        mem = _FakeMem()
        lib = IntuitionLibrary()
        ctx = SimpleNamespace(mem=mem, host_projection=None)
        easy = 0x0030_0000
        _write_easy_struct(mem, easy, title="T", body="B", gadget_format="A|B")
        with self.assertRaises(UnsupportedFeatureError):
            lib.EasyRequestArgs(ctx, 0x000A_0000, easy, None, None)


if __name__ == "__main__":
    unittest.main()
