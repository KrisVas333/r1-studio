// R1 Studio blocks: definitions, toolbox and compiler (blocks → r1ctl steps).
// Colors per category, LEGO-SPIKE style: one color = one kind of thing.
export const COLORS = { events: "#F2A900", moves: "#8E44AD", arms: "#B2479B", hands: "#2F6FEB",
  voice: "#12A150", ai: "#D90429", control: "#E67E22", vision: "#0FA3B1" };

// ⚠️ ids from community sources for firmware 1.4.x: confirm with `r1_arm_action_example <iface> --list`
export const FACTORY_DANCES = [["💃 Dance 1", "601"], ["🕺 Dance 2", "602"], ["🎶 Dance 3", "603"],
  ["🌀 Twist", "604"], ["🥋 Kung fu", "607"], ["🐉 Jeet Kune Do", "608"]];
export const GESTURES = [["🤝 Handshake", "27"], ["🙌 High five", "18"], ["✨ Ultraman ray", "24"],
  ["🏆 Boxing win", "28"], ["😘 Blow kiss", "11"], ["⬇ Arms down (release)", "99"]];

// 13 arm joints, same order as r1_arm / CSV: L(sp sr sy e wr) R(sp sr sy e wr) waist_yaw head_pitch head_yaw
export const JOINTS = ["left_shoulder_pitch", "left_shoulder_roll", "left_shoulder_yaw", "left_elbow", "left_wrist_roll",
  "right_shoulder_pitch", "right_shoulder_roll", "right_shoulder_yaw", "right_elbow", "right_wrist_roll",
  "waist_yaw", "head_pitch", "head_yaw"];
export const JOINT_LABELS = ["L shoulder ↕", "L shoulder ↔", "L shoulder ⟳", "L elbow", "L wrist ⟳",
  "R shoulder ↕", "R shoulder ↔", "R shoulder ⟳", "R elbow", "R wrist ⟳", "Waist turn", "Head nod", "Head turn"];
// Poses checked on Unitree's R1 model (limits + no arm-body contact) in r1sim
const P = (o) => { const q = Array(13).fill(0); for (const [k, v] of Object.entries(o)) q[k] = v; return q; };
export const ARM_POSES = {
  rest: { label: "😐 rest", q: P({}) },
  right_up: { label: "🙋 right hand up", q: P({ 5: -1.5 }) },
  left_up: { label: "🙋 left hand up", q: P({ 0: -1.5 }) },
  both_up: { label: "🙌 both hands up", q: P({ 0: -1.5, 5: -1.5 }) },
  arms_out: { label: "🤸 arms out", q: P({ 1: 1.3, 3: 1.35, 6: -1.3, 8: 1.35 }) },
  wave_ready: { label: "👋 ready to wave", q: P({ 5: -1.4, 6: -0.7 }) },
  point: { label: "👉 point forward", q: P({ 5: -1.4, 8: 1.35 }) },
  look_left: { label: "👀 look left", q: P({ 10: 0.5, 12: 0.5 }) },
  look_right: { label: "👀 look right", q: P({ 10: -0.5, 12: -0.5 }) },
};
const SPEED = { slow: 0.4, normal: 0.8, fast: 1.4 };
export const SIGNS = [["✊ a fist", "Closed_Fist"], ["✋ an open hand", "Open_Palm"], ["✌️ peace", "Victory"],
  ["👍 thumbs up", "Thumb_Up"], ["☝️ a pointing finger", "Pointing_Up"], ["🤟 love sign", "ILoveYou"],
  ["🙂 a person", "person"]];

export const OBJECTS = ["person", "sports ball", "cup", "bottle", "teddy bear", "book", "cell phone", "banana", "apple", "orange", "chair", "dog", "cat", "backpack"];
export const COLOR_NAMES = ["red", "orange", "yellow", "green", "blue", "purple"];
let LIB = { dances: {}, hands: {}, arm: [], personas: {} };
export function setLibrary(lib) { LIB = lib; }
const opt = (list, empty) => () => (list().length ? list() : [[empty, "__none"]]);
const handOptions = opt(() => Object.keys(LIB.hands).map((p) => [p.replace(/_/g, " "), p]), "no poses");
const armOptions = opt(() => LIB.arm.map((a) => [a.replace(/_/g, " "), a]), "no recordings");
const danceOptions = opt(() => Object.keys(LIB.dances).map((d) => [LIB.dances[d].title || d, d]), "no dances");
const side = () => [["right", "right"], ["left", "left"], ["both", "both"]];

