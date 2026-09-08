"""Tests for the repo ``dos.library`` ``GetCurrentDirName``.

Covers, without depending on the iTidy binary, the ``dos.library`` call the target
drives (2x, after its ``ENV:`` prefs lookups fail) to learn the directory it was
launched from:

- the result is the **Amiga-visible** name of the process cwd lock
  (``lock.ami_path``), never the host ``sys_path``;
- the buffer length is respected including the NUL terminator;
- an over-small buffer truncates the name to fit and returns failure
  (``IoErr == ERROR_LINE_TOO_LONG``);
- no current directory (no cwd lock) writes a null string and returns failure
  (``IoErr == ERROR_OBJECT_WRONG_TYPE``);
- no 68k memory is an honest failure, not a crash;
- a scanner regression guard: the method must be a valid ``.fd`` trap so vamos
  wires it instead of silently dropping it as an ``UNKNOWN`` trap.

The register contract matches the classic dos FD (``GetCurrentDirName(buf,len)
(d1,d2)``): D1 = buffer pointer, D2 = buffer length, D0 = success/failure.
"""

import unittest
from types import SimpleNamespace

from amitools.vamos.lib.dos.Error import ERROR_LINE_TOO_LONG, ERROR_OBJECT_WRONG_TYPE
from amitools.vamos.machine.regs import REG_D1, REG_D2

from amiga_ui.vamos.dos_library import RepoDosLibrary


class _FakeMem:
    """A minimal big-endian 68k memory model (unwritten bytes are 0)."""

    def __init__(self) -> None:
        self._bytes: dict[int, int] = {}

    def r8(self, addr: int) -> int:
        return self._bytes.get(addr, 0) & 0xFF

    def w8(self, addr: int, value: int) -> None:
        self._bytes[addr] = value & 0xFF

    def w_cstr(self, addr: int, text: str) -> None:
        for i, ch in enumerate(text):
            self.w8(addr + i, ord(ch) & 0xFF)
        self.w8(addr + len(text), 0)

    def r_cstr(self, addr: int) -> bytes:
        out = bytearray()
        i = 0
        while True:
            b = self.r8(addr + i)
            if b == 0:
                break
            out.append(b)
            i += 1
        return bytes(out)


class _FakeCpu:
    """A minimal CPU returning fixed values for D1 (buf) and D2 (len)."""

    def __init__(self, buf: int, buf_len: int) -> None:
        self._d1 = buf
        self._d2 = buf_len

    def r_reg(self, reg: int) -> int:
        if reg == REG_D1:
            return self._d1
        if reg == REG_D2:
            return self._d2
        return 0


class _FakeLock:
    def __init__(self, ami_path: str, sys_path: str) -> None:
        self.ami_path = ami_path
        self.sys_path = sys_path


class _FakeTaskAccess:
    """Records the ``pr_Result2`` (IoErr) written by ``setioerr``."""

    def __init__(self) -> None:
        self.io_err: int | None = None

    def w_s(self, name: str, value: int) -> None:
        if name == "pr_Result2":
            self.io_err = value

    def r_s(self, name: str) -> int:
        return 0


def _fake_task() -> SimpleNamespace:
    access = _FakeTaskAccess()
    return SimpleNamespace(access=access)


def _lib_with_cwd(ami_path: str | None, sys_path: str) -> RepoDosLibrary:
    """A ``RepoDosLibrary`` whose cwd lock resolves to ``ami_path`` (or None)."""
    lib = RepoDosLibrary()
    lock = _FakeLock(ami_path, sys_path) if ami_path is not None else None
    # get_current_dir() -> self.lock_mgr.get_by_b_addr(process.get_current_dir() >> 2).
    # pyright types lock_mgr as the upstream LockManager (set in setup_lib); this is an
    # intentional minimal stand-in for the focused test.
    lib.lock_mgr = SimpleNamespace(  # pyright: ignore[reportAttributeAccessIssue]
        get_by_b_addr=lambda b_addr, none_if_missing=False: lock
    )
    return lib


