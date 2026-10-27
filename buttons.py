"""Бинды кнопок MX Master 4 для вкладки «Кнопки» виджета: модель «профиль приложения × кнопка».

logid (/etc/logid.cfg) раз и навсегда шлёт с каждой кнопки и каждого жеста свою «пустую»
клавишу (таблица BUTTONS, та же, что в комментарии logid.cfg). Смысл им задаёт xremap
(~/.config/xremap/config.yml), который пишет этот модуль:

- профили приложений — keymap с application.only, по порядку; кнопка, не заданная в профиле,
  берётся из «Всех приложений» (xremap идёт к следующему keymap);
- «Все приложения» — последний keymap без application; в нём заданы все кнопки, «ничего» = [].

Действие кнопки для виджета: preset (из CATALOG), keys (сочетание в синтаксисе xremap), app,
kde (глобальное действие kglobalaccel), nothing, default (только в профиле приложения), raw
(что-то, что модель не разбирает, — сохраняется как есть). Боковое колесо: scroll / tabs / raw.
"""
import json
import os
import re

HOME_BIN = os.path.expanduser("~/.local/bin")
KGA = ["qdbus6", "org.kde.kglobalaccel"]
DEFAULT_NAME = "Все приложения"

# кнопка → направления → «пустая» клавиша из logid.cfg
BUTTONS = [
    {"id": "gesture", "name": "Кнопка жестов", "hint": "под большим пальцем: нажать или зажать и повести",
     "slots": [("click", "Нажатие", "F13"), ("up", "Вверх", "F14"), ("down", "Вниз", "F15"),
               ("left", "Влево", "F16"), ("right", "Вправо", "F17")]},
    {"id": "back", "name": "Назад", "hint": "нажать или зажать и повести; вверх/вниз повторяются по ходу движения",
     "slots": [("click", "Нажатие", "F23"), ("up", "Вверх (повтор)", "F24"), ("down", "Вниз (повтор)", "KEY_FN_F1"),
               ("left", "Влево", "KEY_FN_F2"), ("right", "Вправо", "KEY_FN_F3")]},
    {"id": "forward", "name": "Вперёд", "hint": "нажать или зажать и повести",
     "slots": [("click", "Нажатие", "F19"), ("up", "Вверх", "F18"), ("down", "Вниз", "F20"),
               ("left", "Влево", "F21"), ("right", "Вправо", "F22")]},
    {"id": "haptic", "name": "Haptic-панель", "hint": "нажатие на панель под большим пальцем",
     "slots": [("click", "Нажатие", "KEY_FN_F4")]},
    {"id": "wheelbtn", "name": "Кнопка за колесом", "hint": "",
     "slots": [("click", "Нажатие", "KEY_FN_F5")]},
    {"id": "sidewheel", "name": "Боковое колесо", "hint": "под большим пальцем",
     "slots": [("wheel", "Прокрутка", "WHEEL")]},
]
KEYS = [s[2] for b in BUTTONS for s in b["slots"]]
SLOT_LABEL = {s[2]: f"{b['name']}: {s[1].lower()}" if len(b["slots"]) > 1 else b["name"]
              for b in BUTTONS for s in b["slots"]}
OLD_KEYS = {"Super-Shift-s": "KEY_FN_F4"}   # в ранних версиях haptic-панель слала Meta+Shift+S


def kde(component, name):
    return {"launch": KGA + ["/component/" + component, "org.kde.kglobalaccel.Component.invokeShortcut", name]}


def launch(*argv):
    return {"launch": list(argv)}


