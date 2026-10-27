"""MX Master 4 button bindings for the widget's "Buttons" tab: the "app profile × button" model.

logid (/etc/logid.cfg) permanently sends a dedicated "blank" key from every button and gesture
(the BUTTONS table, the same one as in the logid.cfg comment). Their meaning is assigned by xremap
(~/.config/xremap/config.yml), which this module writes:

- app profiles — keymaps with application.only, in order; a button not set in a profile
  falls back to "All applications" (xremap moves on to the next keymap);
- "All applications" — the last keymap without application; it sets every button, "nothing" = [].

A button action for the widget: preset (from CATALOG), keys (a combo in xremap syntax), app,
kde (a kglobalaccel global action), nothing, default (only in an app profile), raw
(something the model does not parse — stored as is). Thumb wheel: scroll / tabs / raw.
"""
import json
import os
import re

HOME_BIN = os.path.expanduser("~/.local/bin")
KGA = ["qdbus6", "org.kde.kglobalaccel"]
DEFAULT_NAME = "All applications"

# button → directions → "blank" key from logid.cfg
BUTTONS = [
    {"id": "gesture", "name": "Gesture button", "hint": "under the thumb: click, or hold and move",
     "slots": [("click", "Click", "F13"), ("up", "Up", "F14"), ("down", "Down", "F15"),
               ("left", "Left", "F16"), ("right", "Right", "F17")]},
    {"id": "back", "name": "Back", "hint": "click, or hold and move; up/down repeat while you keep moving",
     "slots": [("click", "Click", "F23"), ("up", "Up (repeat)", "F24"), ("down", "Down (repeat)", "KEY_FN_F1"),
               ("left", "Left", "KEY_FN_F2"), ("right", "Right", "KEY_FN_F3")]},
    {"id": "forward", "name": "Forward", "hint": "click, or hold and move",
     "slots": [("click", "Click", "F19"), ("up", "Up", "F18"), ("down", "Down", "F20"),
               ("left", "Left", "F21"), ("right", "Right", "F22")]},
    {"id": "haptic", "name": "Haptic panel", "hint": "press the panel under your thumb",
     "slots": [("click", "Click", "KEY_FN_F4")]},
    {"id": "wheelbtn", "name": "Button behind the wheel", "hint": "",
     "slots": [("click", "Click", "KEY_FN_F5")]},
    {"id": "sidewheel", "name": "Thumb wheel", "hint": "under the thumb",
     "slots": [("wheel", "Scroll", "WHEEL")]},
]
KEYS = [s[2] for b in BUTTONS for s in b["slots"]]
SLOT_LABEL = {s[2]: f"{b['name']}: {s[1].lower()}" if len(b["slots"]) > 1 else b["name"]
              for b in BUTTONS for s in b["slots"]}
OLD_KEYS = {"Super-Shift-s": "KEY_FN_F4"}   # in early versions the haptic panel sent Meta+Shift+S


def kde(component, name):
    return {"launch": KGA + ["/component/" + component, "org.kde.kglobalaccel.Component.invokeShortcut", name]}


def launch(*argv):
    return {"launch": list(argv)}


# Catalogue of ready-made actions: (id, section, name, icon, xremap value[, aliases])
CATALOG = [
    ("back", "Navigation", "Back", "go-previous", "BTN_SIDE"),
    ("forward", "Navigation", "Forward", "go-next", "BTN_EXTRA"),
    ("tab_new", "Tabs", "New tab", "tab-new", "C-t"),
    ("tab_close", "Tabs", "Close tab", "tab-close", "C-w"),
    ("tab_reopen", "Tabs", "Reopen closed tab", "edit-undo", "C-Shift-t"),
    ("tab_next", "Tabs", "Next tab", "go-next-view", "C-tab", ["C-pagedown"]),
    ("tab_prev", "Tabs", "Previous tab", "go-previous-view", "C-Shift-tab", ["C-pageup"]),
    ("overview", "Windows", "Window overview", "view-grid", kde("kwin", "Overview"), ["Super-w"]),
    ("maximize", "Windows", "Maximize window", "window-maximize", kde("kwin", "Window Maximize"), ["Super-pageup"]),
    ("minimize", "Windows", "Minimize window", "window-minimize", kde("kwin", "Window Minimize"), ["Super-pagedown"]),
    ("tile_left", "Windows", "Tile window left", "view-split-left-right", kde("kwin", "Window Quick Tile Left"), ["Super-left"]),
    ("tile_right", "Windows", "Tile window right", "view-split-left-right", kde("kwin", "Window Quick Tile Right"), ["Super-right"]),
    ("close_window", "Windows", "Close window", "window-close", kde("kwin", "Window Close")),
    ("show_desktop", "Windows", "Show desktop", "user-desktop", kde("kwin", "Show Desktop")),
    ("desk_next", "Windows", "Next desktop", "go-next", kde("kwin", "Switch One Desktop to the Right")),
    ("desk_prev", "Windows", "Previous desktop", "go-previous", kde("kwin", "Switch One Desktop to the Left")),
    ("vol_up", "Sound & music", "Volume up", "audio-volume-high", "KEY_VOLUMEUP"),
    ("vol_down", "Sound & music", "Volume down", "audio-volume-low", "KEY_VOLUMEDOWN"),
    ("mute", "Sound & music", "Mute", "audio-volume-muted", "KEY_MUTE"),
    ("play", "Sound & music", "Play / pause", "media-playback-start", "KEY_PLAYPAUSE"),
    ("next_track", "Sound & music", "Next track", "media-skip-forward", "KEY_NEXTSONG"),
    ("prev_track", "Sound & music", "Previous track", "media-skip-backward", "KEY_PREVIOUSSONG"),
    ("mic", "Sound & music", "Toggle microphone (with haptics)", "microphone-sensitivity-muted",
     ["KEY_MICMUTE", launch(os.path.join(HOME_BIN, "mic-buzz"))]),
    ("copy", "Editing", "Copy", "edit-copy", "C-c"),
    ("paste", "Editing", "Paste", "edit-paste", "C-v"),
    ("cut", "Editing", "Cut", "edit-cut", "C-x"),
    ("undo", "Editing", "Undo", "edit-undo", "C-z"),
    ("redo", "Editing", "Redo", "edit-redo", "C-Shift-z"),
    ("save", "Editing", "Save", "document-save", "C-s"),
    ("find", "Editing", "Find", "edit-find", "C-f"),
    ("ring", "System", "Actions Ring", "view-app-grid", launch(os.path.join(HOME_BIN, "actions-ring"), "show")),
    ("screenshot", "System", "Area screenshot", "spectacle", launch("spectacle", "--region")),
    ("smartshift", "System", "Wheel: ratchet ↔ free spin", "input-mouse",
     launch(os.path.join(HOME_BIN, "mousectl"), "wheel", "toggle")),
    ("krunner", "System", "KRunner search", "search", kde("org_kde_krunner_desktop", "_launch")),
    ("lock", "System", "Lock screen", "system-lock-screen", kde("ksmserver", "Lock Session")),
]
CAT_BY_ID = {c[0]: c for c in CATALOG}

