#!/usr/bin/env python3
"""Бэкенд виджета KDE «MX Master 4»: состояние мыши и служб в JSON, команды настройки.

    mousectl status [--enforce]    всё состояние одним JSON (виджет опрашивает раз в 30 с)
    mousectl set dpi|haptic|threshold|torque|freespin ЗНАЧЕНИЕ
    mousectl buzz СИГНАЛ
    mousectl service xremap|ring|meetings start|stop|restart
    mousectl bindings [get]        кнопки по профилям приложений + каталог действий (модель — buttons.py)
    mousectl bindings set JSON     записать профили (JSON в percent-кодировке), проверить и перезапустить xremap
    mousectl bindings reset        стандартная раскладка «Всех приложений» (профили приложений остаются)
    mousectl wheel toggle          колесо: щелчки ↔ свободное вращение
    mousectl ring get              кольцо действий: конфиг, приложения, действия KDE, недавние окна
    mousectl ring set JSON         записать конфиг кольца (JSON в percent-кодировке, как encodeURIComponent)
    mousectl ring show             показать кольцо

Настройки мыши (DPI, сила вибрации, порог и тугость SmartShift) пишутся по HID++
напрямую и запоминаются в ~/.config/mousectl/settings.json. `status --enforce`
возвращает их на мышь, если они сбились (после выключения мыши и т. п.). Режим колеса
(щелчки / свободное) не запоминается: его переключает кнопка за колесом, и виджет не должен
её перебивать. logid эти параметры не задаёт (их нет в config/logid.cfg), иначе он перетирал бы
их при каждом пробуждении мыши.

Задел на расширение: новые команды — новые функции cmd_* и строка в COMMANDS;
виджет вызывает `mousectl <команда>` и разбирает JSON из stdout.
"""
import json
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.realpath(__file__))
sys.path.insert(0, HERE)
import hidpp  # noqa: E402

SETTINGS = os.path.expanduser("~/.config/mousectl/settings.json")
XREMAP_CONFIG = os.path.expanduser("~/.config/xremap/config.yml")
WAVEFORMS = ["COMPLETED", "HAPPY_ALERT", "ANGRY_ALERT", "KNOCK", "RINGING", "JINGLE",
             "FIREWORK", "WAVE", "SQUARE", "MAD", "SHARP_STATE_CHANGE", "DAMP_STATE_CHANGE",
             "SHARP_COLLISION", "DAMP_COLLISION", "SUBTLE_COLLISION", "WHISPER_COLLISION"]
# meetings — необязательный свой таймер напоминаний (в комплект не входит): переключатель
# в виджете показывается, только если такой юнит установлен
SERVICES = {"xremap": "xremap.service", "meetings": "meeting-buzz.timer", "ring": "actions-ring.service"}
RING_CONFIG = os.path.expanduser("~/.config/actions-ring/ring.json")
RING_DEFAULT = os.path.join(HERE, "config", "actions-ring.json")
RING_WAVEFORMS = ["SUBTLE_COLLISION", "WHISPER_COLLISION", "SHARP_COLLISION", "DAMP_COLLISION",
                  "SHARP_STATE_CHANGE", "DAMP_STATE_CHANGE", "HAPPY_ALERT", "COMPLETED", "KNOCK"]
# компоненты kglobalaccel, чьи действия предлагаются в кольцо
KDE_COMPONENTS = ["kwin", "plasmashell", "ksmserver", "mediacontrol", "kmix",
                  "org_kde_powerdevil", "KDE_Keyboard_Layout_Switcher"]
LIMITS = {"dpi": (200, 8000), "haptic": (0, 100), "threshold": (1, 50), "torque": (1, 100)}


def out(obj):
    print(json.dumps(obj, ensure_ascii=False))


# ---------- мышь ----------

