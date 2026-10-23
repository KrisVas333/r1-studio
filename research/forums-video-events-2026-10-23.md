# R1 forums / video / events sweep — 2026-10-23

**Status:** PARTIAL (checklist + first findings saved; appended as sources checked)
**Scope:** Unitree R1 EDU Pro + BrainCo Revo2. Labels: ✅ R1-verified / 🟡 G1-only / ⚠️ unverified.
**Not repeated:** wiki/research/r1-capability-radar.md and r1-radar/2026-10-20-hands-ai-events.md (arm presets, audio API, xr_teleoperate, hand retrofit, G1 child-strike incident).

## TL;DR
- **No official R1 "upload your own dance" feature found** (search 2026-10-23: no R1 dance-upload, no 2026 R1 firmware notes). Custom moves = our SDK code or arm teach/playback. ⚠️ negative result from search only.
- **Training Mode in Unitree Explore App (custom movement sequences) is a G1 firmware release** 🟡, not shown for R1. https://robostore.com/blogs/news/unitree-launches-public-beta-of-its-app-store-for-g1-humanoid-robots
- **R1 Base is closed to developers; EDU variants list SDK/API** — confirm our unit is EDU Pro with SDK access. https://a.storyblok.com/f/298593/x/344bce2eee/rbtx_unitree_robotics_unitree_r1_base_technical_datasheet_en-1.pdf
- **R1 events: voice conversation, several dances, Kung Fu shown at a Hong Kong university session** ✅ (R1 named). https://lttc.eduhk.hk/news/lttc-hosts-hands-on-assembly-and-demonstration-session-for-unitree-r1-humanoid-robot/
- **Rental pricing numbers found are G1, not R1:** 8,000-15,000 CNY/day (~$1,115-2,091), Xinhua via search summary. 🟡 No R1 rental company found. https://www.notebookcheck.net/Humanoid-robot-for-consumers-Unitree-R1-launches-starting-at-US-5-900.1069005.0.html
- Safety: no cutting/blade use. Throw only soft objects, away from people. Kids behind line (R1 sheet says not near children).

## CHECKLIST — what Kris must have ready tomorrow
Source basis: prior radar gotchas + this sweep. Items marked ⚠️ = ask Droni, answer unknown.