# Каталог готовых действий: (id, раздел, название, иконка, значение xremap[, псевдонимы])
CATALOG = [
    ("back", "Навигация", "Назад", "go-previous", "BTN_SIDE"),
    ("forward", "Навигация", "Вперёд", "go-next", "BTN_EXTRA"),
    ("tab_new", "Вкладки", "Новая вкладка", "tab-new", "C-t"),
    ("tab_close", "Вкладки", "Закрыть вкладку", "tab-close", "C-w"),
    ("tab_reopen", "Вкладки", "Вернуть закрытую вкладку", "edit-undo", "C-Shift-t"),
    ("tab_next", "Вкладки", "Следующая вкладка", "go-next-view", "C-tab", ["C-pagedown"]),
    ("tab_prev", "Вкладки", "Предыдущая вкладка", "go-previous-view", "C-Shift-tab", ["C-pageup"]),
    ("overview", "Окна", "Обзор окон", "view-grid", kde("kwin", "Overview"), ["Super-w"]),
    ("maximize", "Окна", "Распахнуть окно", "window-maximize", kde("kwin", "Window Maximize"), ["Super-pageup"]),
    ("minimize", "Окна", "Свернуть окно", "window-minimize", kde("kwin", "Window Minimize"), ["Super-pagedown"]),
    ("tile_left", "Окна", "Окно на левую половину", "view-split-left-right", kde("kwin", "Window Quick Tile Left"), ["Super-left"]),
    ("tile_right", "Окна", "Окно на правую половину", "view-split-left-right", kde("kwin", "Window Quick Tile Right"), ["Super-right"]),
    ("close_window", "Окна", "Закрыть окно", "window-close", kde("kwin", "Window Close")),
    ("show_desktop", "Окна", "Показать рабочий стол", "user-desktop", kde("kwin", "Show Desktop")),
    ("desk_next", "Окна", "Следующий рабочий стол", "go-next", kde("kwin", "Switch One Desktop to the Right")),
    ("desk_prev", "Окна", "Предыдущий рабочий стол", "go-previous", kde("kwin", "Switch One Desktop to the Left")),
    ("vol_up", "Звук и музыка", "Громче", "audio-volume-high", "KEY_VOLUMEUP"),
    ("vol_down", "Звук и музыка", "Тише", "audio-volume-low", "KEY_VOLUMEDOWN"),
    ("mute", "Звук и музыка", "Выключить звук", "audio-volume-muted", "KEY_MUTE"),
    ("play", "Звук и музыка", "Пауза / играть", "media-playback-start", "KEY_PLAYPAUSE"),
    ("next_track", "Звук и музыка", "Следующий трек", "media-skip-forward", "KEY_NEXTSONG"),
    ("prev_track", "Звук и музыка", "Предыдущий трек", "media-skip-backward", "KEY_PREVIOUSSONG"),
    ("mic", "Звук и музыка", "Микрофон вкл/выкл (с вибрацией)", "microphone-sensitivity-muted",
     ["KEY_MICMUTE", launch(os.path.join(HOME_BIN, "mic-buzz"))]),
    ("copy", "Правка", "Копировать", "edit-copy", "C-c"),
    ("paste", "Правка", "Вставить", "edit-paste", "C-v"),
    ("cut", "Правка", "Вырезать", "edit-cut", "C-x"),
    ("undo", "Правка", "Отменить", "edit-undo", "C-z"),
    ("redo", "Правка", "Повторить", "edit-redo", "C-Shift-z"),
    ("save", "Правка", "Сохранить", "document-save", "C-s"),
    ("find", "Правка", "Найти", "edit-find", "C-f"),
    ("ring", "Система", "Кольцо действий", "view-app-grid", launch(os.path.join(HOME_BIN, "actions-ring"), "show")),
    ("screenshot", "Система", "Скриншот области", "spectacle", launch("spectacle", "--region")),
    ("smartshift", "Система", "Колесо: щелчки ↔ свободное", "input-mouse",
     launch(os.path.join(HOME_BIN, "mousectl"), "wheel", "toggle")),
    ("krunner", "Система", "Поиск KRunner", "search", kde("org_kde_krunner_desktop", "_launch")),
    ("lock", "Система", "Заблокировать экран", "system-lock-screen", kde("ksmserver", "Lock Session")),
]
CAT_BY_ID = {c[0]: c for c in CATALOG}

# «Все приложения» по умолчанию — и для «Сбросить», и чтобы дозаполнить старый конфиг
DEFAULTS = {
    "F13": "overview", "F14": "maximize", "F15": "minimize", "F16": "tile_left", "F17": "tile_right",
    "F23": "back", "F24": "vol_up", "KEY_FN_F1": "vol_down", "KEY_FN_F2": None, "KEY_FN_F3": None,
    "F19": "forward", "F18": "mic", "F20": "play", "F21": "prev_track", "F22": "next_track",
    "KEY_FN_F4": "ring", "KEY_FN_F5": "smartshift",
}


def match_catalog(v):
    for c in CATALOG:
        if v == c[4] or (len(c) > 5 and v in c[5]):
            return c[0]
    return None


def describe(v):
    """Короткое описание значения xremap — для комментария в конфиге."""
    if v is None:
        return "как во «Всех приложениях»"
    if v == []:
        return "ничего"
    if (cid := match_catalog(v)):
        return CAT_BY_ID[cid][2]
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and "launch" in v:
        argv = v["launch"]
        if argv[:2] == ["kstart", "--application"]:
            return "запуск " + argv[-1]
        if argv[:2] == KGA:
            return "KDE: " + argv[-1]
        return "запуск " + os.path.basename(argv[0])
    if isinstance(v, list) and v and isinstance(v[0], str) and len(v) == 2:
        return "серия"
    return "своё"


