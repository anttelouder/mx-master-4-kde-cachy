#!/usr/bin/env bash
# mx-master-4-kde-cachy — per-user installation.
# Installs missing packages (with confirmation), symlinks the scripts and the widget,
# enables the user services, installs the udev rule and /etc/logid.cfg (the old one is backed up).
# Safe to run again. Uninstall — ./uninstall.sh
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
BIN="$HOME/.local/bin"
PLASMOIDS="$HOME/.local/share/plasma/plasmoids"
UNITS="$HOME/.config/systemd/user"
PLASMOID_ID="org.mxmaster4.widget"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

# --- packages ---
repo_pkgs=(python python-pyqt6 python-yaml python-dbus layer-shell-qt qt6-tools wireplumber)
aur_pkgs=(logiops-git xremap-kde-bin)
missing_repo=(); missing_aur=()
for p in "${repo_pkgs[@]}"; do pacman -Qq "$p" &>/dev/null || missing_repo+=("$p"); done
command -v logid  &>/dev/null || missing_aur+=(logiops-git)
command -v xremap &>/dev/null || missing_aur+=(xremap-kde-bin)
if (( ${#missing_repo[@]} + ${#missing_aur[@]} )); then
    say "Missing packages: ${missing_repo[*]} ${missing_aur[*]}"
    read -rp "Install? [Y/n] " ans
    [[ "${ans:-y}" =~ ^[Yy]$ ]] || { echo "It will not work without the packages, exiting."; exit 1; }
    if (( ${#missing_repo[@]} )); then
        sudo pacman -S --needed "${missing_repo[@]}"
    fi
    if (( ${#missing_aur[@]} )); then
        aur_helper="$(command -v paru || command -v yay || true)"
        [[ -n "$aur_helper" ]] || { echo "paru or yay is required for AUR: ${missing_aur[*]}"; exit 1; }
        "$aur_helper" -S --needed "${missing_aur[@]}"
    fi
fi

# --- scripts and widget ---
say "Symlinks in $BIN and the MX Master 4 widget"
mkdir -p "$BIN" "$PLASMOIDS" "$UNITS"
ln -sfn "$REPO/mousectl.py"               "$BIN/mousectl"
ln -sfn "$REPO/mouse-buzz.py"             "$BIN/mouse-buzz"
ln -sfn "$REPO/mic-buzz.sh"               "$BIN/mic-buzz"
ln -sfn "$REPO/actions-ring/actions_ring.py" "$BIN/actions-ring"
ln -sfn "$REPO/plasmoid" "$PLASMOIDS/$PLASMOID_ID"

# --- system part: udev and logid ---
say "udev rule and /etc/logid.cfg (sudo required)"
sudo install -m 644 "$REPO/udev/70-mx-master-4.rules" /etc/udev/rules.d/70-mx-master-4.rules
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=input --subsystem-match=hidraw --subsystem-match=misc
if [[ -f /etc/logid.cfg ]] && ! cmp -s /etc/logid.cfg "$REPO/config/logid.cfg"; then
    backup="/etc/logid.cfg.bak-$(date +%Y%m%d-%H%M%S)"
    sudo cp /etc/logid.cfg "$backup"
    echo "    old /etc/logid.cfg saved to $backup"
fi
sudo install -m 644 "$REPO/config/logid.cfg" /etc/logid.cfg
sudo systemctl enable logid.service
sudo systemctl restart logid.service

# --- user services and button layout ---
say "xremap and actions-ring services"
install -m 644 "$REPO/systemd/xremap.service" "$REPO/systemd/actions-ring.service" "$UNITS/"
systemctl --user daemon-reload
if [[ ! -f "$HOME/.config/xremap/config.yml" ]]; then
    "$BIN/mousectl" bindings reset >/dev/null || true   # default button layout
fi
systemctl --user enable --now xremap.service actions-ring.service
systemctl --user restart xremap.service

cat <<EOF

Done.
  1. Add the "MX Master 4" widget to the panel: right-click the panel → "Add Widgets…".
  2. If the buttons do not react — switch the mouse off and on with the switch on its underside
     (logiops with a Bolt receiver sometimes misses the mouse after a restart). Check:
     journalctl -u logid | grep "Device found"
  3. Buttons are set up in the "Buttons" tab, the ring — in the "Ring" tab.
EOF
