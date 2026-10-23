// hand_cli — type finger commands for one BrainCo Revo2 hand.
// Needs brainco_hand_server running. Values 0..1 per finger,
// order [Thumb, Thumb_aux, Index, Middle, Ring, Pinky].
// From the stock test: {0,0,0,0,0,0} -> {0,1,1,1,1,1} -> {1,...} = open -> fist (verify on the unit).
#include "dds/Publisher.h"
#include "dds/Subscription.h"
#include <unitree/idl/go2/MotorCmds_.hpp>
#include <unitree/idl/go2/MotorStates_.hpp>
#include <iostream>
#include <map>
#include <sstream>

using Pose = std::array<float, 6>;

int main(int argc, char** argv)
{
    std::string side = argc > 1 ? argv[1] : "left";
    std::string iface = argc > 2 ? argv[2] : "";
    std::cout << "Usage: " << argv[0] << " [left|right] [network_interface]\n";
    unitree::robot::ChannelFactory::Instance()->Init(0, iface);

    auto cmd = std::make_unique<unitree::robot::RealTimePublisher<unitree_go::msg::dds_::MotorCmds_>>("rt/brainco/" + side + "/cmd");
    cmd->msg_.cmds().resize(6);
    for (auto& f : cmd->msg_.cmds()) f.dq() = 1.;
    auto state = std::make_shared<unitree::robot::SubscriptionBase<unitree_go::msg::dds_::MotorStates_>>("rt/brainco/" + side + "/state");
    std::cout << "Waiting for rt/brainco/" << side << "/state ...\n";
    state->wait_for_connection();

    const std::map<std::string, Pose> poses = {
        {"open",  {0, 0, 0, 0, 0, 0}},
        {"fist",  {1, 1, 1, 1, 1, 1}},
        {"point", {1, 1, 0, 1, 1, 1}},
        {"peace", {1, 1, 0, 0, 1, 1}},
        {"thumb", {0, 0, 1, 1, 1, 1}},
        {"pinch", {0.6, 0.6, 0.6, 0, 0, 0}},
    };

    auto send = [&](const Pose& p) {
        for (int i = 0; i < 6; i++) cmd->msg_.cmds()[i].q() = std::min(1.f, std::max(0.f, p[i]));
        cmd->unlockAndPublish();
    };

    std::cout << "Commands: open | fist | point | peace | thumb | pinch | set t ta i m r p | state | quit\n";
    std::string line;
    while (std::cout << side << "> " && std::getline(std::cin, line)) {
        std::istringstream ss(line);
        std::string c;
        ss >> c;
        if (c == "quit" || c == "q") break;
        if (poses.count(c)) { send(poses.at(c)); continue; }
        if (c == "set") {
            Pose p{};
            for (auto& v : p) if (!(ss >> v)) { std::cout << "need 6 numbers 0..1\n"; goto next; }
            send(p);
        } else if (c == "state") {
            auto s = state->msg_;
            for (auto& m : s.states()) std::cout << m.q() << " ";
            std::cout << "\n";
        } else if (!c.empty()) {
            std::cout << "unknown: " << c << "\n";
        }
        next:;
    }
    return 0;
}