def wheel_tabs(prev, nxt):
    """Боковое колесо: 1 переключение на 4 щелчка (3 вложенных remap глотают следующие щелчки)."""
    def side(key, combo):
        inner = {"remap": {key: []}, "timeout_millis": 400}
        mid = {"remap": {key: inner}, "timeout_millis": 400}
        return [combo, {"remap": {key: mid}, "timeout_millis": 400}]
    return side("XLEFTSCROLL", prev), side("XRIGHTSCROLL", nxt)


def to_ui(key, remap, is_default):
    if key == "WHEEL":
        left, right = remap.get("XLEFTSCROLL"), remap.get("XRIGHTSCROLL")
        if left is None and right is None:
            return {"kind": "default" if not is_default else "scroll"}
        if (isinstance(left, list) and len(left) == 2 and isinstance(left[0], str)
                and isinstance(right, list) and len(right) == 2 and isinstance(right[0], str)):
            return {"kind": "tabs", "prev": left[0], "next": right[0]}
        if left == [] and right == []:
            return {"kind": "scroll"}
        return {"kind": "raw", "raw": {k: remap[k] for k in remap if "SCROLL" in k}, "label": "своё"}
    if key not in remap:
        return {"kind": "nothing" if is_default else "default"}
    v = remap[key]
    if v == []:
        return {"kind": "nothing"}
    if (cid := match_catalog(v)):
        return {"kind": "preset", "id": cid}
    if isinstance(v, str):
        return {"kind": "keys", "keys": v}
    if isinstance(v, dict) and list(v) == ["launch"]:
        argv = v["launch"]
        if argv[:2] == ["kstart", "--application"] and len(argv) == 3:
            return {"kind": "app", "app": argv[2]}
        if argv[:2] == KGA and len(argv) == 5:
            return {"kind": "kde", "component": argv[2].rsplit("/", 1)[-1], "name": argv[4]}
    return {"kind": "raw", "raw": v, "label": describe(v)}


def from_ui(key, a, remap, is_default):
    kind = a.get("kind", "default")
    if key == "WHEEL":
        for k in ("XLEFTSCROLL", "XRIGHTSCROLL", "XHIRES_LEFTSCROLL", "XHIRES_RIGHTSCROLL"):
            remap.pop(k, None)
        if kind == "tabs":
            remap["XLEFTSCROLL"], remap["XRIGHTSCROLL"] = wheel_tabs(a.get("prev") or "C-Shift-tab",
                                                                     a.get("next") or "C-tab")
            remap["XHIRES_LEFTSCROLL"] = []    # плавная прокрутка не должна просачиваться
            remap["XHIRES_RIGHTSCROLL"] = []
        elif kind == "raw":
            remap.update(a["raw"])
        return
    remap.pop(key, None)
    v = None
    if kind == "preset" and a.get("id") in CAT_BY_ID:
        v = CAT_BY_ID[a["id"]][4]
    elif kind == "keys" and a.get("keys", "").strip():
        v = a["keys"].strip()
    elif kind == "app" and a.get("app"):
        v = {"launch": ["kstart", "--application", a["app"]]}
    elif kind == "kde" and a.get("name"):
        v = kde(a["component"], a["name"])
    elif kind == "raw":
        v = a["raw"]
    elif kind == "nothing" or is_default:
        v = []
    if v is not None:
        remap[key] = v


def app_regexes(app_id, wmclass=""):
    """Окна приложения: по id .desktop (без хвоста-хеша) и StartupWMClass, без учёта регистра."""
    names = []
    for n in (re.sub(r"\._[0-9a-f]{16,}$", "", app_id), wmclass):
        if n and n.lower() not in [x.lower() for x in names]:
            names.append(n)
    return ["/(?i)^" + re.escape(n) + "/" for n in names]


def profile_icon(apps, desktop):
    for rx in apps:
        pat = rx[1:-1] if rx.startswith("/") and rx.endswith("/") else "^" + re.escape(rx) + "$"
        try:
            r = re.compile(pat)
        except re.error:
            continue
        hits = [d for d in desktop if r.search(d["id"]) or (d.get("wmclass") and r.search(d["wmclass"]))]
        if hits:                        # самый короткий id — сама программа, а не её веб-ярлыки
            return min(hits, key=lambda d: len(d["id"]))["icon"]
    return "application-x-executable"


