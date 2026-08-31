---
title: "Writing A Library Implementation"
status: draft
depends_on:
  - "vamos-overview.md"
  - "vamos-library-modes.md"
citations_used: []
---

# Writing A Library Implementation

Purpose: Show the concrete, mechanical shape of a repo-owned `vamos` library implementation, so an agent can write one without first reverse-engineering `amitools` from scratch.

Needed for:
- The moment a probe fails with `OpenLibrary: 'X.library' V0 -> 000000` and the fix is "implement (part of) that library."

Notes:
- This page describes internal `amitools` mechanics, not upstream Amiga API facts, so it does not use the `docs/sources.md` numbered citation system. Instead it points directly at file paths inside the installed dependency. Those paths are correct for the `amitools` version pinned in `uv.lock` at the time this page was written; if a function or file has moved, re-derive the pattern from the installed package rather than trusting this page blindly — `grep -rn "class LibImpl" .venv/lib/python*/site-packages/amitools/` is the fastest way to relocate it.
- The worked example below uses `icon.library` because it is a concrete, real function set. It is an illustration of the mechanism, not a claim about what the project's current blocker is — check `docs/apps/<app>/compatibility-notes.md` for that.
- The repository now includes a live minimal example at `src/amiga_ui/vamos/icon_library.py`. Use it as the first reference for "how do we make a missing library open at all?" before adding any function traps.

## Summary

A `vamos` library implementation is an ordinary Python class with one method per AmigaOS function name. `amitools` matches your methods against the library's `.fd` file (its function/register table) by name, calls the matched method whenever the emulated program invokes that function, and reads arguments out of emulated CPU registers rather than a normal Python argument list. This page shows that mechanism end to end.

## Step 1: Find The Library's Function Table (the `.fd` file)

Every AmigaOS library ships an `.fd` file describing its callable functions and which registers carry each argument. `amitools` bundles these under:

```
<amitools-install>/data/fd/<libname>_lib.fd
```

For example, `icon.library`'s table is at `amitools/data/fd/icon_lib.fd`. Find the installed location with:

```bash
.venv/bin/python -c "import amitools, pathlib; print(pathlib.Path(amitools.__file__).parent / 'data' / 'fd')"
```

An `.fd` entry looks like:

```
GetDiskObject(name)(a0)
FreeDiskObject(diskobj)(a0)
AddFreeList(freelist,mem,size)(a0/a1/a2)
```

The first parens list the argument names in order; the second parens list the registers that hold them, in the same order. So `GetDiskObject(name)(a0)` means: one argument called `name`, passed in register `A0`.


## Mapping `UNKNOWN(#index)` Calls To Functions

When `vamos.log` reports a call such as:

```text
graphics.library 972 UNKNOWN(#161)
```

map it with `amitools`' own `.fd` parser. Do not hand-count lines or visible function entries in the `.fd` file. Library tables can start at a non-zero bias, include private functions, or otherwise make manual ordinal counts misleading.

Use this diagnostic shape from the repo root:

```bash
uv run python - <<'PY'
from amitools.fd import read_lib_fd

lib_name = "graphics.library"
unknown_index = 161
fd = read_lib_fd(lib_name)
for func in fd.get_funcs():
    if func.get_index() == unknown_index:
        print(func.get_name(), "index", func.get_index(), "bias", func.get_bias(), "args", func.get_args())
PY
```

For the example above, the important value is the FD index from the log, not the apparent ordinal position in the text file. In the current pinned `amitools`, `graphics.library` index `161` / bias `972` maps to `FreeDBufInfo(dbi)(a1)`, while `SetRGB32CM(cm,n,r,g,b)` is a later FD entry.

If a method exists in your implementation but the log still says `UNKNOWN(#index)`, check the scanner result before adding more stubs:

```bash
uv run python - <<'PY'
from amitools.fd import read_lib_fd
from amitools.vamos.libcore.impl import LibImplScanner
from src.amiga_ui.vamos.graphics_library import GraphicsLibrary

lib_name = "graphics.library"
impl = GraphicsLibrary()
fd = read_lib_fd(lib_name)
scan = LibImplScanner().scan(lib_name, impl, fd, True)
print("valid", scan.get_num_valid_funcs())
print("error", scan.get_num_error_funcs(), scan.get_error_func_names())
print("invalid", scan.get_num_invalid_funcs(), scan.get_invalid_func_names())
print("missing", scan.get_num_missing_funcs())
PY
```

A scanner `error` is not a harmless warning: that function is not installed as a valid trap. The most common cause is a bad method signature. Valid methods must begin with `self, ctx`; if they include extra arguments, the extra argument count must match the `.fd` entry exactly and the method must not use `*args`, `**kwargs`, or default values.

## Step 2: Write The Implementation Class

Subclass `LibImpl` from `amitools.vamos.libcore`, and add one method per function name from the `.fd` file. Each method must begin with `self` and a `ctx` object (the call context). After that, you may either read registers yourself from `ctx`, or add one Python parameter per `.fd` argument and let `amitools` map those registers for you:

