#!/bin/sh
# Haptic feedback after toggling the microphone: muted — a dull thud, unmuted — a lively double.
# Called by xremap right after KEY_MICMUTE (KDE toggles the microphone itself and shows an OSD).
sleep 0.3
if wpctl get-volume @DEFAULT_AUDIO_SOURCE@ | grep -q MUTED; then
    exec "$HOME/.local/bin/mouse-buzz" DAMP_COLLISION
else
    exec "$HOME/.local/bin/mouse-buzz" HAPPY_ALERT
fi