def load_profiles(cfg, desktop):
    """config.yml → профили. Старый формат (несколько групп без application, Super-Shift-s)
    сводится в «Все приложения»; недостающие кнопки там дозаполняются из DEFAULTS."""
    apps, default_remap = [], {}
    for km in cfg.get("keymap", []):
        remap = {OLD_KEYS.get(k, k): v for k, v in (km.get("remap") or {}).items()}
        only = (km.get("application") or {}).get("only") or []
        if only:
            apps.append({"name": km.get("name", ""), "apps": only, "remap": remap})
        else:
            for k, v in remap.items():       # раньше заданное выигрывает, как в xremap
                default_remap.setdefault(k, v)
    for k, cid in DEFAULTS.items():
        if k not in default_remap:
            default_remap[k] = CAT_BY_ID[cid][4] if cid else []
    profiles = []
    for p in apps + [{"name": DEFAULT_NAME, "apps": [], "remap": default_remap}]:
        is_default = not p["apps"]
        profiles.append({
            "name": p["name"], "apps": p["apps"], "default": is_default,
            "icon": "preferences-desktop" if is_default else profile_icon(p["apps"], desktop),
            "keys": {k: to_ui(k, p["remap"], is_default) for k in KEYS},
            "extra": {k: v for k, v in p["remap"].items() if k not in KEYS and "SCROLL" not in k},
        })
    return profiles


def build_keymap(profiles, desktop):
    by_id = {d["id"]: d for d in desktop}
    keymap = []
    ordered = [p for p in profiles if not p.get("default")] + [p for p in profiles if p.get("default")][:1]
    for p in ordered:
        is_default = bool(p.get("default"))
        apps = [a for a in p.get("apps") or [] if a.strip()]
        if not is_default and not apps and p.get("app"):
            d = by_id.get(p["app"], {})
            apps = app_regexes(p["app"], d.get("wmclass", ""))
        if not is_default and not apps:
            continue                    # профиль без окон стал бы общим для всех окон
        remap = dict(p.get("extra") or {})
        for k in KEYS:
            from_ui(k, (p.get("keys") or {}).get(k) or {"kind": "default"}, remap, is_default)
        km = {"name": p.get("name") or "Без названия"}
        if not is_default:
            km["application"] = {"only": apps}
        km["remap"] = remap
        keymap.append(km)
    return keymap


def yq(s):
    """Скаляр YAML: простые строки как есть, остальное — в двойных кавычках (JSON совместим с YAML)."""
    return s if re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]*", s) and s.lower() not in (
        "yes", "no", "on", "off", "true", "false", "null") else json.dumps(s, ensure_ascii=False)


def dump_config(keymap):
    import yaml
    from datetime import date
    label = dict(SLOT_LABEL, XLEFTSCROLL="Боковое колесо ←", XRIGHTSCROLL="Боковое колесо →")
    lines = [
        f"# Кнопки MX Master 4 по приложениям — пишет вкладка «Кнопки» виджета (mousectl bindings set), {date.today()}.",
        "# logid (/etc/logid.cfg) шлёт с каждой кнопки и жеста свою «пустую» клавишу (F13–F24, KEY_FN_F1–F5),",
        "# здесь им задаётся смысл. Профили приложений идут первыми; чего в профиле нет — берётся из",
        "# последнего блока «Все приложения». Руками править можно, виджет файл читает.",
        "keymap:",
    ]
    for g in keymap:
        lines.append(f"  - name: {yq(g.get('name', ''))}")
        only = (g.get("application") or {}).get("only")
        if only:
            lines += ["    application:", "      only:"] + [f"        - {json.dumps(r, ensure_ascii=False)}" for r in only]
        lines.append("    remap:")
        for k, v in (g.get("remap") or {}).items():
            note = f"  # {label[k]} — {describe(v)}" if k in label else ""
            if isinstance(v, str):
                lines.append(f"      {yq(k)}: {yq(v)}{note}")
            elif v == []:
                lines.append(f"      {yq(k)}: []{note}")
            else:
                lines.append(f"      {yq(k)}:{note}")
                body = yaml.safe_dump(v, allow_unicode=True, default_flow_style=None, sort_keys=False)
                lines += ["        " + ln for ln in body.rstrip("\n").splitlines()]
        lines.append("")
    return "\n".join(lines)


def ui_meta():
    return {
        "buttons": [{"id": b["id"], "name": b["name"], "hint": b["hint"],
                     "slots": [{"dir": d, "label": l, "key": k} for d, l, k in b["slots"]]} for b in BUTTONS],
        "catalog": [{"id": c[0], "cat": c[1], "name": c[2], "icon": c[3]} for c in CATALOG],
    }
