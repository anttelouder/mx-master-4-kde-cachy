#!/bin/sh
# Вибро-отклик после переключения микрофона: выключен — глухой удар, включён — бодрый двойной.
# Вызывается xremap сразу после KEY_MICMUTE (KDE сам переключает микрофон и показывает OSD).
sleep 0.3
if wpctl get-volume @DEFAULT_AUDIO_SOURCE@ | grep -q MUTED; then
    exec "$HOME/.local/bin/mouse-buzz" DAMP_COLLISION
else
    exec "$HOME/.local/bin/mouse-buzz" HAPPY_ALERT
fi