def read_mouse(m):
    st = {"online": True}
    if (r := m.call(hidpp.F_BATTERY, 1)):
        st["battery"] = r[0]
        st["charging"] = r[2] in (1, 2)          # 1 — заряжается, 2 — почти полная на зарядке
    if (r := m.call(hidpp.F_DPI, 2, b"\0")):
        st["dpi"] = int.from_bytes(r[1:3], "big") or int.from_bytes(r[3:5], "big")
    if (r := m.call(hidpp.F_HAPTIC, 1)):
        st["haptic"] = r[1] if r[0] & 1 else 0
    if (r := m.call(hidpp.F_SMARTSHIFT, 1)):
        st["freespin"] = r[0] == 1
        st["threshold"] = min(r[1], 50)          # 255 = «всегда щелчки», показываем как 50
        st["torque"] = r[2]
    return st


def write_mouse(m, key, value, current):
    if key == "dpi":
        value = round(value / 50) * 50
        return m.call(hidpp.F_DPI, 3, bytes([0]) + value.to_bytes(2, "big")) is not None
    if key == "haptic":
        payload = bytes([0, 0x32]) if value == 0 else bytes([1, value])
        return m.call(hidpp.F_HAPTIC, 2, payload) is not None
    if key in ("threshold", "torque", "freespin"):
        # MX Master 4 применяет порог/тугость, только если записан и режим — пишем всё целиком
        mode = 2 if not current.get("freespin") else 1
        threshold = current.get("threshold", 20)
        torque = current.get("torque", 20)
        if key == "freespin":
            mode = 1 if value else 2
        elif key == "threshold":
            threshold = value
        else:
            torque = value
        raw_threshold = 255 if threshold >= 50 else threshold
        return m.call(hidpp.F_SMARTSHIFT, 2, bytes([mode, raw_threshold, torque])) is not None
    raise ValueError(key)


def load_settings():
    try:
        return json.load(open(SETTINGS))
    except (OSError, ValueError):
        return {}


def save_setting(key, value):
    s = load_settings()
    s[key] = value
    os.makedirs(os.path.dirname(SETTINGS), exist_ok=True)
    json.dump(s, open(SETTINGS, "w"), ensure_ascii=False, indent=2)


# ---------- службы ----------

def unit_active(unit, user=True):
    cmd = ["systemctl"] + (["--user"] if user else []) + ["is-active", unit]
    return subprocess.run(cmd, capture_output=True, text=True).stdout.strip() == "active"


def unit_installed(unit):
    r = subprocess.run(["systemctl", "--user", "list-unit-files", unit], capture_output=True, text=True)
    return unit in r.stdout


def logid_sees_mouse():
    """По журналу: после последнего «Detected receiver» была строка «Device found»."""
    r = subprocess.run(["journalctl", "-u", "logid", "-n", "200", "-o", "cat", "--no-pager"],
                       capture_output=True, text=True)
    found = None
    for line in r.stdout.splitlines():
        if "Detected receiver" in line:
            found = False
        elif "Device found" in line:
            found = True
    return found


# ---------- команды ----------

def cmd_status(args):
    enforce = "--enforce" in args
    st = {"mouse": {"online": False}, "desired": load_settings(), "enforced": [],
          "waveforms": WAVEFORMS, "limits": LIMITS}
    try:
        with hidpp.Mouse() as m:
            st["mouse"] = read_mouse(m)
            if enforce:
                for key, want in st["desired"].items():
                    if key in LIMITS and st["mouse"].get(key) not in (None, want):
                        if write_mouse(m, key, want, st["mouse"]):
                            st["mouse"][key] = want
                            st["enforced"].append(key)
    except hidpp.NoMouse:
        pass
    st["services"] = {
        "logid": {"active": unit_active("logid.service", user=False), "sees_mouse": logid_sees_mouse()},
        "xremap": {"active": unit_active(SERVICES["xremap"])},
        "meetings": {"active": unit_active(SERVICES["meetings"]), "installed": unit_installed(SERVICES["meetings"])},
        "ring": {"active": unit_active(SERVICES["ring"])},
    }
    out(st)
    return 0


