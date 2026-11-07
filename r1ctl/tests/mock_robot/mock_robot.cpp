// Stand-in robot for testing r1_arm: answers rt/lowstate from the last rt/arm_sdk command and logs what arrives.
#include <unitree/robot/channel/channel_publisher.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/idl/hg/LowCmd_.hpp>
#include <unitree/idl/hg/LowState_.hpp>
#include <fstream>
#include <mutex>
#include <chrono>
#include <thread>
#include <iostream>
using namespace unitree::robot;
static std::mutex mu; static unitree_hg::msg::dds_::LowCmd_ last; static bool got=false;
static std::ofstream out;
static auto t0=std::chrono::steady_clock::now();
static void on_cmd(const void* m){ auto c=*(const unitree_hg::msg::dds_::LowCmd_*)m; std::lock_guard<std::mutex> g(mu); last=c; got=true;}
int main(int argc,char**argv){
  ChannelFactory::Instance()->Init(0,argv[1]); out.open(argv[2]);
  float rest=argc>3?std::stof(argv[3]):0.3f;
  ChannelPublisher<unitree_hg::msg::dds_::LowState_> pub("rt/lowstate"); pub.InitChannel();
  ChannelSubscriber<unitree_hg::msg::dds_::LowCmd_> sub("rt/arm_sdk"); sub.InitChannel(on_cmd,1);
  unitree_hg::msg::dds_::LowState_ st; for(auto&m:st.motor_state()) m.q(rest);
  int n=0;
  for(;;){ {std::lock_guard<std::mutex> g(mu); if(got){ for(int i=0;i<35;i++) if(last.motor_cmd()[i].kp()>0) st.motor_state()[i].q(last.motor_cmd()[i].q());
      if(n%5==0){ double t=std::chrono::duration<double>(std::chrono::steady_clock::now()-t0).count(); out<<t<<" "<<(int)last.mode_pr(); for(int i=0;i<35;i++) if(last.motor_cmd()[i].kp()>0){out<<" "<<last.motor_cmd()[i].q();break;} out<<"\n"; out.flush(); }}}
    pub.Write(st); n++; std::this_thread::sleep_for(std::chrono::milliseconds(2)); }
}
