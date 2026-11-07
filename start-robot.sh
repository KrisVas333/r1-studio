#!/bin/bash
# R1 Studio: one command for each way of running it.
#
#   ./start-robot.sh mac                  Mac + cable, no backpack. Robot state + voice/LED/volume (read-only until you add --allow-commands)
#   ./start-robot.sh mac --allow-commands same, and typing GO in the app unlocks voice / LED / volume on the robot
#   ./start-robot.sh pc2 [PIN]            backpack computer (PC2) is on: runs the Studio ON the robot with --live (moves, arms, hands)
#   ./start-robot.sh event PIN [--allow-commands]   like mac, and phones on the same Wi-Fi as this Mac open R1 Remote (PIN needed)
#   ./start-robot.sh sim                  simulator only, no robot
#
# Ctrl+C stops everything this script started. STOP in the app always works without a PIN.
R1="$(cd "$(dirname "$0")" && pwd)"
MODE="${1:-}"; shift
STUDIO_PY="$R1/sim/.venv/bin/python"; [ -x "$STUDIO_PY" ] || STUDIO_PY=python3
SDK_PY="$R1/.venv-sdk/bin/python"
PC2="unitree@192.168.123.164"

robot_port() {  # the Mac network port that has a 192.168.123.x address (the robot cable), or $R1_IFACE
  if [ -n "$R1_IFACE" ]; then echo "$R1_IFACE"; return; fi
  ifconfig 2>/dev/null | awk '/^[a-z]/{i=$1; sub(":","",i)} /inet 192\.168\.123\./{print i; exit}'
}

stop_old() {
  pkill -f "studio/server.py" 2>/dev/null
  pkill -f "studio/mac_bridge.py" 2>/dev/null
  sleep 0.5
}

start_bridge() {  # $1 = extra bridge args
  [ -x "$SDK_PY" ] || { echo "❌ $SDK_PY missing (the Unitree SDK venv). See docs/TUTORIAL.md, Mac-direct section."; exit 1; }
  IF="$(robot_port)"
  if [ -z "$IF" ]; then
    echo "⚠️  No 192.168.123.x port yet. Plug the cable in and run ./connect.sh <port>. The bridge keeps waiting for en16."
    IF="en16"
  fi
  "$SDK_PY" "$R1/studio/mac_bridge.py" --iface "$IF" $1 &
  BRIDGE=$!
  trap 'kill $BRIDGE 2>/dev/null' EXIT INT TERM
  sleep 1
  echo "🔌 bridge on $IF · state: curl -s http://127.0.0.1:8090/state"
}

case "$MODE" in
  mac)
    stop_old
    ALLOW=""; [ "$1" = "--allow-commands" ] && ALLOW="--allow-commands"
    start_bridge "$ALLOW"
    echo "🤖 Mac-direct · open http://localhost:8080 (header chip shows the robot)"
    "$STUDIO_PY" "$R1/studio/server.py" --bridge
    ;;
  event)
    PIN="$1"; shift
    [ -n "$PIN" ] || { echo "Usage: ./start-robot.sh event 4821 [--allow-commands]   (pick any PIN)"; exit 1; }
    stop_old
    ALLOW=""; [ "$1" = "--allow-commands" ] && ALLOW="--allow-commands"
    start_bridge "$ALLOW --pin $PIN"
    echo "📱 Event mode · phones on this Wi-Fi: http://<this Mac's Wi-Fi address>:8080/phone.html  PIN $PIN"
    "$STUDIO_PY" "$R1/studio/server.py" --bridge --bind 0.0.0.0 --pin "$PIN"
    ;;
  pc2)
    if ! ping -c1 -t2 192.168.123.164 >/dev/null 2>&1; then
      echo "❌ PC2 (192.168.123.164) does not answer. Is the backpack computer on? Without it use: ./start-robot.sh mac"; exit 1
    fi
    PIN_ARG=""; [ -n "$1" ] && PIN_ARG="--pin $1"
    echo "🎒 PC2 live mode · open http://192.168.123.164:8080/phone.html on this Mac"
    ssh -t "$PC2" "python3 ~/r1-kit/studio/server.py --live $PIN_ARG"
    ;;
  sim)
    stop_old
    "$STUDIO_PY" "$R1/studio/server.py"
    ;;
  *)
    sed -n '2,10p' "$0" | sed 's/^# \{0,1\}//'
    exit 1
    ;;
esac
