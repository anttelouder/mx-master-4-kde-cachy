#!/usr/bin/env bash
# mx-master-4-kde-cachy — removal. Leaves packages (logiops, xremap) and settings in ~/.config alone.
set -euo pipefail

BIN="$HOME/.local/bin"
UNITS="$HOME/.config/systemd/user"

systemctl --user disable --now actions-ring.service xremap.service 2>/dev/null || true
rm -f "$UNITS/actions-ring.service" "$UNITS/xremap.service"
systemctl --user daemon-reload
rm -f "$BIN/mousectl" "$BIN/mouse-buzz" "$BIN/mic-buzz" "$BIN/actions-ring"
rm -f "$HOME/.local/share/plasma/plasmoids/org.mxmaster4.widget"

sudo rm -f /etc/udev/rules.d/70-mx-master-4.rules
sudo udevadm control --reload

latest_backup="$(ls -1t /etc/logid.cfg.bak-* 2>/dev/null | head -1 || true)"
if [[ -n "$latest_backup" ]]; then
    echo "Previous logid config: $latest_backup"
    echo "Restore it: sudo cp '$latest_backup' /etc/logid.cfg && sudo systemctl restart logid"
fi
echo "Removed. Settings are kept in ~/.config/xremap, ~/.config/actions-ring, ~/.config/mousectl."
