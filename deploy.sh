#!/bin/bash
# Step 4: copy our code to the robot's PC2 and build it there (same Ubuntu 20.04 / GCC 9.4 we tested in Docker).
# Puts everything in ~/r1-kit on PC2. Never touches the factory ~/brainco_hand_service.
PC2="${PC2:-unitree@192.168.123.164}"
cd "$(dirname "$0")"
# u_* = moves made in the app on the robot: --delete must leave them alone
rsync -az --delete --exclude 'build*' --exclude '.git' --exclude 'bin/' --exclude 'u_*' \
  --exclude 'cache/' --exclude 'projects/' --exclude 'previews/' unitree_sdk2-modified unitree_sdk2 brainco_hand_service r1ctl studio "$PC2:~/r1-kit/" || exit 1
# Ready-made voice lines: the robot speaks them with no internet and no key. Talk recordings stay behind.
rsync -az --exclude 'voice_*' r1ctl/cache/ "$PC2:~/r1-kit/r1ctl/cache/" || exit 1
# R1 yoga app (served by the studio at /joga/) + its moves. Needs the r1-joga clone at <kit>/r1-joga (git clone into ~/r1/r1-joga).
JOGA="${JOGA:-r1-joga}"
if [ -f "$JOGA/index.html" ]; then
  rsync -az --delete --exclude '.git' "$JOGA/" "$PC2:~/r1-kit/r1-joga/" || exit 1
  echo "🧘 copied $JOGA → PC2:~/r1-kit/r1-joga"
else
  echo "⚠️ no $JOGA/index.html here: yoga app skipped (git clone https://github.com/KrisVas333/r1-joga r1-joga)"
fi
ssh -t "$PC2" 'set -e
  cd ~/r1-kit/unitree_sdk2 && mkdir -p build && cd build && cmake .. -DBUILD_EXAMPLES=ON >/dev/null && make -j6 r1_arm_action_example r1_loco_client r1_audio_client_example
  cd ~/r1-kit/unitree_sdk2-modified && mkdir -p build && cd build && cmake .. >/dev/null && make -j6
  if [ -f /usr/local/lib/libunitree_sdk2.a ] || [ -d /usr/local/include/unitree ]; then
    cd ~/r1-kit/brainco_hand_service && mkdir -p build && cd build && cmake .. >/dev/null && make -j6
    cd ~/r1-kit/r1ctl/cpp && mkdir -p build && cd build && cmake .. >/dev/null && make -j6
    python3 -c "import yaml" 2>/dev/null || echo "⚠️ run: sudo apt install python3-yaml"
    sudo ln -sf ~/r1-kit/r1ctl/r1ctl.py /usr/local/bin/r1ctl 2>/dev/null || true
  else
    echo; echo "❌ NOT BUILT. The SDK is not installed on the robot. Run these, then run deploy.sh again:"
    echo "   ssh unitree@192.168.123.164"
    echo "   cd ~/r1-kit/unitree_sdk2/build && sudo make install"
    exit 1
  fi
  if [ -d ~/r1-kit/r1-joga/export ]; then
    echo; echo "🧘 installing yoga moves into the r1ctl library (validated by r1ctl, nothing moves):"
    python3 ~/r1-kit/r1ctl/r1ctl.py install ~/r1-kit/r1-joga/export | tail -3
    ls ~/r1-kit/r1ctl/library/arm | grep -c "^joga_l" | sed "s/^/   joga arm moves in library: /"
  fi
  for prog in r1_arm r1_hand r1_say; do
    [ -x ~/r1-kit/r1ctl/bin/$prog ] || { echo "❌ NOT BUILT: $prog is missing. Send the last 20 lines above."; exit 1; }
  done
  [ -x ~/r1-kit/unitree_sdk2/build/bin/r1_loco_client ] || { echo "❌ NOT BUILT: r1_loco_client is missing. Send the last 20 lines above."; exit 1; }
  echo; echo "R1 Remote on the robot: python3 ~/r1-kit/studio/server.py --live → http://192.168.123.164:8080/phone.html (mic: https://192.168.123.164:8443/phone.html)"
  echo; echo "✅ Built. Programs:"; ls ~/r1-kit/unitree_sdk2-modified/build/bin ~/r1-kit/brainco_hand_service/bin ~/r1-kit/r1ctl/bin 2>/dev/null'