const defs = [
  // EVENTS
  { type: "r1_start", message0: "when ▶ Run is clicked", nextStatement: null, colour: COLORS.events, hat: "cap",
    tooltip: "Your program starts here" },
  { type: "r1_when_sign", message0: "when I see %1", args0: [{ type: "field_dropdown", name: "SIGN", options: SIGNS }],
    nextStatement: null, colour: COLORS.events, tooltip: "Camera tab: robot reacts when it sees this" },
  { type: "r1_when_hear", message0: "when someone says %1", args0: [{ type: "field_input", name: "WORD", text: "hello" }],
    nextStatement: null, colour: COLORS.events, tooltip: "Words from the AI tab or microphone" },
  // VISION
  { type: "r1_when_object", message0: "when I see a %1", args0: [{ type: "field_dropdown", name: "OBJ", options: () => OBJECTS.map((o) => [o, o]) }],
    nextStatement: null, colour: COLORS.vision, tooltip: "Camera tab: object recognition" },
  { type: "r1_when_color", message0: "when I see the color %1", args0: [{ type: "field_dropdown", name: "C", options: () => COLOR_NAMES.map((c) => [c, c]) }],
    nextStatement: null, colour: COLORS.vision, tooltip: "Looks at the middle of the camera image" },
  { type: "r1_describe", message0: "🗣️ say what I see", previousStatement: null, nextStatement: null, colour: COLORS.vision },
  { type: "r1_copy_arms", message0: "🪞 copy my arms for %1 s", args0: [{ type: "field_number", name: "S", value: 10, min: 2, max: 60 }],
    previousStatement: null, nextStatement: null, colour: COLORS.vision, tooltip: "Body tracking. Slow on the real robot." },
  { type: "r1_follow", message0: "🚶 follow the person for %1 s (experimental)", args0: [{ type: "field_number", name: "S", value: 10, min: 2, max: 60 }],
    previousStatement: null, nextStatement: null, colour: COLORS.vision, tooltip: "Real robot walks slowly. Clear floor, adult on STOP." },
  // MOVES (factory)
  { type: "r1_dance", message0: "💃 factory dance %1", args0: [{ type: "field_dropdown", name: "ID", options: FACTORY_DANCES }],
    previousStatement: null, nextStatement: null, colour: COLORS.moves, tooltip: "Built into the robot. Needs space: 2 m!" },
  { type: "r1_gesture", message0: "👋 gesture %1", args0: [{ type: "field_dropdown", name: "ID", options: GESTURES }],
    previousStatement: null, nextStatement: null, colour: COLORS.moves, tooltip: "Built-in arm gesture" },
  { type: "r1_walk", message0: "🚶 walk %1 for %2 s", args0: [
      { type: "field_dropdown", name: "DIR", options: [["forward", "0.2 0 0"], ["backward", "-0.15 0 0"], ["turn left", "0 0 0.4"], ["turn right", "0 0 -0.4"], ["step left", "0 0.15 0"], ["step right", "0 -0.15 0"]] },
      { type: "field_number", name: "S", value: 2, min: 0.5, max: 5, precision: 0.5 }],
    previousStatement: null, nextStatement: null, colour: COLORS.moves, tooltip: "Slow walking. Clear floor only!" },
  { type: "r1_stance", message0: "🧍 %1", args0: [{ type: "field_dropdown", name: "CMD", options: [["stand up", "stand_up"], ["sit down", "sit"], ["squat", "squat"], ["stop walking", "stop_move"]] }],
    previousStatement: null, nextStatement: null, colour: COLORS.moves },
  // ARMS
  { type: "r1_arm_pose", message0: "💪 arms %1 speed %2", args0: [
      { type: "field_dropdown", name: "POSE", options: Object.entries(ARM_POSES).map(([k, v]) => [v.label, k]) },
      { type: "field_dropdown", name: "SPEED", options: [["normal", "normal"], ["slow", "slow"], ["fast", "fast"]] }],
    previousStatement: null, nextStatement: null, colour: COLORS.arms },
  { type: "r1_arm_move", message0: "🎞️ play arm move %1 speed %2", args0: [
      { type: "field_dropdown", name: "FILE", options: armOptions },
      { type: "field_dropdown", name: "SPEED", options: [["1×", "1"], ["½×", "0.5"], ["2×", "2"]] }],
    previousStatement: null, nextStatement: null, colour: COLORS.arms, tooltip: "Recorded by hand: r1ctl arm record <name>" },
  { type: "r1_pose_custom", message0: "💪 my pose %1 speed %2", args0: [{ type: "field_input", name: "NAME", text: "pose 1" },
      { type: "field_dropdown", name: "SPEED", options: [["normal", "normal"], ["slow", "slow"], ["fast", "fast"]] }],
    previousStatement: null, nextStatement: null, colour: COLORS.arms, tooltip: "Made in the Joints tab" },
  { type: "r1_joint", message0: "🎚️ turn %1 to %2 °", args0: [
      { type: "field_dropdown", name: "J", options: JOINT_LABELS.map((l, i) => [l, String(i)]) },
      { type: "field_number", name: "DEG", value: 0, min: -180, max: 180 }],
    previousStatement: null, nextStatement: null, colour: COLORS.arms, tooltip: "One joint. Limits are checked." },
  // HANDS
  { type: "r1_hand", message0: "✋ %1 hand %2", args0: [
      { type: "field_dropdown", name: "SIDE", options: side }, { type: "field_dropdown", name: "POSE", options: handOptions }],
    previousStatement: null, nextStatement: null, colour: COLORS.hands },
  { type: "r1_fingers", message0: "🖐️ %1 fingers %2 thumb %3 index %4 middle %5 ring %6 pinky %7 % bent", args0: [
      { type: "field_dropdown", name: "SIDE", options: side }, { type: "input_dummy" },
      { type: "field_number", name: "T", value: 0, min: 0, max: 100 }, { type: "field_number", name: "I", value: 0, min: 0, max: 100 },
      { type: "field_number", name: "M", value: 0, min: 0, max: 100 }, { type: "field_number", name: "R", value: 0, min: 0, max: 100 },
      { type: "field_number", name: "P", value: 0, min: 0, max: 100 }],
    previousStatement: null, nextStatement: null, colour: COLORS.hands, inputsInline: true },
  { type: "r1_mirror", message0: "🪞 %1 hand copies my hand for %2 s", args0: [
      { type: "field_dropdown", name: "SIDE", options: side }, { type: "field_number", name: "S", value: 10, min: 2, max: 60 }],
    previousStatement: null, nextStatement: null, colour: COLORS.hands, tooltip: "Camera tab must be on" },
  { type: "r1_grab", message0: "🤏 %1 hand grab %2", args0: [
      { type: "field_dropdown", name: "SIDE", options: side }, { type: "field_dropdown", name: "STR", options: [["gently", "0.5"], ["firmly", "0.75"]] }],
    previousStatement: null, nextStatement: null, colour: COLORS.hands, tooltip: "Soft, light things only. Never a person's hand." },
  { type: "r1_release", message0: "🖐️ %1 hand let go", args0: [{ type: "field_dropdown", name: "SIDE", options: side }],
    previousStatement: null, nextStatement: null, colour: COLORS.hands },
  // VOICE
  { type: "r1_say", message0: "🗣️ say %1 voice %2", args0: [{ type: "field_input", name: "TEXT", text: "Hello!" },
      { type: "field_dropdown", name: "VOICE", options: [["🤖 Kris robot voice", "eleven"], ["📢 R1 built-in (EN)", "robot"]] }],
    previousStatement: null, nextStatement: null, colour: COLORS.voice },
  { type: "r1_joke", message0: "😂 tell a random joke", previousStatement: null, nextStatement: null, colour: COLORS.voice },
  { type: "r1_led", message0: "💡 light %1", args0: [{ type: "field_dropdown", name: "C", options: [["🔵 blue", "0,120,255"], ["🟢 green", "0,200,80"], ["🔴 red", "255,0,40"], ["🟡 yellow", "255,190,0"], ["🟣 purple", "160,0,255"], ["⚫ off", "0,0,0"]] }],
    previousStatement: null, nextStatement: null, colour: COLORS.voice },
  // AI
  { type: "r1_ai_say", message0: "🧠 ask AI %1 and say the answer", args0: [{ type: "field_input", name: "TEXT", text: "Tell the kids one fun fact about robots" }],
    previousStatement: null, nextStatement: null, colour: COLORS.ai },
  { type: "r1_ai_do", message0: "🧠 AI picks a move for %1", args0: [{ type: "field_input", name: "TEXT", text: "show us something happy" }],
    previousStatement: null, nextStatement: null, colour: COLORS.ai, tooltip: "AI answers and may run one move from the persona's allowed list" },
  { type: "r1_ai_chat", message0: "🧠 talk with people for %1 turns", args0: [{ type: "field_number", name: "N", value: 3, min: 1, max: 10 }],
    previousStatement: null, nextStatement: null, colour: COLORS.ai, tooltip: "Opens the AI tab and waits for people to talk" },
  // CONTROL
  { type: "r1_wait", message0: "⏱️ wait %1 s", args0: [{ type: "field_number", name: "S", value: 1, min: 0, max: 60, precision: 0.1 }],
    previousStatement: null, nextStatement: null, colour: COLORS.control },
  { type: "r1_repeat", message0: "🔁 repeat %1 times %2 %3", args0: [{ type: "field_number", name: "N", value: 3, min: 1, max: 20, precision: 1 },
      { type: "input_dummy" }, { type: "input_statement", name: "DO" }],
    previousStatement: null, nextStatement: null, colour: COLORS.control },
  { type: "r1_together", message0: "⚡ do at the same time %1 %2", args0: [{ type: "input_dummy" }, { type: "input_statement", name: "DO" }],
    previousStatement: null, nextStatement: null, colour: COLORS.control, tooltip: "e.g. move arms while the hand changes" },
  { type: "r1_random", message0: "🎲 do ONE of these %1 %2", args0: [{ type: "input_dummy" }, { type: "input_statement", name: "DO" }],
    previousStatement: null, nextStatement: null, colour: COLORS.control },
  { type: "r1_play", message0: "📼 play saved program %1", args0: [{ type: "field_dropdown", name: "NAME", options: danceOptions }],
    previousStatement: null, nextStatement: null, colour: COLORS.control },
];