### Accounts / logins
- [ ] Unitree Explore app installed on phone + account logged in (the account bound to the robot). Screenshot every menu (radar test #1).
- [ ] Phone Bluetooth + Wi-Fi on; robot paired BEFORE the event, not at the venue.
- [ ] Robot SSH/PC2 credentials: ⚠️ ask Droni whether given (default creds not verified; do not guess).
- [ ] Wi-Fi: venue network is unreliable. Bring own pocket router; note SSID/password. SDK services bind to wired port only; router must bridge 192.168.123.x (radar gotcha).
- [ ] API keys charged and in env: ElevenLabs (LT voice; test v3/v4 LT), LLM key (Claude/OpenAI), STT (Scribe/Whisper). Keys on laptop only, not in chat/git.
- [ ] Offline fallback: pre-rendered LT audio WAVs (16 kHz mono) for greeting/jokes/goodbye in case internet drops.

### Hardware
- [ ] Laptop (Ubuntu or Mac w/ SDK built) with `unitree_sdk2` compiled BEFORE the event.
- [ ] USB-C/USB-A to Ethernet adapter + 2 Ethernet cables (laptop to robot, 192.168.123.x static IP).
- [ ] Pocket router + power strip + extension cable.
- [ ] Gantry/hoist or stand for first hand/arm tests (Weston page advises support for first motion).
- [ ] Spare battery(ies) + charger: ⚠️ price/lead time unknown, ask Droni. Plan runtime breaks.
- [ ] Remote controller charged (E-stop = hold L2+B, radar gotcha). One person holds it at all times.
- [ ] Soft props: foam balls, small plush, paper cups. Nothing heavy (<500 g Dex3 test; Revo2 grip 50 N can hurt fingers). No handshakes with closed fingers on a person.
- [ ] Barrier/tape line (2 m), spotter, flat non-slip floor, space for dances.
- [ ] Speaker/mic option: external Bluetooth speaker if robot speaker too quiet at venue ⚠️ untested.
- [ ] Phone/camera on tripod to film (content rule).

### Ask Droni (reseller) before tomorrow
1. Exact SKU: Dex3-1 or Revo2 (U3-U6)? Who installed hands?
2. Current firmware/app version + release notes; any OTA pending (do NOT update night before).
3. Remote button map for dances (601-603 etc.) and AI mode; wake word; supported chat languages; whether cloud is China-hosted.
4. Where arm "teach" recording lives (app or SDK only).
5. Is SSH/PC2 access allowed; SDK access confirmed (EDU)?
6. Written OK for audiences/kids behind a line; payload on head/arms.
7. Spare battery, warranty on fall damage, security patch status (BLE issue patched?).
8. Wi-Fi/Bluetooth range and what happens when the app drops.

### Day-of rules
- One voice/motion program at a time (else no sound). Error 3104 = unreachable; 7404 = not in built-in controller.
- Never double-click Start during a dance (zero torque, robot goes limp).
- SDK arm control while walking = lockout; do arms while standing.
- NO blades/cutting. Throwing: soft only, away from people, adult operator, tested on gantry first. ⚠️ throwing is not a documented R1 feature; treat as arm-preset/own-code experiment, not promised.
- Test the whole show end to end at home once; event = replay, not experiment.

## SOURCES LOG (appended)
| # | Source | Finding | Label | Date |
|---|---|---|---|---|
| 1 | https://www.notebookcheck.net/Humanoid-robot-for-consumers-Unitree-R1-launches-starting-at-US-5-900.1069005.0.html | R1 positioned for entertainment, conversation, dancing at events; no functional hands on base | ✅ | 2026 (search summary) |
| 2 | https://lttc.eduhk.hk/news/lttc-hosts-hands-on-assembly-and-demonstration-session-for-unitree-r1-humanoid-robot/ | EdUHK session: R1 voice conversation + dance routines + Kung Fu | ✅ | date ⚠️ |
| 3 | https://robostore.com/blogs/news/unitree-launches-public-beta-of-its-app-store-for-g1-humanoid-robots | App Store beta + Training Mode are G1 | 🟡 | date ⚠️ |
| 4 | https://unitree.com/R1 | OTA upgrade advertised; contents not listed | ⚠️ | 2026 |

## Event-robotics practice (all G1, no R1 rental firm found 🟡)
| Who | How they run it | Price | Source |
|---|---|---|---|
| RobotShop CA (G1 EDU U2 rental) | Their staff set up, operate, tear down; pre-programmed routines for live audience; client needs no robotics skill | on listing ⚠️ not captured; lead 6-8 wks | https://ca.robotshop.com/products/unitree-g1-edu-u2-humanoid-robot-rental-w-on-site-service |
| TVC Robotics & Events (US, claims Unitree distributor) | Setup to live performance; corporate/education/private | ⚠️ not stated | https://miami.makerfaire.com/maker/entry/1798/ |
| AgiBot Qingtian Rent (CN) | 50 cities, 600 providers, 1000+ robots; Unitree U2 ~$690/day incl. support+delivery | ~$690/day | https://www.chinadaily.com.cn/a/202504/03/WS67edf643a3104d9fd381d769.html |
| CN market reports | 5,000-15,000 CNY/day ($690-1,380), usually with operator; beware high deposit with no operator | as left | https://www.chinadaily.com.cn/a/202503/20/WS67db6a4ba310c240449dbce0.html |
Pattern: **operator + pre-programmed routines, not live improvisation.** No public safety/insurance terms found ⚠️. Takeaway for Kris: sell/price "robot + operator" as one package; benchmark ~$700-1,400/day (G1, not R1).

## Negative results (2026-10-23 searches)
- No R1 rock-paper-scissors, custom-ChatGPT-voice, throwing, or custom-dance-upload videos/posts surfaced via search ⚠️ (Reddit/YouTube/Bilibili/X not indexed by search tool; direct fetch not attempted yet).
- No BrainCo Revo2 RPS demo on R1; Revo2 listings are for Unitree **H2** (RobotShop). 🟡 https://www.robotshop.com/products/revo2-basic-hand-for-unitree-h2-right . BrainCo launch Sep 2025: https://pr.enewspf.com/article/BrainCo-Launches-Revo2-Hand-for-Humanoid-Robotics/68c95ca6b83f4e9fe2c52880
- Implication: RPS = own build: camera (hand-gesture classifier on laptop, e.g. MediaPipe ⚠️ not R1-verified) + Revo2 finger commands via brainco_hand_service (topics in prior radar). Needs hands installed; confirm with Droni.

## Voice / AI stacks (2026-10-23)
- Unitree R1 page: "Large Multimodal Model for voice and images", 4-mic array + speaker; **no languages listed**; OTA advertised; **secondary development: NO on R1 Air/R1, YES on R1 EDU**; dexterous hand optional on EDU only. ✅ https://www.unitree.com/R1 (fetched 2026-10-23)
- Built-in AI-mode languages and wake word: **not confirmed anywhere** ⚠️ (prior radar: TTS CN/EN). Ask Droni.
- Closest working pattern: Unitree **Go2** + OpenAI Realtime API voice agent on onboard Jetson 🟡 https://wso2.com/library/blogs/how-we-gave-life-to-an-ai-agent-with-unitree-go2-robot/
- ElevenLabs Agents = cascaded ASR + LLM + ElevenLabs TTS, OpenAI-Realtime-compatible flow ⚠️ not R1-tested. https://elevenlabs.io/docs/hi/eleven-agents/guides/openai-realtime-compatibility.md . Wire to R1 via SDK PlayStream (16 kHz WAV) per prior radar. Personality = system prompt (name, jokes, short LT answers, refuse unsafe asks).
- Our memory: ElevenLabs agents not for under-18 users; kids' voices through a cloud agent need consent: keep kid Q&A scripted/moderated at events ⚠️.

## Blocked / not reachable
- reddit.com: WebFetch blocked. Bilibili, X, Discord, Unitree support docs: not attempted/JS-rendered (prior radar says unreachable). YouTube not searchable by tool.
- ⚠️ Gap: Kris should skim YouTube "Unitree R1" results himself for RPS/dance/throwing videos; none verified here.

## BUILD PLAN for tomorrow (smallest version, ordered)
1. Factory dances 601-603 via remote + arm presets by ID (prior radar) = safe event core. ✅
2. LT greeting/jokes: pre-rendered ElevenLabs WAVs through PlayStream + LED. ✅ parts
3. Live AI chat: laptop loop (mic -> STT -> LLM -> ElevenLabs -> PlayStream); build only after 1-2 work; fallback = pre-rendered jokes.
4. Hand games / grasp / throw: ONLY if hands installed and tested on gantry; otherwise SKIP tomorrow. RPS = own vision build, unproven ⚠️.
5. Custom full-body dance: SKIP (no R1 route found); custom = arm teach/playback only.
6. Event control: one laptop button panel (script launching presets) + handheld remote + E-stop person. Unofficial WebRTC panel may break after OTA ⚠️.

## Updated TL;DR verdict
Tomorrow is realistic for: factory dances, arm presets, LT voice via audio API, scripted jokes. Not proven on R1: RPS, throwing, custom dance upload, full AI agent loop. This sweep (search-only, Reddit/Bilibili blocked) added little new beyond: EDU-only SDK gating, rental-show pattern (operator + scripted), checklist.