```python
from amitools.vamos.libcore import LibImpl
from amitools.vamos.machine.regs import REG_A0


class IconLibrary(LibImpl):
    def GetDiskObject(self, ctx):
        name_ptr = ctx.cpu.r_reg(REG_A0)
        name = ctx.mem.r_cstr(name_ptr)
        # ... build and return a DiskObject pointer ...
```

For the "library is missing entirely" stage, a class with only `get_version()` can already be useful if the real goal is to make `OpenLibrary()` succeed and let the next probe expose the first required function call. The repo's current `icon.library` override demonstrates that narrower first step.

If you include `.fd` arguments in the method signature, keep the count exact and keep `ctx` as the first argument after `self`:

```python
def FreeDBufInfo(self, ctx, dbi):
    # graphics.library FreeDBufInfo(dbi)(a1)
    return None
```

Do not write methods like `def FreeDBufInfo(self, dbi):`. They import and compile, but `amitools` marks them as scanner errors and does not wire them into the library jump table.

Method names must match the `.fd` entry exactly, including case. `amitools` scans your class with `inspect.getmembers` and matches by name against the `.fd` table (`amitools/vamos/libcore/impl.py`, `LibImplScanner.scan`); a method whose name isn't in the `.fd` file is simply not wired up as a trap, not an error, so a typo fails silently rather than loudly. If a run still reports the library as missing after adding an implementation, first confirm the method name matches the `.fd` file exactly.

You do not need to implement every function up front. Implement the one function the current blocker needs, register it, rerun the probe, and let the next blocker (possibly the next function on the same library) tell you what to add next — this is the same one-fix-at-a-time discipline as the rest of the porting loop.

## Step 3: Read Arguments From Registers

Arguments arrive in CPU registers. You can either read them explicitly from `ctx`, or let `amitools` pass them as extra Python parameters if your method signature is `self, ctx, <fd args...>`. For explicit reads, use `ctx.cpu.r_reg(...)` with the register named in the `.fd` file:

```python
from amitools.vamos.machine.regs import REG_D0, REG_A0, REG_A1


def SomeFunction(self, ctx):
    flags = ctx.cpu.r_reg(REG_D0)  # a plain integer/flags argument
    ptr = ctx.cpu.r_reg(REG_A0)  # a pointer argument
```

## Step 4: Read And Write Emulated Memory

Pointer arguments are addresses into the emulated Amiga address space, not real Python objects. Use `ctx.mem` to dereference them:

```python
name = ctx.mem.r_cstr(name_ptr)  # read a NUL-terminated C string
first_long = ctx.mem.r32(struct_ptr)  # read a 4-byte field at an address
ctx.mem.w32(struct_ptr + 12, new_value)  # write a 4-byte field at an offset
```

`r32`/`w32` (and the `r16`/`w16`, `r8`/`w8` equivalents) take an absolute emulated address; add the appropriate struct-field byte offset yourself, the same way you would in C. The relevant struct's field layout and offsets belong in `docs/platform/structs/` — check there before hand-deriving offsets.

## Step 5: Return Values

- A single scalar return value (what would normally come back in `D0`): `return value`.
- Multiple register outputs (rare; `.fd` entries never encode this, but some AmigaOS calls document secondary results in `D1` etc.): return a list in register order, e.g. `return [quotient, remainder]`. See `amitools/vamos/lib/UtilityLibrary.py`'s `UDivMod32` for a real example of this shape.
- Returning `None` is fine for functions with no meaningful result.

## Step 6: Register The Implementation

Add the class to the repo-owned override registry so the launcher's library manager picks it up. Continuing the `IconLibrary` example from Step 2, once that class exists somewhere under `src/amiga_ui/vamos/`:

```python
# src/amiga_ui/vamos/extensions.py
from .icon_library import IconLibrary  # wherever you place the implementation


def get_library_impl_overrides() -> dict[str, type]:
    return {"icon.library": IconLibrary}
```

Pass the class itself, not an instance — `amitools` instantiates it with a no-argument constructor when the library is opened (`amitools/vamos/libcore/mgr.py`, `VLibManager.make_lib`). If the implementation needs per-session state, initialize it in `setup_lib(self, ctx, base_addr)` (a hook on the `LibImpl` base class) rather than `__init__`.

Also set the library's mode so `vamos` actually uses your Python implementation instead of trying to load an original Amiga library or failing outright. See `vamos-library-modes.md` for the `vamos`/`amiga`/`auto`/`fake`/`off` choice; a library you are actively implementing should normally run in `vamos` mode.

## Step 7: Verify

1. Rerun the relevant probe and confirm `OpenLibrary` for that library now succeeds in the `vamos.log`.
2. Confirm the app's next action against that library (the one your new method implements) behaves plausibly, not just that the library opened.
3. Add or extend a focused unit test alongside the implementation, per `.agents/skills/code-style/SKILL.md` and `.agents/skills/testing-and-regression/SKILL.md`.

## Working Rule

Implement the smallest set of functions that moves the current blocker forward — usually one function, occasionally two or three that are called in the same startup sequence. Do not pre-implement a library's full function table speculatively; let real probe failures choose the next function, the same way they choose the next library.
