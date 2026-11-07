// r1_arm — arm/waist/head motion over rt/arm_sdk (same mechanism as the official
// r1_arm_sdk_dds_example). 13 joints in ArmSdk::JOINTS order:
//   L shoulder pitch/roll/yaw, L elbow, L wrist roll,
//   R shoulder pitch/roll/yaw, R elbow, R wrist roll, waist yaw, head pitch, head yaw.
// ⚠️ A7 arms have extra wrist joints (indices 20-21, 27-28); not driven here.
//
//   r1_arm <iface> pose  q0..q12 [max_vel]       move to a pose, then release
//   r1_arm <iface> traj  <file.csv> [speed]      play t,q0..q12 rows (time-indexed)
//   r1_arm <iface> record <file.csv> <seconds> [left|right|both]
//                                                 make chosen arm(s) limp, record by hand
//   r1_arm <iface> state                         print current 13 joint positions
//   r1_arm <iface> serve                         hold the arm between commands read from stdin:
//                                                 "pose q0..q12 vel" · "traj file speed" · "release"
//                                                 (auto-release after 30 s idle or when stdin closes)
// Ctrl-C, kill, or a dropped ssh: the arms go back slowly to where they were, then control is handed back.
// A second Ctrl-C skips the slow return. Unitree issue #182 says mode_pr may act as a switch, not a percent,
// so the old ramp alone could end in a jump. Coming home first means there is nothing left to jump.
#include "unitree/dds_wrapper/robots/g1/g1.h"
#include "unitree/dds_wrapper/robots/r1/r1.h"
#include <atomic>
#include <csignal>
#include <fstream>
#include <sstream>
#include <deque>
#include <mutex>

using Vec = Eigen::VectorXf;
static std::atomic<int> g_stop{0};
static void on_stop(int) { g_stop++; }

static const float KP[13] = {50, 50, 40, 40, 30, 50, 50, 40, 40, 30, 50, 15, 15};
static const float KD[13] = {2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3, 1, 1};
static const float MAX_STEP = 0.02f;  // rad per 10 ms tick = 2 rad/s hard cap on any joint
static const float HOME_VEL = 1.0f;   // rad/s, top speed of the walk home after a move or a STOP

class Arm
{
public:
    Arm()
    {
        state_ = std::make_shared<unitree::robot::g1::subscription::LowState>();
        state_->wait_for_connection();
        sdk_ = std::make_unique<unitree::robot::r1::publisher::ArmSdk>();
        n_ = sdk_->JOINTS.size();
        cmd_ = current();
    }

    Vec current()
    {
        Vec q(n_);
        for (int i = 0; i < n_; i++) q[i] = state_->msg_.motor_state().at(idx(i)).q();
        return q;
    }

    // Take control, holding the current pose; kp_scale per joint lets arms go limp.
    void enable(const std::vector<float>& kp_scale = {})
    {
        cmd_ = current();
        home_ = cmd_;
        sdk_->weight(1.0);
        for (int i = 0; i < n_; i++) {
            auto& m = sdk_->msg_.motor_cmd().at(idx(i));
            float s = kp_scale.empty() ? 1.f : kp_scale[i];
            m.q(cmd_[i]); m.kp(KP[i] * s); m.kd(KD[i]); m.dq(0); m.tau(0);
        }
        sdk_->unlockAndPublish();
    }

    void set_kp_scale(const std::vector<float>& s)
    {
        for (int i = 0; i < n_; i++) sdk_->msg_.motor_cmd().at(idx(i)).kp(KP[i] * s[i]);
    }

    // One 10 ms tick toward target, rate limited.
    void step(const Vec& target)
    {
        for (int i = 0; i < n_; i++) {
            float d = std::clamp(target[i] - cmd_[i], -MAX_STEP, MAX_STEP);
            cmd_[i] += d;
            sdk_->msg_.motor_cmd().at(idx(i)).q(cmd_[i]);
        }
        sdk_->unlockAndPublish();
        std::this_thread::sleep_for(std::chrono::milliseconds(10));
    }

    void movej(const Vec& target, float max_vel)
    {
        Vec start = cmd_;
        float dur = std::max(0.2f, (target - start).cwiseAbs().maxCoeff() / max_vel);
        for (float t = 0; t < dur && !g_stop; t += 0.01f) {
            float s = t / dur;
            s = s * s * (3 - 2 * s);  // smoothstep
            step(start + (target - start) * s);
        }
    }

    void hold() { step(cmd_); }

