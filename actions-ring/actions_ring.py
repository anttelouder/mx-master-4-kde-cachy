#!/usr/bin/env python3
"""Кольцо действий для MX Master 4 на KDE Wayland — аналог Actions Ring из Logi Options+.

    actions-ring              служба: держит скрытое окно-кольцо и канал к мыши
    actions-ring show         показать кольцо у курсора (повторный вызов — закрыть)
    actions-ring hide

Нажатие на haptic-панель → logid шлёт Meta+Shift+S → xremap (только с мыши)
запускает `actions-ring show` → служба показывает кольцо через сокет
$XDG_RUNTIME_DIR/actions-ring.sock. Окно — layer-shell поверх всего на активном
экране; центр кольца ставится туда, где wl_pointer.enter сообщил курсор.

При переходе курсора на другой сектор мышь коротко вибрирует (HID++ HAPTIC,
канал к приёмнику держится открытым, отклик ~10 мс у активной мыши).

Набор действий — ~/.config/actions-ring/ring.json (если нет — config/actions-ring.json),
правится во вкладке «Кольцо» виджета мыши. Действие (kind): app — приложение по id
.desktop, kde — глобальное действие KDE (kglobalaccel), cmd — команда, folder — вложенное
кольцо. Кольца под приложения — в "apps": первое, у которого регулярка match совпала
с классом активного окна; класс сообщает KWin-скрипт через D-Bus (org.mxmaster4.ActionsRing).
"""
import json
import os
import queue
import re
import shlex
import socket
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
import hidpp  # noqa: E402

SOCK = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache"), "actions-ring.sock")
CONFIGS = [os.path.expanduser("~/.config/actions-ring/ring.json"),
           os.path.join(os.path.dirname(HERE), "config", "actions-ring.json")]
WAVEFORMS = {"SHARP_STATE_CHANGE": 0x00, "DAMP_STATE_CHANGE": 0x01, "SHARP_COLLISION": 0x02,
             "DAMP_COLLISION": 0x03, "SUBTLE_COLLISION": 0x04, "WHISPER_COLLISION": 0x1B,
             "HAPPY_ALERT": 0x05, "COMPLETED": 0x07, "KNOCK": 0x0C}
SLOTS = 8
DBUS_NAME = "org.mxmaster4.ActionsRing"

# Сообщает службе класс каждого активированного окна (кроме самого кольца).
KWIN_SCRIPT = """
function report(w) {
    if (!w || w.resourceClass === "actions-ring") return;
    callDBus("%s", "/", "%s", "setActiveWindow", String(w.resourceClass || ""), String(w.caption || ""));
}
workspace.windowActivated.connect(report);
report(workspace.activeWindow);
""" % (DBUS_NAME, DBUS_NAME)


def client(cmd):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(0.5)
    try:
        s.connect(SOCK)
        s.sendall(cmd.encode() + b"\n")
    except OSError:
        print("служба actions-ring не запущена", file=sys.stderr)
        return 1
    return 0


def load_config():
    for path in CONFIGS:
        try:
            return json.load(open(path))
        except (OSError, ValueError):
            continue
    return {"items": []}


def slots(items):
    """Ровно 8 позиций; пустая позиция — None (сектор не подсвечивается)."""
    items = list(items or [])[:SLOTS]
    items += [None] * (SLOTS - len(items))
    return [i if i and (i.get("kind") or i.get("cmd") or i.get("items")) else None for i in items]


def argv_for(item):
    kind = item.get("kind") or ("folder" if "items" in item else "cmd")
    if kind == "app" and item.get("app"):
        return ["kstart", "--application", item["app"]]
    if kind == "kde" and item.get("shortcut"):
        sc = item["shortcut"]
        return ["qdbus6", "org.kde.kglobalaccel", "/component/" + sc["component"],
                "org.kde.kglobalaccel.Component.invokeShortcut", sc["name"]]
    if kind == "cmd" and item.get("cmd"):
        return shlex.split(item["cmd"]) if isinstance(item["cmd"], str) else item["cmd"]
    return None


class Haptics(threading.Thread):
    """Очередь на один сигнал: пока мышь отвечает, новые наведения вытесняют старые."""

    def __init__(self):
        super().__init__(daemon=True)
        self.q = queue.Queue(maxsize=1)
        self.mouse = None
        self.retry_at = 0.0

    def play(self, name):
        if name not in WAVEFORMS:
            return
        try:
            self.q.get_nowait()
        except queue.Empty:
            pass
        self.q.put_nowait(name)

    def connect(self):
        if self.mouse is None and time.monotonic() >= self.retry_at:
            try:
                self.mouse = hidpp.Mouse().__enter__()
            except hidpp.NoMouse:
                self.retry_at = time.monotonic() + 5
        return self.mouse

    def run(self):
        self.connect()  # прогрев: найти приёмник до первого показа
        while True:
            name = self.q.get()
            m = self.connect()
            if m and m.call(hidpp.F_HAPTIC, 4, bytes([WAVEFORMS[name]])) is None:
                m.close()  # мышь уснула или переподключилась — откроем заново
                self.mouse = None


