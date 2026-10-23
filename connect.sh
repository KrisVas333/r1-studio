#!/bin/bash
# Step 1-2: give the Mac an address on the robot's network and check the robot answers.
# Usage: ./connect.sh            -> lists adapters
#        ./connect.sh en7        -> sets en7 to 192.168.123.222 and pings the robot
IF="$1"
if [ -z "$IF" ]; then
  echo "Plug the USB-C Ethernet adapter + cable into the robot, then run: ./connect.sh <device>"
  networksetup -listallhardwareports | grep -B1 -A1 "Device: en" | grep -v "^--"
  exit 0
fi
sudo ifconfig "$IF" 192.168.123.222 netmask 255.255.255.0 up || exit 1
echo "Mac = 192.168.123.222 on $IF"
for ip in 192.168.123.161 192.168.123.164; do
  if ping -c1 -t2 $ip >/dev/null 2>&1; then echo "✅ $ip answers"; else echo "❌ $ip no answer"; fi
done
echo "Next: ssh unitree@192.168.123.164   (PC2, the dev computer)"