def cmd_set(args):
    key, value = args[0], args[1]
    if key == "freespin":
        value = value.lower() in ("1", "true", "on", "yes")
    else:
        lo, hi = LIMITS[key]
        value = max(lo, min(hi, int(float(value))))
    try:
        with hidpp.Mouse() as m:
            current = read_mouse(m)
            ok = write_mouse(m, key, value, current)
            if ok and key != "freespin":
                save_setting(key, value)
            out({"ok": ok, "key": key, "value": value, "mouse": read_mouse(m)})
            return 0 if ok else 1
    except hidpp.NoMouse:
        if key != "freespin":       # применится через status --enforce, когда мышь проснётся
            save_setting(key, value)
        out({"ok": False, "error": "мышь не отвечает", "key": key, "value": value})
        return 1


def cmd_buzz(args):
    r = subprocess.run([os.path.join(HERE, "mouse-buzz.py"), args[0]])
    out({"ok": r.returncode == 0})
    return r.returncode


def cmd_service(args):
    name, action = args[0], args[1]
    if name not in SERVICES or action not in ("start", "stop", "restart"):
        out({"ok": False, "error": "неизвестная служба или действие"})
        return 2
    r = subprocess.run(["systemctl", "--user", action, SERVICES[name]], capture_output=True, text=True)
    out({"ok": r.returncode == 0, "error": r.stderr.strip(), "active": unit_active(SERVICES[name])})
    return r.returncode


def cmd_bindings(args):
    import yaml
    import buttons
    sub = args[0] if args else "get"
    def current():
        try:
            return yaml.safe_load(open(XREMAP_CONFIG)) or {}
        except FileNotFoundError:          # первый запуск: стандартная раскладка
            return {}

    if sub == "get":
        cfg = current()
        out(dict(buttons.ui_meta(), profiles=buttons.load_profiles(cfg, desktop_apps()),
                 config=XREMAP_CONFIG))
        return 0
    if sub in ("set", "reset"):
        import shutil
        import tempfile
        if sub == "set":
            from urllib.parse import unquote
            profiles = json.loads(unquote(args[1]))
            keymap = buttons.build_keymap(profiles, desktop_apps())
        else:                                   # стандартная раскладка, профили приложений сохраняются
            cfg = current()
            keymap = [km for km in cfg.get("keymap", []) if (km.get("application") or {}).get("only")]
            keymap += buttons.build_keymap(buttons.load_profiles({}, []), [])
        text = buttons.dump_config(keymap)
        os.makedirs(os.path.dirname(XREMAP_CONFIG), exist_ok=True)
        fd, tmp = tempfile.mkstemp(suffix=".yml", dir=os.path.dirname(XREMAP_CONFIG))
        with os.fdopen(fd, "w") as f:
            f.write(text)
        r = subprocess.run(["xremap", "--validate-config", tmp], capture_output=True, text=True)
        if r.returncode != 0:
            os.unlink(tmp)
            out({"ok": False, "error": "xremap не принял конфиг: " + (r.stderr or r.stdout).strip()[-300:]})
            return 1
        if os.path.exists(XREMAP_CONFIG):
            shutil.copy2(XREMAP_CONFIG, XREMAP_CONFIG + ".bak")
        os.replace(tmp, XREMAP_CONFIG)
        r = subprocess.run(["systemctl", "--user", "restart", SERVICES["xremap"]], capture_output=True, text=True)
        out({"ok": r.returncode == 0, "error": r.stderr.strip()})
        return r.returncode
    raise ValueError(sub)


def cmd_wheel(args):
    """wheel toggle — колесо: щелчки ↔ свободное вращение (для кнопки за колесом)."""
    if args[0] != "toggle":
        raise ValueError(args[0])
    try:
        with hidpp.Mouse() as m:
            cur = read_mouse(m)
            ok = write_mouse(m, "freespin", not cur.get("freespin"), cur)
            out({"ok": ok, "freespin": not cur.get("freespin")})
            return 0 if ok else 1
    except hidpp.NoMouse:
        out({"ok": False, "error": "мышь не отвечает"})
        return 1


# ---------- кольцо действий ----------