    // Back to the pose control was taken in, at a walking pace, whatever the stop flag says.
    void go_home()
    {
        Vec start = cmd_;
        float dur = 1.5f * (home_ - start).cwiseAbs().maxCoeff() / HOME_VEL;  // smoothstep peaks at 1.5 x the average
        for (float t = 0; t < dur && g_stop.load() < 2; t += 0.01f) {
            float s = t / dur;
            s = s * s * (3 - 2 * s);
            step(start + (home_ - start) * s);
        }
    }

    void release(float dur = 1.5f)
    {
        go_home();
        auto t0 = std::chrono::steady_clock::now();
        for (;;) {
            float e = std::chrono::duration<float>(std::chrono::steady_clock::now() - t0).count();
            if (e > dur) break;
            sdk_->weight(std::clamp((dur - e) / dur, 0.f, 1.f));
            sdk_->unlockAndPublish();
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        sdk_->weight(0);
        sdk_->unlockAndPublish();
    }

    int n_;
    Vec cmd_, home_;

private:
    int idx(int i) const { return static_cast<int>(sdk_->JOINTS[i]); }
    std::shared_ptr<unitree::robot::g1::subscription::LowState> state_;
    std::unique_ptr<unitree::robot::r1::publisher::ArmSdk> sdk_;
};

static bool parse_row(const std::string& line, float& t, Vec& q)
{
    std::stringstream ss(line);
    std::string cell;
    std::vector<float> v;
    while (std::getline(ss, cell, ',')) {
        try { v.push_back(std::stof(cell)); } catch (...) { return false; }
    }
    if (v.size() != 14) return false;
    t = v[0];
    q = Vec(13);
    for (int i = 0; i < 13; i++) q[i] = v[i + 1];
    return true;
}

static int usage()
{
    std::cout << "r1_arm <iface> pose q0..q12 [max_vel] | traj <csv> [speed] | record <csv> <sec> [left|right|both] | state\n";
    return 1;
}

int main(int argc, char** argv)
{
    if (argc < 3) return usage();
    for (int sig : {SIGINT, SIGTERM, SIGHUP}) std::signal(sig, on_stop);
    std::signal(SIGPIPE, SIG_IGN);  // a closed ssh or pipe must not kill the walk home
    unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);
    std::string mode = argv[2];
    Arm arm;

    if (mode == "state") {
        Vec q = arm.current();
        for (int i = 0; i < q.size(); i++) std::cout << q[i] << (i + 1 < q.size() ? " " : "\n");
        return 0;
    }

    if (mode == "pose") {
        if (argc < 16) return usage();
        Vec q(13);
        for (int i = 0; i < 13; i++) q[i] = std::stof(argv[3 + i]);
        float vel = argc > 16 ? std::stof(argv[16]) : 0.8f;
        arm.enable();
        arm.movej(q, std::min(vel, 1.5f));
        for (int i = 0; i < 30 && !g_stop; i++) arm.hold();
        arm.release();
        return 0;
    }

    if (mode == "traj") {
        if (argc < 4) return usage();
        float speed = argc > 4 ? std::clamp(std::stof(argv[4]), 0.25f, 2.f) : 1.f;
        std::ifstream f(argv[3]);
        std::vector<std::pair<float, Vec>> rows;
        std::string line;
        while (std::getline(f, line)) {
            float t; Vec q;
            if (parse_row(line, t, q)) rows.push_back({t, q});  // header/bad lines skipped
        }
        if (rows.size() < 2) { std::cerr << "need >=2 rows of t,q0..q12\n"; return 1; }
        arm.enable();
        arm.movej(rows[0].second, 0.6f);  // slow approach to the first frame
        std::cout << "go" << std::endl;   // r1ctl starts the voice and the fingers on this line
        auto t0 = std::chrono::steady_clock::now();
        size_t k = 0;
        while (!g_stop) {
            float t = std::chrono::duration<float>(std::chrono::steady_clock::now() - t0).count() * speed + rows[0].first;
            while (k + 1 < rows.size() && rows[k + 1].first <= t) k++;
            if (k + 1 >= rows.size()) break;
            float a = (t - rows[k].first) / std::max(1e-3f, rows[k + 1].first - rows[k].first);
            arm.step(rows[k].second + (rows[k + 1].second - rows[k].second) * std::clamp(a, 0.f, 1.f));
        }
        for (int i = 0; i < 30 && !g_stop; i++) arm.hold();
        arm.release();
        return 0;
    }

