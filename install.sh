#!/usr/bin/env bash
# mx-master-4-kde-cachy — установка для текущего пользователя.
# Ставит недостающие пакеты (с подтверждением), делает ссылки на скрипты и виджет,
# включает службы пользователя, кладёт правило udev и /etc/logid.cfg (старый — в резервную копию).
# Запускать повторно безопасно. Удаление — ./uninstall.sh
set -euo pipefail

REPO="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
BIN="$HOME/.local/bin"
PLASMOIDS="$HOME/.local/share/plasma/plasmoids"
UNITS="$HOME/.config/systemd/user"
PLASMOID_ID="org.mxmaster4.widget"

say() { printf '\033[1m==> %s\033[0m\n' "$*"; }

# --- пакеты ---
repo_pkgs=(python python-pyqt6 python-yaml python-dbus layer-shell-qt qt6-tools wireplumber)
aur_pkgs=(logiops-git xremap-kde-bin)
missing_repo=(); missing_aur=()
for p in "${repo_pkgs[@]}"; do pacman -Qq "$p" &>/dev/null || missing_repo+=("$p"); done
command -v logid  &>/dev/null || missing_aur+=(logiops-git)
command -v xremap &>/dev/null || missing_aur+=(xremap-kde-bin)
if (( ${#missing_repo[@]} + ${#missing_aur[@]} )); then
    say "Не хватает пакетов: ${missing_repo[*]} ${missing_aur[*]}"
    read -rp "Установить? [Y/n] " ans
    [[ "${ans:-y}" =~ ^[YyДд]$ ]] || { echo "Без пакетов не заработает, выхожу."; exit 1; }
    if (( ${#missing_repo[@]} )); then
        sudo pacman -S --needed "${missing_repo[@]}"
    fi
    if (( ${#missing_aur[@]} )); then
        aur_helper="$(command -v paru || command -v yay || true)"
        [[ -n "$aur_helper" ]] || { echo "Нужен paru или yay для AUR: ${missing_aur[*]}"; exit 1; }
        "$aur_helper" -S --needed "${missing_aur[@]}"
    fi
fi

# --- скрипты и виджет ---
say "Ссылки в $BIN и виджет «MX Master 4»"
mkdir -p "$BIN" "$PLASMOIDS" "$UNITS"
ln -sfn "$REPO/mousectl.py"               "$BIN/mousectl"
ln -sfn "$REPO/mouse-buzz.py"             "$BIN/mouse-buzz"
ln -sfn "$REPO/mic-buzz.sh"               "$BIN/mic-buzz"
ln -sfn "$REPO/actions-ring/actions_ring.py" "$BIN/actions-ring"
ln -sfn "$REPO/plasmoid" "$PLASMOIDS/$PLASMOID_ID"

# --- системная часть: udev и logid ---
say "Правило udev и /etc/logid.cfg (нужен sudo)"
sudo install -m 644 "$REPO/udev/70-mx-master-4.rules" /etc/udev/rules.d/70-mx-master-4.rules
sudo udevadm control --reload
sudo udevadm trigger --subsystem-match=input --subsystem-match=hidraw --subsystem-match=misc
if [[ -f /etc/logid.cfg ]] && ! cmp -s /etc/logid.cfg "$REPO/config/logid.cfg"; then
    backup="/etc/logid.cfg.bak-$(date +%Y%m%d-%H%M%S)"
    sudo cp /etc/logid.cfg "$backup"
    echo "    старый /etc/logid.cfg сохранён в $backup"
fi
sudo install -m 644 "$REPO/config/logid.cfg" /etc/logid.cfg
sudo systemctl enable logid.service
sudo systemctl restart logid.service

# --- службы пользователя и раскладка кнопок ---
say "Службы xremap и кольца действий"
install -m 644 "$REPO/systemd/xremap.service" "$REPO/systemd/actions-ring.service" "$UNITS/"
systemctl --user daemon-reload
if [[ ! -f "$HOME/.config/xremap/config.yml" ]]; then
    "$BIN/mousectl" bindings reset >/dev/null || true   # стандартная раскладка кнопок
fi
systemctl --user enable --now xremap.service actions-ring.service
systemctl --user restart xremap.service

cat <<EOF

Готово.
  1. Добавь виджет «MX Master 4» на панель: правый клик по панели → «Добавить виджеты…».
  2. Если кнопки не реагируют — выключи и включи мышь переключателем снизу
     (logiops с приёмником Bolt иногда не видит мышь после перезапуска). Проверка:
     journalctl -u logid | grep "Device found"
  3. Кнопки настраиваются во вкладке «Кнопки», кольцо — во вкладке «Кольцо».
EOF