export function defineBlocks() {
  Blockly.defineBlocksWithJsonArray(defs.map(({ hat, ...d }) => d));
  for (const t of ["r1_start", "r1_when_sign", "r1_when_hear", "r1_when_object", "r1_when_color"]) {
    const b = Blockly.Blocks[t]; const init = b.init;
    b.init = function () { init.call(this); this.hat = "cap"; };
  }
}

const cat = (name, colour, types) => ({ kind: "category", name, colour,
  contents: types.map((t) => (typeof t === "string" ? { kind: "block", type: t } : t)) });
export const TOOLBOX = { kind: "categoryToolbox", contents: [
  cat("Events", COLORS.events, ["r1_start", "r1_when_sign", "r1_when_hear"]),
  cat("Moves", COLORS.moves, ["r1_dance", "r1_gesture", "r1_stance", "r1_walk"]),
  cat("Arms", COLORS.arms, ["r1_arm_pose", "r1_arm_move", "r1_joint", "r1_pose_custom"]),
  cat("Hands", COLORS.hands, ["r1_hand", "r1_fingers", "r1_mirror", "r1_grab", "r1_release"]),
  cat("Voice & light", COLORS.voice, ["r1_say", "r1_joke", "r1_led"]),
  cat("AI", COLORS.ai, ["r1_ai_say", "r1_ai_do", "r1_ai_chat"]),
  cat("Vision", COLORS.vision, ["r1_when_object", "r1_when_color", "r1_describe", "r1_copy_arms", "r1_follow"]),
  cat("Control", COLORS.control, ["r1_wait", "r1_repeat", "r1_together", "r1_random", "r1_play"]),
]};

