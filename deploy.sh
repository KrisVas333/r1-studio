#!/bin/bash
# Step 4: copy our code to the robot's PC2 and build it there (same Ubuntu 20.04 / GCC 9.4 we tested in Docker).
# Puts everything in ~/r1-kit on PC2. Never touches the factory ~/brainco_hand_service.
PC2="${PC2:-unitree@192.168.123.164}"
cd "$(dirname "$0")"
rsync -az --delete --exclude 'build*' --exclude '.git' --exclude 'bin/' \
  --exclude 'cache/' --exclude 'projects/' --exclude 'previews/' unitree_sdk2-modified unitree_sdk2 brainco_hand_service r1ctl studio "$PC2:~/r1-kit/" || exit 1
ssh -t "$PC2" 'set -e
  cd ~/r1-kit/unitree_sdk2 && mkdir -p build && cd build && cmake .. -DBUILD_EXAMPLES=ON >/dev/null && make -j6 r1_arm_action_example r1_loco_client r1_audio_client_example
  cd ~/r1-kit/unitree_sdk2-modified && mkdir -p build && cd build && cmake .. >/dev/null && make -j6
  if [ -f /usr/local/lib/libunitree_sdk2.a ] || [ -d /usr/local/include/unitree ]; then
    cd ~/r1-kit/brainco_hand_service && mkdir -p build && cd build && cmake .. >/dev/null && make -j6
    cd ~/r1-kit/r1ctl/cpp && mkdir -p build && cd build && cmake .. >/dev/null && make -j6
    python3 -c "import yaml" 2>/dev/null || echo "⚠️ run: sudo apt install python3-yaml"
    sudo ln -sf ~/r1-kit/r1ctl/r1ctl.py /usr/local/bin/r1ctl 2>/dev/null || true
  else echo "⚠️ SDK not installed system-wide on PC2: run  cd ~/r1-kit/unitree_sdk2/build && sudo make install  then re-run deploy"; fi
  echo; echo "Studio on the robot:  python3 ~/r1-kit/studio/server.py --live   → open http://192.168.123.164:8080 on the Mac"
  echo; echo "✅ Built. Programs:"; ls ~/r1-kit/unitree_sdk2-modified/build/bin ~/r1-kit/brainco_hand_service/bin ~/r1-kit/r1ctl/bin 2>/dev/null'
