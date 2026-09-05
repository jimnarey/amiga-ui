"""Host-side source of ``IntuiMessage`` events for in-process vamos runs.

This module is the sanctioned way to drive a Workbench app's event loop from
the host: a test (today) or a Qt host window (later) produces *real*
``struct IntuiMessage`` blocks in 68k memory and enqueues them on the window's
*real* ``UserPort`` through the exec ``PortManager``. The app then consumes
them through the genuine path::

    WaitPort(UserPort) -> GT_GetIMsg(UserPort) -> GT_ReplyIMsg(msg)

Nothing here fakes a ``WaitPort`` success on an empty queue: a message is on
the queue only because the host event source actually posted one. With no
pending host events, ``WaitPort`` keeps its existing honest behaviour
(registered-but-empty queue raises ``UnsupportedFeatureError``).

Layout evidence
---------------
``struct IntuiMessage`` (V36+) as declared by NDK 3.2
``Include_H/intuition/intuition.h`` (the layout the target binary was
compiled against — it dereferences ``Class``/``Code``/``IAddress``/
``MouseX``/``MouseY`` directly)::

    struct IntuiMessage {
        struct Message ExecMessage;  /* ReplyMsg@0x00 + Node@0x04 (16 bytes) */
        ULONG Class;                 /* 0x10 */
        UWORD Code;                  /* 0x14 */
        UWORD Qualifier;             /* 0x16 */
        APTR IAddress;               /* 0x18 */
        WORD MouseX, MouseY;         /* 0x1C, 0x1E */
        ULONG Seconds, Micros;       /* 0x20, 0x24 */
        struct Window *IDCMPWindow;  /* 0x28 */
        struct IntuiMessage *SpecialLink;  /* 0x2C */
    };  /* size 0x30 */

IDCMP_* flag values from the same header (lines 863-882). The classic
``WaitPort``/``GetMsg`` split (WaitPort reports the first queued message
without removing it; GetMsg removes it) is what the app's drain loop
``WaitPort(); while ((msg = GT_GetIMsg(...)))`` relies on — see
``amiga_apps/itidy1classic/source/src/GUI/main_window.c``
(``handle_itidy_window_events``) and ``exec_library.py``.
"""

from __future__ import annotations

# --- struct IntuiMessage (V36+, NDK 3.2 intuition.h) -------------------------
IMSG_SIZE = 0x30
IMSG_OFF_REPLYMSG = 0x00  # APTR struct MsgPort * (from struct Message)
IMSG_OFF_LN_TYPE = 0x04  # UBYTE (from struct Message.Node)
IMSG_OFF_LN_PRI = 0x05  # BYTE (from struct Message.Node)
IMSG_OFF_LN_SUCC = 0x08  # APTR (from struct Message.Node)
IMSG_OFF_LN_PRED = 0x0C  # APTR (from struct Message.Node)
IMSG_OFF_CLASS = 0x10  # ULONG
IMSG_OFF_CODE = 0x14  # UWORD
IMSG_OFF_QUALIFIER = 0x16  # UWORD
IMSG_OFF_IADDRESS = 0x18  # APTR
IMSG_OFF_MOUSEX = 0x1C  # WORD
IMSG_OFF_MOUSEY = 0x1E  # WORD (consecutive with MouseX: ``WORD MouseX, MouseY;``)
IMSG_OFF_SECONDS = 0x20  # ULONG
IMSG_OFF_MICROS = 0x24  # ULONG
IMSG_OFF_IDCMPWINDOW = 0x28  # APTR struct Window *
IMSG_OFF_SPECIALLINK = 0x2C  # APTR struct IntuiMessage *

# --- IDCMP_* (NDK 3.2 intuition.h, lines 863-882) -----------------------------
IDCMP_SIZEVERIFY = 0x00000001
IDCMP_NEWSIZE = 0x00000002
IDCMP_REFRESHWINDOW = 0x00000004
IDCMP_MOUSEBUTTONS = 0x00000008
IDCMP_MOUSEMOVE = 0x00000010
IDCMP_GADGETDOWN = 0x00000020
IDCMP_GADGETUP = 0x00000040
IDCMP_REQSET = 0x00000080
IDCMP_MENUPICK = 0x00000100
IDCMP_CLOSEWINDOW = 0x00000200
IDCMP_RAWKEY = 0x00000400

# Targeting keyword for schedule_*: the first window whose IDCMPFlags admit
# the event class (real Intuition never generates a class a window did not
# request, so the 1x1 WFLG_BACKDROP utility window iTidy opens first is
# naturally excluded — it requests no IDCMP classes at all).
FIRST_WINDOW = "first"


