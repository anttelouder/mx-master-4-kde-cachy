"""Minimal HID++ 2.0 client for the MX Master 4 through a Logitech receiver (/dev/hidraw*).

Shared by mouse-buzz.py, mousectl.py and the actions ring. Finds the receiver and the mouse slot
by the HAPTIC feature (0x19B0), caches the hidraw/slot in ~/.cache/mouse-buzz.json; feature
indices are looked up through ROOT.getFeature on every connection and kept in process memory.

Gotchas caught on 25–26.10.2026:
- a sleeping mouse or an empty slot — the receiver answers the write with EPIPE;
- after idling the mouse answers in ~0.9 s (active — in ~6 ms), hence the 1.5 s timeout;
- its own software id (0x0E) so replies are not confused with logid traffic;
- hidraw delivers every reply to everyone who opened the device, and our processes (widget, ring,
  mouse-buzz) use a single software id — without queueing one of them grabbed someone else's reply.
  That is how a FEATURE SET index once ended up in the cache instead of HAPTIC, and the haptics
  silently stopped working. So a request-reply runs under a shared lock (flock), stale replies are
  drained before a request, and feature indices are no longer written to the cache.
"""
import contextlib
import fcntl
import glob
import json
import os
import select
import time

SW_ID = 0x0E
CACHE = os.path.expanduser("~/.cache/mouse-buzz.json")
LOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache"), "mx-hidpp.lock")

F_ROOT = 0x0000
F_BATTERY = 0x1004       # UNIFIED BATTERY
F_HAPTIC = 0x19B0
F_SMARTSHIFT = 0x2111    # SMART SHIFT ENHANCED
F_DPI = 0x2201           # ADJUSTABLE DPI


class NoMouse(Exception):
    """The mouse is not responding: switched off, too deeply asleep, or not connected."""


@contextlib.contextmanager
def _exclusive():
    """One request-reply on the receiver at a time — across all our processes."""
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
    finally:
        os.close(lock)


def request(fd, dev, feat_idx, fn, params=b"", timeout=1.5):
    """Long HID++ 2.0 request; returns the reply parameters or None (error/timeout)."""
    func = (fn << 4) | SW_ID
    msg = bytes([0x11, dev, feat_idx, func]) + params
    with _exclusive():
        while select.select([fd], [], [], 0)[0]:       # late replies to previous requests
            os.read(fd, 64)
        os.write(fd, msg.ljust(20, b"\0"))
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            if not select.select([fd], [], [], left)[0]:
                break
            r = os.read(fd, 64)
            if len(r) < 5 or r[1] != dev:
                continue
            if r[2] == 0xFF and r[3] == feat_idx and r[4] == func:   # HID++ 2.0 error for our request
                return None
            if r[0] == 0x10 and r[2] == 0x8F and r[3] == feat_idx:  # HID++ 1.0 error (no device)
                return None
            if r[2] == feat_idx and r[3] == func:
                return r[4:]
    return None


def receivers():
    for h in sorted(glob.glob("/sys/class/hidraw/hidraw*")):
        try:
            uevent = open(os.path.join(h, "device/uevent")).read()
        except OSError:
            continue
        if "HID_NAME=Logitech" in uevent and "Receiver" in uevent:
            yield "/dev/" + os.path.basename(h)


def discover():
    """Scan the receivers and slots 1–6: wherever the HAPTIC feature answers."""
    feat = F_HAPTIC.to_bytes(2, "big")
    for path in receivers():
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError:
            continue
        try:
            for dev in range(1, 7):
                try:  # empty slot or sleeping mouse — the receiver answers EPIPE
                    r = request(fd, dev, 0x00, 0, feat)  # ROOT.getFeature
                except OSError:
                    continue
                if r and r[0]:
                    return {"path": path, "dev": dev}
        finally:
            os.close(fd)
    return None


class Mouse:
    """An open connection to the mouse; use as `with Mouse() as m:`."""

    def __init__(self):
        self.fd = None
        self.target = None
        self.features = {}

    def __enter__(self):
        for attempt in ("cache", "discover"):
            if attempt == "cache":
                try:
                    self.target = json.load(open(CACHE))
                except (OSError, ValueError):
                    continue
            else:
                self.target = discover()
                if not self.target:
                    break
                os.makedirs(os.path.dirname(CACHE), exist_ok=True)
                json.dump(self.target, open(CACHE, "w"))
            try:
                self.fd = os.open(self.target["path"], os.O_RDWR)
                self.features = {}
                if self.feature_index(F_HAPTIC) is not None:  # this slot has a haptic-capable mouse and it is online
                    return self
            except (OSError, KeyError):
                pass
            self.close()
        raise NoMouse()

    def __exit__(self, *exc):
        self.close()

    def close(self):
        if self.fd is not None:
            os.close(self.fd)
            self.fd = None

    def feature_index(self, feature):
        if feature not in self.features:
            r = request(self.fd, self.target["dev"], 0x00, 0, feature.to_bytes(2, "big"))
            self.features[feature] = r[0] if r and r[0] else None
        return self.features[feature]

    def call(self, feature, fn, params=b""):
        """Call a feature function; None — no such feature or the mouse did not answer."""
        idx = self.feature_index(feature)
        if idx is None:
            return None
        try:
            return request(self.fd, self.target["dev"], idx, fn, params)
        except OSError:
            return None