const JOKES = ["Why did the robot go on holiday? It needed to recharge.",
  "What is a robot's favourite snack? Micro-chips.",
  "I tried to dance like a human. My elbows filed a complaint.",
  "Why was the robot tired? It had a hard drive."];

// ---- compiler: block → node {id, step} or container {id, kind, children}
function chain(block) { const out = []; while (block) { if (!block.isEnabled || block.isEnabled()) out.push(...node(block)); block = block.getNextBlock(); } return out; }
function inner(block, name) { return chain(block.getInputTargetBlock(name)); }
const L = (id, step) => [{ id, step }];

function node(b) {
  const f = (n) => b.getFieldValue(n), id = b.id;
  switch (b.type) {
    case "r1_dance": return L(id, { fsm: +f("ID") });
    case "r1_gesture": return L(id, { arm_preset: +f("ID") });
    case "r1_walk": return L(id, { loco: { cmd: "move", value: `"${f("DIR")}"`, seconds: +f("S") } });
    case "r1_stance": return L(id, { loco: f("CMD") });
    case "r1_arm_pose": return L(id, { arm_pose: { q: ARM_POSES[f("POSE")].q.slice(), max_vel: SPEED[f("SPEED")] } });
    case "r1_arm_move": return f("FILE") === "__none" ? [] : L(id, { arm_traj: { file: f("FILE"), speed: +f("SPEED") } });
    case "r1_pose_custom": { let q; try { q = JSON.parse(b.data || "null"); } catch (e) { q = null; }
      return Array.isArray(q) && q.length === 13 ? L(id, { arm_pose: { q, max_vel: SPEED[f("SPEED")] } }) : []; }
    case "r1_mirror": return [{ id, kind: "mirror", side: f("SIDE"), secs: +f("S") }];
    case "r1_joint": return L(id, { arm_joint: { j: +f("J"), rad: +f("DEG") * Math.PI / 180 } });
    case "r1_hand": return L(id, { hand: { side: f("SIDE"), pose: f("POSE") } });
    case "r1_fingers": { const t = +f("T") / 100; return L(id, { hand: { side: f("SIDE"), q: [t, t, +f("I") / 100, +f("M") / 100, +f("R") / 100, +f("P") / 100] } }); }
    case "r1_grab": return L(id, { grab: { side: f("SIDE"), strength: +f("STR") } });
    case "r1_release": return L(id, { release: { side: f("SIDE") } });
    case "r1_say": return L(id, { say: { text: f("TEXT"), voice: f("VOICE") } });
    case "r1_joke": return [{ id, kind: "random", children: JOKES.map((j) => ({ id, step: { say: j } })) }];
    case "r1_led": return L(id, { led: f("C").split(",").map(Number) });
    case "r1_ai_say": return L(id, { ai: { prompt: f("TEXT"), act: false } });
    case "r1_ai_do": return L(id, { ai: { prompt: f("TEXT"), act: true } });
    case "r1_ai_chat": return [{ id, kind: "chat", turns: +f("N") }];
    case "r1_wait": return L(id, { wait: +f("S") });
    case "r1_repeat": return [{ id, kind: "repeat", times: Math.max(1, Math.min(20, +f("N"))), children: inner(b, "DO") }];
    case "r1_together": return [{ id, kind: "parallel", children: inner(b, "DO") }];
    case "r1_random": return [{ id, kind: "random", children: inner(b, "DO") }];
    case "r1_describe": return [{ id, kind: "describe" }];
    case "r1_copy_arms": return [{ id, kind: "copyarms", secs: +f("S") }];
    case "r1_follow": return [{ id, kind: "follow", secs: +f("S") }];
    case "r1_play": return f("NAME") === "__none" ? [] : L(id, { dance: f("NAME") });
    default: return [];
  }
}