class IntuitionEventBridge:
    """Deliver host-scheduled IntuiMessages to a window's real UserPort.

    Usage (test or Qt host)::

        bridge = IntuitionEventBridge()
        bridge.schedule_close_window()  # or schedule_gadget_up(...)
        rc = run_vamos_in_process(args=..., event_bridge=bridge)
        assert bridge.posted  # introspect what was delivered

    The library impls reach the bridge through the ``event_bridge`` context
    extra attribute (registered by the launcher); without it (plain probes)
    the bridge simply never gets hooks and behaviour is unchanged.
    """

    def __init__(self) -> None:
        # window addr -> {"title": str, "idcmp": int, "user_port": int,
        #                 "window_port": int}  (insertion order = open order)
        self._windows: dict[int, dict] = {}
        # gadget addr -> gadget id (registered by CreateGadgetA)
        self._gadgets: dict[int, int] = {}
        # scheduled but not yet delivered events (in schedule order)
        self._pending: list[dict] = []
        # imsg addr -> MemoryBlock (freed by release_message)
        self._imsgs: dict[int, object] = {}
        # introspection: one record per delivered message
        self.posted: list[dict] = []
        self.released: list[int] = []
        self.skipped: list[str] = []

    # -- host-side scheduling (the "Qt/test event" side) ----------------------
    def schedule_event(
        self,
        idcmp_class: int,
        *,
        window: str = FIRST_WINDOW,
        code: int = 0,
        gadget_id: int = 0,
        mousex: int = 0,
        mousey: int = 0,
    ) -> None:
        """Queue one host event for delivery to a matching window."""
        self._pending.append(
            {
                "idcmp_class": idcmp_class,
                "window": window,
                "code": code,
                "gadget_id": gadget_id,
                "mousex": mousex,
                "mousey": mousey,
            }
        )

    def schedule_close_window(self, window: str = FIRST_WINDOW) -> None:
        """Schedule an IDCMP_CloseWindow event (window close-gadget clicked)."""
        self.schedule_event(IDCMP_CLOSEWINDOW, window=window)

    def schedule_refresh_window(self, window: str = FIRST_WINDOW) -> None:
        """Schedule an IDCMP_RefreshWindow event (redraw request)."""
        self.schedule_event(IDCMP_REFRESHWINDOW, window=window)

    def schedule_gadget_up(
        self, window: str = FIRST_WINDOW, gadget_id: int = 0, mousex: int = 0, mousey: int = 0
    ) -> None:
        """Schedule an IDCMP_GadgetUp event for the gadget with ``gadget_id``.

        ``IAddress`` is resolved at delivery time to the registered gadget
        struct that carries that id; if no such gadget was created the event
        is skipped (recorded in ``self.skipped``) rather than posted with a
        NULL gadget the app would dereference.
        """
        self.schedule_event(
            IDCMP_GADGETUP,
            window=window,
            gadget_id=gadget_id,
            mousex=mousex,
            mousey=mousey,
        )

    # -- hooks called by the repo-owned library impls --------------------------
    def on_window_opened(
        self,
        ctx,
        window_addr: int,
        user_port_addr: int,
        window_port_addr: int,
        idcmp_flags: int,
        title: str = "",
    ) -> None:
        """Register an opened window and deliver pending events to it.

        Called from ``IntuitionLibrary.OpenWindowTagList`` after the window's
        real UserPort/WindowPort exist. An event is delivered to this window
        when (a) the window's ``IDCMPFlags`` admit the class — real Intuition
        filters by IDCMPFlags, so a class the window did not request is never
        generated — and (b) the window matches the event's targeting
        (``"first"`` = first window admitting the class, or a case-insensitive
        title substring).
        """
        self._windows[window_addr] = {
            "title": title,
            "idcmp": idcmp_flags,
            "user_port": user_port_addr,
            "window_port": window_port_addr,
        }
        if not self._pending:
            return
        still_pending = []
        for spec in self._pending:
            if self._targets(spec, window_addr):
                self._deliver(ctx, spec, window_addr)
            else:
                still_pending.append(spec)
        self._pending = still_pending

    def register_gadget(self, gadget_addr: int, gadget_id: int) -> None:
        """Record a created gadget for later IAddress resolution."""
        if gadget_addr:
            self._gadgets[gadget_addr] = gadget_id

    # -- message plumbing -------------------------------------------------------
    def post_event(
        self,
        ctx,
        window_addr: int,
        idcmp_class: int,
        code: int = 0,
        iaddress: int = 0,
        mousex: int = 0,
        mousey: int = 0,
    ) -> int:
        """Allocate, fill and enqueue one real IntuiMessage on the UserPort.

        Returns the IntuiMessage address. Raises ``RuntimeError`` if the
        window is unknown or its UserPort is not registered with the exec
        PortManager.
        """
        info = self._windows.get(window_addr)
        if info is None:
            raise RuntimeError(f"event bridge: post_event for unknown window {window_addr:06x}")
        port_mgr = self._get_port_mgr(ctx)
        user_port = info["user_port"]
        if port_mgr is None or not port_mgr.has_port(user_port):
            raise RuntimeError(f"event bridge: UserPort {user_port:06x} not registered with PortManager")
        mem = ctx.alloc.alloc_memory(IMSG_SIZE, label="EventBridge.IMsg")
        imsg = mem.addr
        m = ctx.mem
        m.w32(imsg + IMSG_OFF_REPLYMSG, info["window_port"])
        m.w8(imsg + IMSG_OFF_LN_TYPE, 0)
        m.w8(imsg + IMSG_OFF_LN_PRI, 0)
        m.w32(imsg + IMSG_OFF_LN_SUCC, 0)
        m.w32(imsg + IMSG_OFF_LN_PRED, 0)
        m.w32(imsg + IMSG_OFF_CLASS, idcmp_class & 0xFFFFFFFF)
        m.w16(imsg + IMSG_OFF_CODE, code & 0xFFFF)
        m.w16(imsg + IMSG_OFF_QUALIFIER, 0)
        m.w32(imsg + IMSG_OFF_IADDRESS, iaddress & 0xFFFFFFFF)
        # ``WORD MouseX, MouseY;`` are consecutive words (0x1C, 0x1E) — no
        # overlap, so plain word stores.
        m.w16(imsg + IMSG_OFF_MOUSEX, mousex & 0xFFFF)
        m.w16(imsg + IMSG_OFF_MOUSEY, mousey & 0xFFFF)
        m.w32(imsg + IMSG_OFF_SECONDS, 0)
        m.w32(imsg + IMSG_OFF_MICROS, 0)
        m.w32(imsg + IMSG_OFF_IDCMPWINDOW, window_addr & 0xFFFFFFFF)
        m.w32(imsg + IMSG_OFF_SPECIALLINK, 0)
        self._imsgs[imsg] = mem
        port_mgr.put_msg(user_port, imsg)
        self.posted.append(
            {
                "window": window_addr,
                "idcmp_class": idcmp_class,
                "code": code,
                "iaddress": iaddress,
                "imsg": imsg,
            }
        )
        return imsg

    def release_message(self, ctx, imsg_addr: int) -> None:
        """Free an IntuiMessage consumed via GT_GetIMsg (GT_ReplyIMsg side).

        The classic reply (PutMsg to ``msg->ReplyMsg`` / the WindowPort) has
        no consumer on the headless host — nothing ever waits on the
        WindowPort — so the observable work is releasing the block the
        bridge allocated. Addresses the bridge did not allocate are ignored
        (they would belong to a PutMsg the host cannot own).
        """
        if not imsg_addr:
            return
        mem = self._imsgs.pop(imsg_addr, None)
        if mem is not None:
            ctx.alloc.free_memory(mem)
            self.released.append(imsg_addr)

    # -- internals ----------------------------------------------------------------
    def _targets(self, spec: dict, window_addr: int) -> bool:
        """Whether a pending event targets this window.

        The window must admit the class via its IDCMPFlags (real Intuition
        never generates a class a window did not request); then ``"first"``
        resolves to the first such window in open order, any other value is
        a case-insensitive title substring.
        """
        info = self._windows[window_addr]
        if not (info["idcmp"] & spec["idcmp_class"]):
            return False
        target = spec["window"]
        if target == FIRST_WINDOW:
            for addr in self._windows:
                if self._windows[addr]["idcmp"] & spec["idcmp_class"]:
                    return addr == window_addr
            return False
        return target.lower() in info["title"].lower()

    def _deliver(self, ctx, spec: dict, window_addr: int) -> None:
        iaddress = 0
        if spec["idcmp_class"] == IDCMP_GADGETUP:
            for gadget_addr, gid in self._gadgets.items():
                if gid == spec["gadget_id"]:
                    iaddress = gadget_addr
                    break
            if not iaddress:
                self.skipped.append(f"gadgetup: no registered gadget with id {spec['gadget_id']}")
                return
        self.post_event(
            ctx,
            window_addr,
            spec["idcmp_class"],
            code=spec["code"],
            iaddress=iaddress,
            mousex=spec["mousex"],
            mousey=spec["mousey"],
        )

    @staticmethod
    def _get_port_mgr(ctx):
        """Reach the exec PortManager (same lookup as the intuition impl)."""
        vlib_mgr = getattr(ctx, "vlib_mgr", None)
        if vlib_mgr is None:
            return None
        vlib = vlib_mgr.get_vlib_by_name("exec.library")
        if vlib is None or vlib.impl is None:
            return None
        return vlib.impl.port_mgr
