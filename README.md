# MX Master 4 for KDE Plasma (CachyOS / Arch)

[Русская версия](README.ru.md)

Logitech's Options+ doesn't exist on Linux. This project brings the most useful parts of it to
KDE Plasma 6 on Wayland for the **Logitech MX Master 4**:

- **Per-app buttons, set up with the mouse.** A Plasma widget shows every button and gesture
  (the gesture button, Back and Forward each with click + 4 directions, the haptic panel, the button
  behind the wheel, the thumb wheel). Click a tile, pick an action from a searchable catalogue
  (tabs, windows, media, editing, launch an app, a key combo, any KDE global action). Add a
  profile for any installed app in one click. Changes apply instantly — no config files, no sudo.
- **Actions Ring.** Press the haptic panel and a ring of 8 app launchers pops up around the
  cursor. Moving over a slot gives a short haptic tick in your thumb. Slots can be folders.
  Arranged in the widget.
- **Mouse settings.** Battery, DPI, haptic strength, SmartShift threshold and ratchet force,
  free-spin toggle — read and written straight over HID++.
- **Haptic notifications** you can call from anywhere: `mouse-buzz COMPLETED` (16 built-in
  waveforms). Examples for Claude Code hooks and fish are in `extras/`. Muting the mic from the
  mouse answers with a distinct buzz for muted/unmuted.

The UI is in Russian for now; translations are welcome.

## Requirements

- CachyOS or another Arch-based distro, KDE Plasma 6 on **Wayland**
  (tested: CachyOS, Plasma 6.7.5, xremap 0.15.15, logiops-git 0.3.5)
- Logitech MX Master 4 connected through a **Logi Bolt (or Unifying) receiver**.
  Over Bluetooth the buttons work, but battery/DPI/haptics in the widget don't (HID++ goes through the receiver).
- Packages (the installer offers to install missing ones): `logiops-git`, `xremap-kde-bin` (AUR),
  `python-pyqt6`, `python-yaml`, `python-dbus`, `layer-shell-qt`, `qt6-tools`, `wireplumber`

## Install

```sh
git clone https://github.com/anttelouder/mx-master-4-kde-cachy.git ~/git/mx-master-4-kde-cachy
cd ~/git/mx-master-4-kde-cachy
./install.sh
```

Then right-click the panel → *Add Widgets…* → **MX Master 4**.
If the buttons don't react, switch the mouse off and on (logiops with a Bolt receiver sometimes
misses an already-connected mouse after a restart).

The repository stays the single source: `~/.local/bin/*` and the widget are symlinks into it,
so `git pull` updates everything (restart the ring with `systemctl --user restart actions-ring`).

Uninstall: `./uninstall.sh` (keeps your settings in `~/.config`).

## How it works

```
mouse ─┬─► logiops (logid, /etc/logid.cfg — fixed)
       │     every button and gesture → its own spare key (F13–F24, KEY_FN_F1–F5) ─► "LogiOps Virtual Input"
       └─ the mouse itself (motion, wheels) ──────────────────────────────────────────────┤
                                                                                          ▼
                xremap (user service, ~/.config/xremap/config.yml — written by the widget)
                      → action for the active app's profile, or "All apps"
```

| Part | What it does |
|---|---|
| `config/logid.cfg` | Maps each button/gesture to a spare key. Never needs editing again. |
| `buttons.py` | The model: buttons → keys, the action catalogue, default layout, reading/writing xremap's config. |
| `mousectl.py` | Backend for the widget: status, settings over HID++, bindings, ring config. JSON on stdout. |
| `hidpp.py` | Minimal HID++ 2.0 client (battery, DPI, SmartShift, haptics). Cross-process lock — several tools share the receiver. |
| `actions-ring/` | The ring: a PyQt6/QML layer-shell overlay, a KWin script reports the active window over D-Bus. |
| `plasmoid/` | The Plasma widget. |
| `mouse-buzz.py`, `mic-buzz.sh` | Haptic waveform from the command line; feedback after toggling the mic. |

Limitations: gestures fire on button release, so holding a side button (push-to-talk) isn't
possible yet; key combos with Meta are grabbed by KWin before the widget's "Record" — type them
instead (`Super-w`).

## Credits

[logiops](https://github.com/PixlOne/logiops), [xremap](https://github.com/xremap/xremap),
and [Solaar](https://github.com/pwr-Solaar/Solaar) as the HID++ protocol reference.

## License

MIT
