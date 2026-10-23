// r1_say — robot voice + LEDs through the R1 audio service.
//   r1_say <iface> tts <speaker_id> <text>     built-in TTS (0 = Chinese, 1 = English)
//   r1_say <iface> wav <file.wav>              play 16 kHz mono WAV (e.g. ElevenLabs Lithuanian)
//   r1_say <iface> led <r> <g> <b>
//   r1_say <iface> volume <0-100>
//   r1_say <iface> listen [seconds]            print ASR text from rt/audio_msg
#include <unitree/common/time/time_tool.hpp>
#include <unitree/idl/ros2/String_.hpp>
#include <unitree/robot/channel/channel_subscriber.hpp>
#include <unitree/robot/r1/audio/audio_client.hpp>
#include <fstream>
#include <iostream>
#include <thread>
#include "wav.hpp"

int main(int argc, char** argv)
{
    if (argc < 3) {
        std::cout << "r1_say <iface> tts <id> <text> | wav <file> | led r g b | volume n | listen [s]\n";
        return 1;
    }
    unitree::robot::ChannelFactory::Instance()->Init(0, argv[1]);
    std::string mode = argv[2];

    if (mode == "listen") {
        int secs = argc > 3 ? std::stoi(argv[3]) : 10;
        unitree::robot::ChannelSubscriber<std_msgs::msg::dds_::String_> sub("rt/audio_msg");
        sub.InitChannel([](const void* m) {
            std::cout << ((const std_msgs::msg::dds_::String_*)m)->data() << std::endl;
        });
        std::this_thread::sleep_for(std::chrono::seconds(secs));
        return 0;
    }

    unitree::robot::r1::AudioClient client;
    client.Init();
    client.SetTimeout(10.0f);
    int32_t ret = -1;

    if (mode == "tts" && argc >= 5) {
        ret = client.TtsMaker(argv[4], std::stoi(argv[3]));
    } else if (mode == "led" && argc >= 6) {
        ret = client.LedControl(std::stoi(argv[3]), std::stoi(argv[4]), std::stoi(argv[5]));
    } else if (mode == "volume" && argc >= 4) {
        ret = client.SetVolume(std::stoi(argv[3]));
    } else if (mode == "wav" && argc >= 4) {
        int32_t rate = -1;
        int8_t ch = 0;
        bool ok = false;
        std::vector<uint8_t> pcm = ReadWave(argv[3], &rate, &ch, &ok);
        if (!ok || rate != 16000 || ch != 1) {
            std::cerr << "need 16 kHz mono WAV (got " << rate << " Hz, " << int(ch) << " ch)\n";
            return 1;
        }
        std::string id = std::to_string(unitree::common::GetCurrentTimeMillisecond());
        const size_t chunk = 96000;  // 3 s, as in the official example
        for (size_t off = 0; off < pcm.size(); off += chunk) {
            std::vector<uint8_t> part(pcm.begin() + off, pcm.begin() + std::min(pcm.size(), off + chunk));
            client.PlayStream("r1ctl", id, part);
            unitree::common::Sleep(1);
        }
        // let the tail finish before stopping
        std::this_thread::sleep_for(std::chrono::milliseconds(500 + (pcm.size() % chunk) / 32));
        ret = client.PlayStop(id);
    } else {
        std::cerr << "bad arguments\n";
        return 1;
    }
    std::cout << "ret " << ret << std::endl;
    return ret == 0 ? 0 : 3;
}
