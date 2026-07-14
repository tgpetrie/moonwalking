#!/bin/zsh

set -e

SERIAL="R5CW6267XVP"
DISPLAY_ID="4630946592180194435"

/opt/homebrew/bin/adb -s "$SERIAL" shell input keyevent KEYCODE_WAKEUP >/dev/null 2>&1 || true

/opt/homebrew/bin/adb -s "$SERIAL" exec-out \
  screenrecord \
  --display-id "$DISPLAY_ID" \
  --size 720x1280 \
  --bit-rate 4M \
  --time-limit 0 \
  --output-format=h264 - |
  /opt/homebrew/bin/ffplay \
    -window_title "Android USB Viewer" \
    -x 360 \
    -left 40 \
    -top 40 \
    -alwaysontop \
    -nostats \
    -loglevel warning \
    -fflags nobuffer \
    -flags low_delay \
    -framedrop \
    -probesize 32 \
    -sync video \
    -an -