export function compile(ws) {
  const prog = { main: [], signs: {}, words: [] };
  for (const top of ws.getTopBlocks(true)) {
    if (top.type === "r1_start") prog.main.push(...chain(top.getNextBlock()));
    else if (top.type === "r1_when_sign") (prog.signs[top.getFieldValue("SIGN")] ||= []).push(...chain(top.getNextBlock()));
    else if (top.type === "r1_when_object") (prog.signs["obj:" + top.getFieldValue("OBJ")] ||= []).push(...chain(top.getNextBlock()));
    else if (top.type === "r1_when_color") (prog.signs["color:" + top.getFieldValue("C")] ||= []).push(...chain(top.getNextBlock()));
    else if (top.type === "r1_when_hear") prog.words.push({ word: top.getFieldValue("WORD").toLowerCase(), nodes: chain(top.getNextBlock()) });
  }
  return prog;
}

// nodes → plain r1ctl steps (for saving / the Code tab). arm_joint becomes a full arm_pose.
export function toSteps(nodes, pose = Array(13).fill(0)) {
  const out = [];
  for (const n of nodes) {
    if (n.step) {
      const [k, a] = Object.entries(n.step)[0];
      if (k === "arm_joint") { pose = pose.slice(); pose[a.j] = a.rad; out.push({ arm_pose: { q: pose.map((v) => +v.toFixed(3)), max_vel: 0.8 } }); continue; }
      if (k === "arm_pose") pose = a.q.slice();
      out.push(n.step);
    } else if (n.kind === "repeat") out.push({ repeat: { times: n.times, steps: toSteps(n.children, pose) } });
    else if (n.kind === "parallel") out.push({ parallel: toSteps(n.children, pose) });
    else if (n.kind === "random") out.push({ random: toSteps(n.children, pose) });
    else if (n.kind === "mirror" || n.kind === "copyarms" || n.kind === "follow") out.push({ wait: n.secs });
    else if (n.kind === "describe") out.push({ say: "(Studio only: says what the camera sees)" });
    else if (n.kind === "chat") out.push({ ai: { prompt: "Greet the audience and invite them to talk to you.", act: true } });
  }
  return out.filter((s) => !(Array.isArray(Object.values(s)[0]) && !Object.values(s)[0].length));
}
