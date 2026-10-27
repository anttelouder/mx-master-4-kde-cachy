"""Минимальный HID++ 2.0 клиент для MX Master 4 через Logitech-приёмник (/dev/hidraw*).

Общий для mouse-buzz.py, mousectl.py и кольца действий. Находит приёмник и слот мыши
по фиче HAPTIC (0x19B0), кеширует hidraw/слот в ~/.cache/mouse-buzz.json; индексы фич
узнаёт через ROOT.getFeature при каждом подключении и держит в памяти процесса.

Особенности, пойманные 25–26.10.2026:
- спящая мышь или пустой слот — приёмник отвечает на запись EPIPE;
- после простоя мышь отвечает через ~0,9 с (активная — за ~6 мс), поэтому таймаут 1,5 с;
- свой software id (0x0E), чтобы не путать ответы с трафиком logid;
- hidraw раздаёт каждый ответ всем, кто открыл устройство, а наши процессы (виджет, кольцо,
  mouse-buzz) ходят с одним software id — без очереди один забирал чужой ответ. Так в кэш
  однажды попал индекс FEATURE SET вместо HAPTIC, и вибрация молча перестала работать.
  Поэтому запрос-ответ идёт под общей блокировкой (flock), перед запросом старые ответы
  вычитываются, а индексы фич в кэш больше не пишутся.
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
    """Мышь не отвечает: выключена, спит слишком глубоко или не подключена."""


@contextlib.contextmanager
def _exclusive():
    """Один запрос-ответ на приёмнике за раз — между всеми нашими процессами."""
    os.makedirs(os.path.dirname(LOCK), exist_ok=True)
    lock = os.open(LOCK, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600)
    try:
        fcntl.flock(lock, fcntl.LOCK_EX)
        yield
    finally:
        os.close(lock)


def request(fd, dev, feat_idx, fn, params=b"", timeout=1.5):
    """Длинный HID++ 2.0 запрос; возвращает параметры ответа или None (ошибка/таймаут)."""
    func = (fn << 4) | SW_ID
    msg = bytes([0x11, dev, feat_idx, func]) + params
    with _exclusive():
        while select.select([fd], [], [], 0)[0]:       # опоздавшие ответы на прошлые запросы
            os.read(fd, 64)
        os.write(fd, msg.ljust(20, b"\0"))
        deadline = time.monotonic() + timeout
        while (left := deadline - time.monotonic()) > 0:
            if not select.select([fd], [], [], left)[0]:
                break
            r = os.read(fd, 64)
            if len(r) < 5 or r[1] != dev:
                continue
            if r[2] == 0xFF and r[3] == feat_idx and r[4] == func:   # ошибка HID++ 2.0 на наш запрос
                return None
            if r[0] == 0x10 and r[2] == 0x8F and r[3] == feat_idx:  # ошибка HID++ 1.0 (нет устройства)
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
    """Перебор приёмников и слотов 1–6: где отвечает фича HAPTIC."""
    feat = F_HAPTIC.to_bytes(2, "big")
    for path in receivers():
        try:
            fd = os.open(path, os.O_RDWR)
        except OSError:
            continue
        try:
            for dev in range(1, 7):
                try:  # пустой слот или спящая мышь — приёмник отвечает EPIPE
                    r = request(fd, dev, 0x00, 0, feat)  # ROOT.getFeature
                except OSError:
                    continue
                if r and r[0]:
                    return {"path": path, "dev": dev}
        finally:
            os.close(fd)
    return None


class Mouse:
    """Открытое соединение с мышью; использовать через `with Mouse() as m:`."""

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
                if self.feature_index(F_HAPTIC) is not None:  # в этом слоте мышь с вибрацией и она на связи
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
        """Вызов функции фичи; None — фичи нет или мышь не ответила."""
        idx = self.feature_index(feature)
        if idx is None:
            return None
        try:
            return request(self.fd, self.target["dev"], idx, fn, params)
        except OSError:
            return None
