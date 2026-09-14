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
The iTidy target binary was compiled against NDK headers whose
``struct Message`` is 0x14 bytes (one ULONG wider than the classic
0x10-byte layout). That shifts every ``IntuiMessage`` field after
``im_Message`` by +0x04 relative to the classic offsets. Established by
targeted disassembly of ``handle_itidy_window_events`` (the app reads
``im_Class`` from ``msg+0x14`` and ``im_IAddress`` from ``msg+0x1c``) and
confirmed by runtime memory evidence::

    struct IntuiMessage {
        struct Message ExecMessage;  /* ReplyMsg@0x00 + Node@0x04 + pad (20 bytes) */
        ULONG Class;                 /* 0x14 */
        UWORD Code;                  /* 0x18 */
        UWORD Qualifier;             /* 0x1A (padding) */
        APTR IAddress;               /* 0x1C */
        WORD MouseX, MouseY;         /* 0x20, 0x22 */
        ULONG Seconds, Micros;       /* 0x24, 0x28 */
        struct Window *IDCMPWindow;  /* 0x2C */
        struct IntuiMessage *SpecialLink;  /* 0x30 */
    };  /* size 0x34 */

IDCMP_* flag values from the same header (lines 863-882). The classic
``WaitPort``/``GetMsg`` split (WaitPort reports the first queued message
without removing it; GetMsg removes it) is what the app's drain loop
``WaitPort(); while ((msg = GT_GetIMsg(...)))`` relies on — see
``amiga_apps/itidy1classic/source/src/GUI/main_window.c``
(``handle_itidy_window_events``) and ``exec_library.py``.
"""

from __future__ import annotations

from typing import Any

from ..host.scheduler import WaitResource

# --- struct IntuiMessage (iTidy target layout) --------------------------------
#
# The iTidy binary was built against NDK headers whose ``struct Message`` is
# 0x14 bytes (one ULONG wider than the classic 0x10-byte layout), which shifts
# every ``IntuiMessage`` field after ``im_Message`` by +0x04 relative to the
# classic offsets. This was established by targeted disassembly of
# ``handle_itidy_window_events`` (the app reads ``im_Class`` from ``msg+0x14``
# and ``im_IAddress`` from ``msg+0x1c``) and confirmed by runtime memory
# evidence (the app observed 0x00 at those offsets when the classic layout was
# posted). See docs/apps/itidy/compatibility-notes.md.
IMSG_SIZE = 0x34
IMSG_OFF_REPLYMSG = 0x00  # APTR struct MsgPort * (from struct Message)
IMSG_OFF_LN_TYPE = 0x04  # UBYTE (from struct Message.Node)
IMSG_OFF_LN_PRI = 0x05  # BYTE (from struct Message.Node)
IMSG_OFF_LN_SUCC = 0x08  # APTR (from struct Message.Node)
IMSG_OFF_LN_PRED = 0x0C  # APTR (from struct Message.Node)
IMSG_OFF_CLASS = 0x14  # ULONG
IMSG_OFF_CODE = 0x18  # UWORD
IMSG_OFF_QUALIFIER = 0x1A  # UWORD (padding between Code and IAddress)
IMSG_OFF_IADDRESS = 0x1C  # APTR
IMSG_OFF_MOUSEX = 0x20  # WORD
IMSG_OFF_MOUSEY = 0x22  # WORD (consecutive with MouseX: ``WORD MouseX, MouseY;``)
IMSG_OFF_SECONDS = 0x24  # ULONG
IMSG_OFF_MICROS = 0x28  # ULONG
IMSG_OFF_IDCMPWINDOW = 0x2C  # APTR struct Window *
IMSG_OFF_SPECIALLINK = 0x30  # APTR struct IntuiMessage *

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

    ``schedule_*`` is the *pre-open* form: the event waits until a window that
    admits the class opens. A live Qt host instead drives the address-based
    forms from widget callbacks — ``gadget_up()`` for a projected BUTTON and
    ``request_close_window()`` for a host window-manager close request.
    The library impls reach the bridge through the ``event_bridge`` context
    extra attribute (registered by the launcher); without it (plain probes)
    the bridge simply never gets hooks and behaviour is unchanged.
    """

    def __init__(self) -> None:
        # The live vamos context (set on the first window open). The Qt host
        # path reaches the bridge from a widget signal callback that has no
        # direct ``ctx`` handle, so the bridge stores it here to allocate
        # messages and reach the exec PortManager.
        self._ctx: Any = None
        # The exec PortManager, captured at the first window open while the
        # intuition ctx is known-good. Re-looking it up later via
        # ``ctx.vlib_mgr`` is fragile: the vlib registry a lazy LibCtx exposes
        # does not always retain the bootstrap exec lib, so the captured handle
        # is authoritative for queueing messages.
        self._port_mgr: Any = None
        # window addr -> {"title": str, "idcmp": int, "user_port": int,
        #                 "window_port": int}  (insertion order = open order)
        self._windows: dict[int, dict] = {}
        # gadget addr -> gadget id (registered by CreateGadgetA)
        self._gadgets: dict[int, int] = {}
        # scheduled but not yet delivered events (in schedule order)
        self._pending: list[dict] = []
        # window addr -> the IntuiMessage address of the close-window event that
        # is currently *in flight* for it (posted, not yet released by the app).
        # This is what makes repeated host close requests idempotent: a second
        # request while the first is unanswered posts nothing new.
        self._close_pending: dict[int, int] = {}
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
        self._ctx = ctx
        if self._port_mgr is None:
            self._port_mgr = self._get_port_mgr(ctx)
        self._windows[window_addr] = {
            "title": title,
            "idcmp": idcmp_flags,
            "user_port": user_port_addr,
            "window_port": window_port_addr,
        }
        # A freshly opened window is a fresh close lifecycle: drop any stale
        # in-flight marker left by an earlier window that reused this address
        # (the emulated allocator recycles blocks), so a new window's first
        # host close request is never swallowed.
        self._close_pending.pop(window_addr, None)
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

    def unregister_gadget(self, gadget_addr: int) -> None:
        """Forget a freed gadget (called from ``FreeGadgets``).

        A host widget that outlives the emulated gadget is stale: dropping the
        registration makes a later activation a no-op rather than a message the
        app would dereference through a freed ``struct Gadget *``.
        """
        if gadget_addr:
            self._gadgets.pop(gadget_addr, None)

    def on_window_closed(self, window_addr: int) -> None:
        """Forget a closed window and the gadgets it owned (stale guard).

        Called from ``CloseWindow``. A projected widget (or a late window-manager
        close callback) that fires after the Amiga window is gone must not post
        into a released ``UserPort``: dropping the window record makes any such
        activation a no-op, and repeated closes are idempotent.
        """
        info = self._windows.pop(window_addr, None)
        if info is None:
            return
        # The close lifecycle ends with the window: forget its in-flight close
        # marker (a late window-manager request is now rejected by the missing
        # window record above, and a recycled address starts clean).
        self._close_pending.pop(window_addr, None)
        # Gadget registrations do not currently carry window ownership, so do
        # not guess by deleting the global gadget map here: that would corrupt
        # every other projected window. ``FreeGadgets`` unregisters the actual
        # released chain. A late callback for this window is already rejected
        # by the missing window record above.

    def gadget_up(
        self,
        window_addr: int,
        gadget_addr: int,
        *,
        code: int = 0,
        mousex: int = 0,
        mousey: int = 0,
    ) -> int | None:
        """Translate one projected-gadget activation into a real ``IntuiMessage``.

        This is the Qt-free semantic path a projected button's activation is
        routed through. It is *address-based* (``window_addr`` / ``gadget_addr``
        are the real emulated addresses recorded on the widget) — it never
        matches a label string, a hard-coded ``GadgetID`` or a window title.

        Steps, in order:
        1. verify the owning window is still open and requested ``IDCMP_GADGETUP``
           (real Intuition never generates a class a window did not request);
        2. verify the gadget is still registered (not freed / released);
        3. allocate and fill a complete real ``IntuiMessage`` (``IAddress`` = the
           real emulated ``struct Gadget *``, so the app reads the genuine
           ``GadgetID`` from that structure);
        4. enqueue it on the owning ``Window.UserPort``;
        5. only *after* the queue insertion, notify the scheduler (a hint to
           recheck the real port).

        Returns the ``IntuiMessage`` address, or ``None`` when the activation is
        stale or filtered out (recorded in ``self.skipped``).
        """
        info = self._windows.get(window_addr)
        if info is None:
            self.skipped.append(f"gadgetup: window {window_addr:06x} not open (stale activation)")
            return None
        if not (info["idcmp"] & IDCMP_GADGETUP):
            self.skipped.append(f"gadgetup: window {window_addr:06x} did not request IDCMP_GADGETUP")
            return None
        if gadget_addr not in self._gadgets:
            self.skipped.append(f"gadgetup: gadget {gadget_addr:06x} not registered (released)")
            return None
        if self._ctx is None:
            self.skipped.append("gadgetup: no live context to allocate the message")
            return None
        imsg = self.post_event(
            self._ctx,
            window_addr,
            IDCMP_GADGETUP,
            code=code,
            iaddress=gadget_addr,
            mousex=mousex,
            mousey=mousey,
        )
        # The message is on the real UserPort now; only then is the hint
        # meaningful. The scheduler rechecks the real queue before resuming.
        scheduler = getattr(self._ctx, "scheduler", None)
        if scheduler is not None:
            scheduler.notify_resource_changed(WaitResource.MESSAGE_PORT, info["user_port"])
        return imsg

    def request_close_window(self, window_addr: int) -> int | None:
        """Translate one *host window-manager* close request into a real event.

        The live counterpart of :meth:`schedule_close_window`, exactly as
        :meth:`gadget_up` is the live counterpart of :meth:`schedule_gadget_up`:
        a host close request arrives while the window is already open and the
        target is parked in ``WaitPort``, so the event must go to *that* window
        now — not sit in the pre-open pending list waiting for a window that is
        never opened again. It is address-based (``window_addr`` is the real
        ``struct Window *`` recorded on the host widget), never title- or
        label-based.

        Steps, in the same order as :meth:`gadget_up`:

        1. verify the window is still open (a request racing the app's own
           ``CloseWindow`` is an honest no-op);
        2. verify it requested ``IDCMP_CLOSEWINDOW`` (real Intuition never
           generates a class a window did not request);
        3. verify no close-window message is already in flight for it —
           repeated host close requests (double click, a click while the first
           is still unanswered) are idempotent no-ops, not duplicate messages;
        4. allocate and fill a real ``IntuiMessage`` of class
           ``IDCMP_CLOSEWINDOW`` (``IAddress`` = 0: a close request carries no
           gadget; the window identity is ``IDCMPWindow``);
        5. only *after* the queue insertion, notify the scheduler (a hint to
           recheck the real port).

        Returns the ``IntuiMessage`` address, or ``None`` when the request was
        stale, filtered or a duplicate (recorded in ``self.skipped``). The host
        window is *not* destroyed here: only the app's own ``CloseWindow``
        releases the projection (see ``docs/architecture/
        cooperative-host-scheduler.md`` "Window Close Semantics").
        """
        info = self._windows.get(window_addr)
        if info is None:
            self.skipped.append(f"closewindow: window {window_addr:06x} not open (stale request)")
            return None
        if not (info["idcmp"] & IDCMP_CLOSEWINDOW):
            self.skipped.append(
                f"closewindow: window {window_addr:06x} did not request IDCMP_CLOSEWINDOW"
            )
            return None
        if window_addr in self._close_pending:
            self.skipped.append(
                f"closewindow: window {window_addr:06x} close request already pending (idempotent)"
            )
            return None
        if self._ctx is None:
            self.skipped.append("closewindow: no live context to allocate the message")
            return None
        imsg = self.post_event(self._ctx, window_addr, IDCMP_CLOSEWINDOW)
        # In flight until the app replies to *this* message (see release_message).
        self._close_pending[window_addr] = imsg
        scheduler = getattr(self._ctx, "scheduler", None)
        if scheduler is not None:
            scheduler.notify_resource_changed(WaitResource.MESSAGE_PORT, info["user_port"])
        return imsg

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
        # Prefer the captured exec PortManager (set at the first window open,
        # when the intuition ctx is known-good); fall back to a live lookup.
        port_mgr = self._port_mgr
        if port_mgr is None:
            port_mgr = self._get_port_mgr(ctx)
        user_port = info["user_port"]
        if port_mgr is None or not port_mgr.has_port(user_port):
            raise RuntimeError(f"event bridge: UserPort {user_port:06x} not registered with PortManager")
        # Classic per-message lifetime: allocate one real IntuiMessage block per
        # event (freed by ``release_message`` when the app replies). The machine
        # buffer is alive for the whole run — a projected-gadget click is
        # serviced on the GUI thread while the target is parked in the scheduler
        # (same thread, machine not yet cleaned up) — so the allocator's block
        # erase is safe here.
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
        # ``WORD MouseX, MouseY;`` are consecutive words (0x20, 0x22) — no
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
                "port": user_port,
            }
        )
        return imsg

    def release_message(self, ctx, imsg_addr: int) -> None:
        """Free an IntuiMessage consumed via GT_GetIMsg (GT_ReplyIMsg side).

        The classic reply (PutMsg to ``msg->ReplyMsg`` / the WindowPort) has
        no consumer on the headless host — nothing ever waits on the
        WindowPort — so the observable work is releasing the block the bridge
        allocated. The app replies on the GUI thread while the machine is alive
        (it is resuming from the scheduler), so the free is safe. Addresses the
        bridge did not allocate are ignored (they would belong to a PutMsg the
        host cannot own).
        """
        if not imsg_addr:
            return
        mem = self._imsgs.pop(imsg_addr, None)
        if mem is not None:
            ctx.alloc.free_memory(mem)
            self.released.append(imsg_addr)
            # The app acknowledged this message. If it was the in-flight
            # host close-window request, that window's close request is no
            # longer outstanding — a later request is a fresh event, not a
            # duplicate of one the app already answered.
            for addr, pending in list(self._close_pending.items()):
                if pending == imsg_addr:
                    del self._close_pending[addr]

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