def desktop_apps():
    """Видимые приложения из .desktop: id, название (на языке системы, если есть), иконка."""
    lang = (os.environ.get("LANG") or "en")[:2]
    dirs = ["/usr/share/applications", os.path.expanduser("~/.local/share/applications"),
            "/var/lib/flatpak/exports/share/applications"]
    apps = {}
    for d in dirs:
        try:
            names = os.listdir(d)
        except OSError:
            continue
        for fn in names:
            if not fn.endswith(".desktop"):
                continue
            entry, section = {}, None
            try:
                for line in open(os.path.join(d, fn), encoding="utf-8", errors="replace"):
                    line = line.strip()
                    if line.startswith("["):
                        section = line
                    elif section == "[Desktop Entry]" and "=" in line:
                        k, v = line.split("=", 1)
                        entry.setdefault(k.strip(), v.strip())
            except OSError:
                continue
            if (entry.get("Type") != "Application" or entry.get("NoDisplay") == "true"
                    or entry.get("Hidden") == "true"):
                continue
            name = entry.get(f"Name[{lang}]") or entry.get("Name") or fn[:-8]
            apps[fn[:-8]] = {"id": fn[:-8], "name": name, "icon": entry.get("Icon", ""),
                             "wmclass": entry.get("StartupWMClass", "")}
    return sorted(apps.values(), key=lambda a: a["name"].lower())


def kde_shortcuts():
    try:
        import dbus
        bus = dbus.SessionBus()
    except Exception:  # noqa: BLE001 — нет dbus-python или сессии: просто без действий KDE
        return []
    result = []
    for comp in KDE_COMPONENTS:
        try:
            obj = bus.get_object("org.kde.kglobalaccel", "/component/" + comp)
            infos = obj.allShortcutInfos(dbus_interface="org.kde.kglobalaccel.Component")
        except dbus.DBusException:
            continue
        for i in infos:
            result.append({"component": comp, "componentName": str(i[3]),
                           "name": str(i[0]), "friendly": str(i[1]) or str(i[0])})
    return sorted(result, key=lambda s: (s["component"] != "kwin", s["friendly"].lower()))


def recent_windows():
    r = subprocess.run(["qdbus6", "org.mxmaster4.ActionsRing", "/",
                        "org.mxmaster4.ActionsRing.recentWindows"], capture_output=True, text=True)
    try:
        return json.loads(r.stdout)
    except ValueError:
        return []


def cmd_ring(args):
    sub = args[0]
    if sub == "get":
        cfg = None
        for path in (RING_CONFIG, RING_DEFAULT):
            try:
                cfg = json.load(open(path))
                break
            except (OSError, ValueError):
                continue
        out({"config": cfg or {"items": [], "apps": []}, "apps": desktop_apps(),
             "shortcuts": kde_shortcuts(), "windows": recent_windows(),
             "waveforms": RING_WAVEFORMS, "active": unit_active(SERVICES["ring"])})
        return 0
    if sub == "set":
        from urllib.parse import unquote
        cfg = json.loads(unquote(args[1]))
        if not isinstance(cfg, dict) or not isinstance(cfg.get("items", []), list):
            raise ValueError("ожидался объект с items")
        os.makedirs(os.path.dirname(RING_CONFIG), exist_ok=True)
        tmp = RING_CONFIG + ".tmp"
        json.dump(cfg, open(tmp, "w"), ensure_ascii=False, indent=2)
        os.replace(tmp, RING_CONFIG)
        out({"ok": True})
        return 0
    if sub == "show":
        r = subprocess.run([os.path.join(HERE, "actions-ring", "actions_ring.py"), "show"])
        out({"ok": r.returncode == 0, "error": "" if r.returncode == 0 else "служба кольца не запущена"})
        return r.returncode
    raise ValueError(sub)


COMMANDS = {"status": cmd_status, "set": cmd_set, "buzz": cmd_buzz,
            "service": cmd_service, "bindings": cmd_bindings, "ring": cmd_ring, "wheel": cmd_wheel}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print(__doc__, file=sys.stderr)
        return 2
    try:
        return COMMANDS[sys.argv[1]](sys.argv[2:])
    except (IndexError, KeyError, ValueError) as e:
        out({"ok": False, "error": f"неверные аргументы: {e}"})
        return 2


if __name__ == "__main__":
    sys.exit(main())
