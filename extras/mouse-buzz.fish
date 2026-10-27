# Вибро-сигнал на MX Master 4, когда команда шла дольше минуты:
# успех — COMPLETED, ошибка — ANGRY_ALERT. Положить в ~/.config/fish/conf.d/.
function __mouse_buzz_long_cmd --on-event fish_postexec
    set -l st $status
    test "$CMD_DURATION" -gt 60000; or return
    test -x ~/.local/bin/mouse-buzz; or return
    if test $st -eq 0
        ~/.local/bin/mouse-buzz COMPLETED >/dev/null 2>&1 &
    else
        ~/.local/bin/mouse-buzz ANGRY_ALERT >/dev/null 2>&1 &
    end
    disown 2>/dev/null
end