# "All applications" defaults — used by "Reset" and to fill in an old config
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
    """Short description of an xremap value — for the comment in the config."""
    if v is None:
        return "same as in All applications"
    if v == []:
        return "nothing"
    if (cid := match_catalog(v)):
        return CAT_BY_ID[cid][2]
    if isinstance(v, str):
        return v
    if isinstance(v, dict) and "launch" in v:
        argv = v["launch"]
        if argv[:2] == ["kstart", "--application"]:
            return "launch " + argv[-1]
        if argv[:2] == KGA:
            return "KDE: " + argv[-1]
        return "launch " + os.path.basename(argv[0])
    if isinstance(v, list) and v and isinstance(v[0], str) and len(v) == 2:
        return "sequence"
    return "custom"


def wheel_tabs(prev, nxt):
    """Thumb wheel: one switch per 4 clicks (3 nested remaps swallow the following clicks)."""
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
        return {"kind": "raw", "raw": {k: remap[k] for k in remap if "SCROLL" in k}, "label": "custom"}
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
            remap["XHIRES_LEFTSCROLL"] = []    # smooth scrolling must not leak through
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
    """App windows: by .desktop id (without the hash suffix) and StartupWMClass, case-insensitive."""
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
        if hits:                        # the shortest id is the program itself, not its web shortcuts
            return min(hits, key=lambda d: len(d["id"]))["icon"]
    return "application-x-executable"


def load_profiles(cfg, desktop):
    """config.yml → profiles. The old format (several groups without application, Super-Shift-s)
    collapses into "All applications"; missing buttons there are filled in from DEFAULTS."""
    apps, default_remap = [], {}
    for km in cfg.get("keymap", []):
        remap = {OLD_KEYS.get(k, k): v for k, v in (km.get("remap") or {}).items()}
        only = (km.get("application") or {}).get("only") or []
        if only:
            apps.append({"name": km.get("name", ""), "apps": only, "remap": remap})
        else:
            for k, v in remap.items():       # earlier settings win, as in xremap
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
            continue                    # a profile without windows would apply to every window
        remap = dict(p.get("extra") or {})
        for k in KEYS:
            from_ui(k, (p.get("keys") or {}).get(k) or {"kind": "default"}, remap, is_default)
        km = {"name": p.get("name") or "Untitled"}
        if not is_default:
            km["application"] = {"only": apps}
        km["remap"] = remap
        keymap.append(km)
    return keymap


def yq(s):
    """YAML scalar: plain strings as is, everything else in double quotes (JSON is valid YAML)."""
    return s if re.fullmatch(r"[A-Za-z][A-Za-z0-9_\-]*", s) and s.lower() not in (
        "yes", "no", "on", "off", "true", "false", "null") else json.dumps(s, ensure_ascii=False)


def dump_config(keymap):
    import yaml
    from datetime import date
    label = dict(SLOT_LABEL, XLEFTSCROLL="Thumb wheel ←", XRIGHTSCROLL="Thumb wheel →")
    lines = [
        f'# MX Master 4 per-app buttons — written by the "Buttons" tab of the widget (mousectl bindings set), {date.today()}.',
        "# logid (/etc/logid.cfg) sends its own spare key from every button and gesture (F13–F24, KEY_FN_F1–F5),",
        "# this file gives them meaning. App profiles come first; whatever a profile lacks is taken from",
        "# the last All applications block. You can edit it by hand, the widget reads the file.",
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