def serve():
    from PyQt6.QtCore import (QObject, QSocketNotifier, QTimer, QUrl, pyqtClassInfo,
                              pyqtProperty, pyqtSignal, pyqtSlot)
    from PyQt6.QtDBus import QDBusConnection, QDBusInterface
    from PyQt6.QtGui import QGuiApplication
    from PyQt6.QtQml import QQmlApplicationEngine

    class Ring(QObject):
        showRequested = pyqtSignal()
        hideRequested = pyqtSignal()
        changed = pyqtSignal()

        def __init__(self, haptics):
            super().__init__()
            self.haptics = haptics
            self.config = load_config()
            self.window_class = ""
            self.recent = {}  # класс окна → заголовок, для выбора в виджете
            self._items, self._title = slots(self.config.get("items")), ""

        @pyqtProperty("QVariantList", notify=changed)
        def items(self):
            return self._items

        @pyqtProperty(str, notify=changed)
        def title(self):
            return self._title

        def set_active_window(self, cls, caption):
            self.window_class = cls
            if cls:
                self.recent.pop(cls, None)
                self.recent[cls] = caption

        def prepare(self):
            """Перед показом: перечитать конфиг и выбрать кольцо под активное окно."""
            self.config = load_config()
            items, title = self.config.get("items"), ""
            for app in self.config.get("apps", []):
                try:
                    if app.get("match") and re.search(app["match"], self.window_class, re.I):
                        items, title = app.get("items"), app.get("name", "")
                        break
                except re.error:
                    continue
            self._items, self._title = slots(items), title
            self.changed.emit()


        @pyqtSlot("QVariant", result="QVariantList")
        def slotsOf(self, items):
            return slots(items)

        @pyqtSlot(int)
        def hover(self, index):
            self.haptics.play(self.config.get("hover_haptic", "SUBTLE_COLLISION"))

        @pyqtSlot()
        def enterFolder(self):
            self.haptics.play(self.config.get("folder_haptic", "SHARP_STATE_CHANGE"))

        @pyqtSlot("QVariant")
        def run(self, item):
            self.haptics.play(self.config.get("activate_haptic", "DAMP_STATE_CHANGE"))
            argv = argv_for(item or {})
            if argv:  # после скрытия окна, чтобы фокус успел вернуться
                QTimer.singleShot(60, lambda: subprocess.Popen(
                    argv, start_new_session=True,
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL))

    @pyqtClassInfo("D-Bus Interface", DBUS_NAME)
    class DBusApi(QObject):
        """Наружу по D-Bus: KWin-скрипт сообщает активное окно, виджет берёт список недавних."""

        def __init__(self, ring):
            super().__init__()
            self.ring = ring

        @pyqtSlot(str, str)
        def setActiveWindow(self, cls, caption):
            self.ring.set_active_window(cls, caption)

        @pyqtSlot(result=str)
        def recentWindows(self):  # JSON [{class, caption}], свежие первыми
            return json.dumps([{"class": c, "caption": t} for c, t in reversed(self.ring.recent.items())],
                              ensure_ascii=False)

    app = QGuiApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)
    haptics = Haptics()
    haptics.start()
    ring = Ring(haptics)

    bus = QDBusConnection.sessionBus()
    bus.registerService(DBUS_NAME)
    bus_api = DBusApi(ring)
    bus.registerObject("/", bus_api, QDBusConnection.RegisterOption.ExportAllSlots)
    # KWin выполнит этот файл в сессии пользователя — только в личном каталоге (0700), не в /tmp
    script = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or os.path.expanduser("~/.cache"), "actions-ring-kwin.js")
    os.makedirs(os.path.dirname(script), exist_ok=True)
    fd = os.open(script, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, "w") as f:
        f.write(KWIN_SCRIPT)
    kwin = QDBusInterface("org.kde.KWin", "/Scripting", "org.kde.kwin.Scripting", bus)
    kwin.call("unloadScript", "actions-ring")
    reply = kwin.call("loadScript", script, "actions-ring")
    if reply.arguments() and isinstance(reply.arguments()[0], int) and reply.arguments()[0] >= 0:
        QDBusInterface("org.kde.KWin", f"/Scripting/Script{reply.arguments()[0]}",
                       "org.kde.kwin.Script", bus).call("run")
    else:
        print("KWin-скрипт не загрузился: кольца под приложения не работают", file=sys.stderr)

    if os.path.lexists(SOCK):
        os.unlink(SOCK)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCK)
    srv.listen(4)
    srv.setblocking(False)

    def on_conn():
        try:
            conn, _ = srv.accept()
        except BlockingIOError:
            return
        with conn:
            conn.settimeout(0.2)
            try:
                cmd = conn.recv(64).decode().strip()
            except OSError:
                return
        if cmd == "show":
            ring.prepare()
            ring.showRequested.emit()
        elif cmd == "hide":
            ring.hideRequested.emit()

    notifier = QSocketNotifier(srv.fileno(), QSocketNotifier.Type.Read)
    notifier.activated.connect(on_conn)

    engine = QQmlApplicationEngine()
    engine.rootContext().setContextProperty("ring", ring)
    engine.load(QUrl.fromLocalFile(os.path.join(HERE, "ring.qml")))
    if not engine.rootObjects():
        sys.exit(1)
    rc = app.exec()
    kwin.call("unloadScript", "actions-ring")
    sys.exit(rc)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        sys.exit(client(sys.argv[1]))
    serve()
