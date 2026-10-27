#!/usr/bin/env python3
"""Haptic signal on the MX Master 4 directly over HID++ (no solaar, ~10 ms instead of 2.5 s).

    mouse-buzz [WAVEFORM]      COMPLETED by default
    mouse-buzz --list

Sends function 4 (play waveform) of the HAPTIC feature (0x19B0) — the same as
`solaar config <mouse> haptic-play <waveform>`. Protocol and mouse discovery — in hidpp.py.
If there is no mouse (asleep, switched off, another machine) — exits silently with code 1.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))  # launched through a symlink from ~/.local/bin
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
        print(f"unknown waveform {arg}; mouse-buzz --list", file=sys.stderr)
        return 2
    try:
        with hidpp.Mouse() as m:
            return 0 if buzz(m, arg) else 1
    except hidpp.NoMouse:
        return 1


if __name__ == "__main__":
    sys.exit(main())
