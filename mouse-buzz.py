#!/usr/bin/env python3
"""Вибро-сигнал на MX Master 4 напрямую через HID++ (без solaar, ~10 мс вместо 2,5 с).

    mouse-buzz [СИГНАЛ]      по умолчанию COMPLETED
    mouse-buzz --list

Шлёт функцию 4 (play waveform) фичи HAPTIC (0x19B0) — то же, что делает
`solaar config <мышь> haptic-play <сигнал>`. Протокол и поиск мыши — в hidpp.py.
Если мыши нет (спит, выключена, другая машина) — молча выходит с кодом 1.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))  # запуск через ссылку из ~/.local/bin
import hidpp  # noqa: E402

WAVEFORMS = {
    "SHARP_STATE_CHANGE": 0x00, "DAMP_STATE_CHANGE": 0x01, "SHARP_COLLISION": 0x02,
    "DAMP_COLLISION": 0x03, "SUBTLE_COLLISION": 0x04, "HAPPY_ALERT": 0x05,
    "ANGRY_ALERT": 0x06, "COMPLETED": 0x07, "SQUARE": 0x08, "WAVE": 0x09,
    "FIREWORK": 0x0A, "MAD": 0x0B, "KNOCK": 0x0C, "JINGLE": 0x0D, "RINGING": 0x0E,
    "WHISPER_COLLISION": 0x1B,
}


def buzz(mouse, name):
    return mouse.call(hidpp.F_HAPTIC, 4, bytes([WAVEFORMS[name]])) is not None


def main():
    arg = (sys.argv[1] if len(sys.argv) > 1 else "COMPLETED").upper().replace(" ", "_")
    if arg in ("--LIST", "-L"):
        print("\n".join(WAVEFORMS))
        return 0
    if arg not in WAVEFORMS:
        print(f"неизвестный сигнал {arg}; mouse-buzz --list", file=sys.stderr)
        return 2
    try:
        with hidpp.Mouse() as m:
            return 0 if buzz(m, arg) else 1
    except hidpp.NoMouse:
        return 1


if __name__ == "__main__":
    sys.exit(main())