def _ctx(buf: int, buf_len: int, lib: RepoDosLibrary, mem: _FakeMem | None) -> SimpleNamespace:
    process = SimpleNamespace(
        get_current_dir=lambda: 0x0006A814 << 2,
        this_task=_fake_task(),
    )
    return SimpleNamespace(cpu=_FakeCpu(buf, buf_len), mem=mem, process=process)


class GetCurrentDirNameTest(unittest.TestCase):
    """``GetCurrentDirName`` writes the Amiga cwd name, honouring the buffer."""

    BUF = 0x00064FBC  # the app's buffer address (probe log)
    HOST = "/workspace/amiga-ui/artifacts/runs/x/runtime/sys/T"

    def test_success_writes_ami_name(self) -> None:
        lib = _lib_with_cwd("SYS:T", self.HOST)
        mem = _FakeMem()
        result = lib.GetCurrentDirName(_ctx(self.BUF, 256, lib, mem))

        self.assertEqual(result, 0xFFFFFFFF)  # DOSTRUE
        self.assertEqual(mem.r_cstr(self.BUF), b"SYS:T")

    def test_returns_ami_path_not_host_path(self) -> None:
        # The result must be the Amiga-visible name, never the host filesystem path.
        lib = _lib_with_cwd("SYS:T", self.HOST)
        mem = _FakeMem()
        lib.GetCurrentDirName(_ctx(self.BUF, 256, lib, mem))

        written = mem.r_cstr(self.BUF)
        self.assertNotIn(b"/", written)
        self.assertNotEqual(written, self.HOST.encode("latin1"))

    def test_truncates_when_buffer_too_small(self) -> None:
        lib = _lib_with_cwd("SYS:T", self.HOST)
        mem = _FakeMem()
        ctx = _ctx(self.BUF, 4, lib, mem)
        # buf_len=4 fits "SYS" (3 chars) + NUL, not "SYS:T" (5 chars) + NUL.
        result = lib.GetCurrentDirName(ctx)

        self.assertEqual(result, 0)  # DOSFALSE
        self.assertEqual(mem.r_cstr(self.BUF), b"SYS")
        self.assertEqual(ctx.process.this_task.access.io_err, ERROR_LINE_TOO_LONG)

    def test_zero_length_buffer_fails(self) -> None:
        lib = _lib_with_cwd("SYS:T", self.HOST)
        mem = _FakeMem()
        ctx = _ctx(self.BUF, 0, lib, mem)
        result = lib.GetCurrentDirName(ctx)

        self.assertEqual(result, 0)  # DOSFALSE
        self.assertEqual(ctx.process.this_task.access.io_err, ERROR_LINE_TOO_LONG)

    def test_no_cwd_lock_writes_null_and_fails(self) -> None:
        lib = _lib_with_cwd(None, self.HOST)
        mem = _FakeMem()
        ctx = _ctx(self.BUF, 256, lib, mem)
        result = lib.GetCurrentDirName(ctx)

        self.assertEqual(result, 0)  # DOSFALSE
        self.assertEqual(mem.r8(self.BUF), 0)  # null string
        self.assertEqual(ctx.process.this_task.access.io_err, ERROR_OBJECT_WRONG_TYPE)

    def test_no_memory_is_a_safe_failure(self) -> None:
        lib = _lib_with_cwd("SYS:T", self.HOST)
        # No 68k memory: honest failure, must not raise.
        result = lib.GetCurrentDirName(_ctx(self.BUF, 256, lib, None))

        self.assertEqual(result, 0)  # DOSFALSE


class DosScannerTest(unittest.TestCase):
    """Regression guard: GetCurrentDirName must be a valid .fd trap."""

    def _scan(self):
        from amitools.fd import read_lib_fd
        from amitools.vamos.libcore.impl import LibImplScanner

        # dos.library is in the default amitools FD set (dos_lib.fd).
        impl = RepoDosLibrary()
        fd = read_lib_fd("dos.library")
        return LibImplScanner().scan("dos.library", impl, fd, True)

    def test_get_current_dir_name_is_a_wired_trap(self) -> None:
        scan = self._scan()
        self.assertIn("GetCurrentDirName", set(scan.get_valid_func_names()))


if __name__ == "__main__":
    unittest.main()
