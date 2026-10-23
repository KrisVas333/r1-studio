# R1 dev image: Ubuntu 20.04 + GCC 9.4 (same as robot PC2) + official unitree_sdk2 installed
FROM ubuntu:20.04
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y cmake g++ build-essential git vim iproute2 iputils-ping openssh-client \
    libyaml-cpp-dev libeigen3-dev libboost-all-dev libspdlog-dev libfmt-dev && rm -rf /var/lib/apt/lists/*
COPY unitree_sdk2 /opt/src/unitree_sdk2
RUN cd /opt/src/unitree_sdk2 && rm -rf build* && mkdir build && cd build && cmake .. -DBUILD_EXAMPLES=OFF && make install
WORKDIR /r1
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y python3 python3-yaml && rm -rf /var/lib/apt/lists/*
