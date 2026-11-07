#!/bin/bash
# One-time setup for Mac-direct control (studio/mac_bridge.py): CycloneDDS 0.10 (the version Unitree robots
# speak) + its Python binding + unitree_sdk2_python, all inside ~/r1 (venv ~/r1/.venv-sdk).
# Sources: Homebrew (cmake), github.com/eclipse-cyclonedds (official), PyPI cyclonedds 0.10.5 source,
# github.com/unitreerobotics/unitree_sdk2_python (official).
# Already set up? Do not run again: it rebuilds the binding.
set -e
brew list cmake >/dev/null 2>&1 || brew install cmake
cd ~/r1
[ -d .venv-sdk ] || python3 -m venv .venv-sdk
[ -d cyclonedds-src ] || git clone -q -b releases/0.10.x --depth 1 https://github.com/eclipse-cyclonedds/cyclonedds cyclonedds-src
mkdir -p cyclonedds-src/build && cd cyclonedds-src/build
cmake .. -DCMAKE_INSTALL_PREFIX="$HOME/r1/cyclonedds-0.10" -DBUILD_EXAMPLES=OFF -DBUILD_TESTING=OFF -DENABLE_SSL=OFF -DENABLE_SECURITY=OFF >/dev/null
cmake --build . --target install -j8 >/dev/null
echo "✅ CycloneDDS C 0.10 built"
cd ~/r1
CYCLONEDDS_HOME="$HOME/r1/cyclonedds-0.10" .venv-sdk/bin/pip -q uninstall -y cyclonedds || true
# Python 3.13+ renamed _Py_IsFinalizing; the 0.10.5 binding still uses the old name
CFLAGS="-D_Py_IsFinalizing=Py_IsFinalizing" CYCLONEDDS_HOME="$HOME/r1/cyclonedds-0.10" \
  .venv-sdk/bin/pip -q install --no-binary cyclonedds cyclonedds==0.10.5
.venv-sdk/bin/python -c "import cyclonedds.domain; print('✅ Python binding 0.10.5 OK')"
[ -d unitree_sdk2_python ] || git clone -q --depth 1 https://github.com/unitreerobotics/unitree_sdk2_python
.venv-sdk/bin/pip -q install numpy
# --no-deps: its setup.py pins cyclonedds 0.10.2; we keep the 0.10.5 binding built above (same 0.10 protocol)
.venv-sdk/bin/pip -q install --no-deps -e unitree_sdk2_python
.venv-sdk/bin/python -c "import unitree_sdk2py; print('✅ unitree_sdk2py OK')"
