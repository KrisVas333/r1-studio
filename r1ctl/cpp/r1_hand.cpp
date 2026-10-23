// r1_hand — move one BrainCo Revo2 hand to a pose (needs brainco_hand_server running).
//   r1_hand <iface> <left|right> q0 q1 q2 q3 q4 q5 [duration_ms]
// q in 0..1, order [Thumb, Thumb_aux, Index, Middle, Ring, Pinky]. ⚠️ 0=open/1=closed unverified on our unit.
#include <unitree/robot/channel/channel_publisher.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/idl/go2/MotorCmds_.hpp>
#include <unitree/idl/go2/MotorStates_.hpp>
#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <iostream>
#include <mutex>
#include <thread>

using namespace unitree::robot;
using Cmds = unitree_go::msg::dds_::MotorCmds_;
using States = unitree_go::msg::dds_::MotorStates_;

int main(int argc, char** argv)
{
    if (argc < 9) {
        std::cout << "r1_hand <iface> <left|right> q0..q5 [duration_ms]\n";
        return 1;
    }
    ChannelFactory::Instance()->Init(0, argv[1]);
    std::string side = argv[2];
    std::array<float, 6> target;
    for (int i = 0; i < 6; i++) target[i] = std::clamp(std::stof(argv[3 + i]), 0.f, 1.f);
    int dur_ms = argc > 9 ? std::max(100, std::stoi(argv[9])) : 600;

    std::mutex mu;
    std::array<float, 6> now{};
    std::atomic<bool> got{false};
    ChannelSubscriber<States> sub("rt/brainco/" + side + "/state");
    sub.InitChannel([&](const void* m) {
        auto* s = (const States*)m;
        std::lock_guard<std::mutex> l(mu);
        for (int i = 0; i < 6 && i < (int)s->states().size(); i++) now[i] = s->states()[i].q();
        got = true;
    });
    ChannelPublisher<Cmds> pub("rt/brainco/" + side + "/cmd");
    pub.InitChannel();

    for (int i = 0; i < 30 && !got; i++) std::this_thread::sleep_for(std::chrono::milliseconds(100));
    if (!got) {
        std::cerr << "no state on rt/brainco/" << side << "/state — is brainco_hand_server running?\n";
        return 2;
    }
    std::array<float, 6> start;
    { std::lock_guard<std::mutex> l(mu); start = now; }

    Cmds msg;
    msg.cmds().resize(6);
    int steps = dur_ms / 20;
    for (int k = 1; k <= steps; k++) {
        float s = float(k) / steps;
        s = s * s * (3 - 2 * s);
        for (int i = 0; i < 6; i++) {
            msg.cmds()[i].q() = start[i] + (target[i] - start[i]) * s;
            msg.cmds()[i].dq() = 1.f;
        }
        pub.Write(msg);
        std::this_thread::sleep_for(std::chrono::milliseconds(20));
    }
    return 0;
}