    if (mode == "record") {
        if (argc < 5) return usage();
        float secs = std::stof(argv[4]);
        std::string which = argc > 5 ? argv[5] : "right";
        std::vector<float> limp(13, 1.f);
        for (int i = 0; i < 5; i++) {
            if (which == "left" || which == "both") limp[i] = 0.f;
            if (which == "right" || which == "both") limp[5 + i] = 0.f;
        }
        arm.enable();
        std::cout << "Arm(s) going soft in 2.5 s. Move them by hand. Recording " << secs << " s." << std::endl;
        for (float t = 0; t < 2.5f && !g_stop; t += 0.01f) {
            float s = t / 2.5f;
            s = s * s * (3 - 2 * s);
            std::vector<float> k(13);
            for (int i = 0; i < 13; i++) k[i] = 1.f + (limp[i] - 1.f) * s;
            arm.set_kp_scale(k);
            arm.hold();
        }
        std::ofstream out(argv[3]);
        out << "t,lsp,lsr,lsy,le,lwr,rsp,rsr,rsy,re,rwr,waist_yaw,head_pitch,head_yaw\n";
        auto t0 = std::chrono::steady_clock::now();
        for (;;) {
            float t = std::chrono::duration<float>(std::chrono::steady_clock::now() - t0).count();
            if (t > secs || g_stop) break;
            Vec q = arm.current();
            out << t;
            for (int i = 0; i < 13; i++) out << "," << q[i];
            out << "\n";
            for (int i = 0; i < 13; i++) if (limp[i] == 0.f) arm.cmd_[i] = q[i];  // limp joints follow the hand
            arm.hold();
        }
        out.close();
        // Stiffen where the arm now is, then hand back.
        g_stop = 0;
        for (float t = 0; t < 2.5f; t += 0.01f) {
            float s = t / 2.5f;
            std::vector<float> k(13);
            for (int i = 0; i < 13; i++) k[i] = limp[i] + (1.f - limp[i]) * s;
            arm.set_kp_scale(k);
            arm.hold();
        }
        arm.release();
        std::cout << "Saved " << argv[3] << std::endl;
        return 0;
    }
    if (mode == "serve") {
        std::mutex mu;
        std::deque<std::string> q;
        std::atomic<bool> eof{false};
        std::thread reader([&] {
            std::string l;
            while (std::getline(std::cin, l)) { std::lock_guard<std::mutex> g(mu); q.push_back(l); }
            eof = true;
        });
        reader.detach();
        bool enabled = false;
        auto idle = std::chrono::steady_clock::now();
        std::cout << "ready" << std::endl;
        while (!g_stop) {
            std::string line;
            { std::lock_guard<std::mutex> g(mu); if (!q.empty()) { line = q.front(); q.pop_front(); } }
            if (line.empty()) {
                if (eof || std::chrono::steady_clock::now() - idle > std::chrono::seconds(30)) break;
                if (enabled) arm.hold(); else std::this_thread::sleep_for(std::chrono::milliseconds(10));
                continue;
            }
            idle = std::chrono::steady_clock::now();
            std::stringstream ss(line);
            std::string cmd;
            ss >> cmd;
            if (cmd == "release") {
                if (enabled) arm.release();
                enabled = false;
            } else if (cmd == "pose") {
                Vec t(13);
                for (int i = 0; i < 13; i++) ss >> t[i];
                float vel = 0.8f;
                ss >> vel;
                if (!enabled) { arm.enable(); enabled = true; }
                arm.movej(t, std::clamp(vel, 0.1f, 1.5f));
            } else if (cmd == "traj") {
                std::string file;
                float speed = 1.f;
                ss >> file >> speed;
                std::ifstream f(file);
                std::vector<std::pair<float, Vec>> rows;
                std::string l;
                while (std::getline(f, l)) { float t; Vec v; if (parse_row(l, t, v)) rows.push_back({t, v}); }
                if (rows.size() < 2) { std::cout << "error bad csv" << std::endl; continue; }
                if (!enabled) { arm.enable(); enabled = true; }
                arm.movej(rows[0].second, 0.6f);
                auto t0 = std::chrono::steady_clock::now();
                size_t k = 0;
                speed = std::clamp(speed, 0.25f, 2.f);
                while (!g_stop) {
                    float t = std::chrono::duration<float>(std::chrono::steady_clock::now() - t0).count() * speed + rows[0].first;
                    while (k + 1 < rows.size() && rows[k + 1].first <= t) k++;
                    if (k + 1 >= rows.size()) break;
                    float a = (t - rows[k].first) / std::max(1e-3f, rows[k + 1].first - rows[k].first);
                    arm.step(rows[k].second + (rows[k + 1].second - rows[k].second) * std::clamp(a, 0.f, 1.f));
                }
            }
            std::cout << "done" << std::endl;
        }
        if (enabled) arm.release();
        return 0;
    }
    return usage();
}
