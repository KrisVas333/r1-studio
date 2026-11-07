// R1 Studio — blocks, 3D robot, camera, AI and the live robot in one page.
import { defineBlocks, TOOLBOX, compile, toSteps, setLibrary, ARM_POSES, JOINTS, JOINT_LABELS, FACTORY_DANCES, GESTURES } from "./blocks.js";
import { Robot3D } from "./robot3d.js";
import { Vision } from "./vision.js";
import { t, tf, LANG, applyDom, langSwitch, moveTitle, catLabel, srv } from "./i18n.js";
applyDom();
const SPEECH = LANG === "lt" ? "Lithuanian" : "English";  // browser voice + mic language in the simulator

const $ = (id) => document.getElementById(id);
const api = async (path, body) => {
  const r = await fetch(path, body ? { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) } : {});
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(j.error || r.statusText);
  return j;
};
const sleep = (ms, signal) => new Promise((res) => { const t = setTimeout(res, ms); signal && signal.addEventListener("abort", () => { clearTimeout(t); res(); }); });

let LIB = { dances: {}, hands: {}, arm: [], personas: {} }, STATUS = {}, live = false, run = null, chatWaiters = [];
const armCache = {};

// ---------------------------------------------------------------- UI helpers
function modal(title, html, { ok = t("ok"), input = null } = {}) {
  return new Promise((resolve) => {
    $("modalTitle").textContent = title;
    $("modalBody").innerHTML = html + (input !== null ? `<input id="modalInput" value="${input}">` : "");
    $("modalYes").textContent = ok; $("modal").classList.remove("hidden");
    const inp = $("modalInput"); if (inp) { inp.focus(); inp.select(); }
    const done = (v) => { $("modal").classList.add("hidden"); $("modalYes").onclick = $("modalNo").onclick = null; resolve(v); };
    $("modalYes").onclick = () => done(inp ? inp.value : true);
    $("modalNo").onclick = () => done(null);
    if (inp) inp.onkeydown = (e) => { if (e.key === "Enter") done(inp.value); };
  });
}
function logLine(s) { const el = $("log"); el.textContent = (el.textContent + s + "\n").split("\n").slice(-300).join("\n"); el.scrollTop = 1e9; }
function status(s) { $("chipStatus").textContent = s; }
function bubble(text) { const b = $("bubble"); if (!text) return b.classList.add("hidden"); b.textContent = text; b.classList.remove("hidden"); }
function banner(text) { const b = $("banner"); if (!text) return b.classList.add("hidden"); b.textContent = text; b.classList.remove("hidden"); }

let audio = null;
async function speak(text, lang, signal, voice = "eleven") {
  // Simulator voice: Kris robot voice (ElevenLabs + robot effect, via server) or the browser's. On the robot the R1 speaks itself.
  if ($("chatSpeak").checked && STATUS.eleven && voice !== "robot") {
    try {
      bubble(text);
      audio = new Audio("/api/tts?text=" + encodeURIComponent(text));
      await new Promise((res, rej) => { audio.onended = res; audio.onerror = rej; audio.play().catch(rej);
        signal && signal.addEventListener("abort", () => { audio.pause(); res(); }); });
      setTimeout(() => bubble(""), 300); return;
    } catch (e) { logLine(t("log.voicefb")); }
  }
  return new Promise((resolve) => {
    bubble(text);
    const end = () => { setTimeout(() => bubble(""), 400); resolve(); };
    if (!$("chatSpeak").checked || !window.speechSynthesis) return sleep(Math.max(1200, text.length * 60), signal).then(end);
    const u = new SpeechSynthesisUtterance(text);
    u.lang = /lith/i.test(lang || "") ? "lt-LT" : "en-US"; u.rate = 1.0; u.pitch = 0.6;
    u.onend = end; u.onerror = end; speechSynthesis.cancel(); speechSynthesis.speak(u);
    signal && signal.addEventListener("abort", () => { speechSynthesis.cancel(); end(); });
  });
}

// ---------------------------------------------------------------- Blockly
defineBlocks();
const ws = Blockly.inject("blockly", {
  toolbox: TOOLBOX, renderer: "zelos", grid: { spacing: 24, length: 3, colour: "#e8e8e3", snap: true },
  zoom: { controls: true, wheel: true, startScale: 0.9, maxScale: 2, minScale: 0.4 }, trashcan: true, move: { scrollbars: true, drag: true, wheel: false },
  theme: Blockly.Theme.defineTheme("r1", { base: Blockly.Themes.Classic, fontStyle: { family: "Inter, sans-serif", weight: "600", size: 13 },
    componentStyles: { workspaceBackgroundColour: "#FBFBF9", toolboxBackgroundColour: "#FFFFFF", flyoutBackgroundColour: "#F3F3EF", flyoutOpacity: 1 } }),
});
ws.addChangeListener(Blockly.Events.disableOrphans);
ws.addChangeListener((e) => { if (!e.isUiEvent) { refreshCode(); try { localStorage.setItem("r1studio", JSON.stringify(Blockly.serialization.workspaces.save(ws))); } catch (x) { /* private mode */ } } });

function build(spec) {
  // spec: [{t, f:{field:value}, data, do:[...]}] → a connected chain, returns first block
  let first = null, prev = null;
  for (const s of spec) {
    const b = ws.newBlock(s.t);
    for (const [k, v] of Object.entries(s.f || {})) b.setFieldValue(String(v), k);
    if (s.data) b.data = s.data;
    b.initSvg(); b.render();
    if (s.do) { const c = build(s.do); if (c) b.getInput("DO").connection.connect(c.previousConnection); }
    if (prev) prev.nextConnection.connect(b.previousConnection); else first = b;
    prev = b;
  }
  return first;
}
function place(spec, x, y) { const b = build(spec); b.moveBy(x, y); return b; }

const SAYV = LANG === "lt" ? "eleven" : "robot";  // the robot's built-in voice speaks English only
const EXAMPLES = {
  [t("ex.hello")]: () => place([{ t: "r1_start" }, { t: "r1_led", f: { C: "0,120,255" } }, { t: "r1_say", f: { TEXT: t("exs.hello1"), VOICE: SAYV } },
    { t: "r1_together", do: [{ t: "r1_arm_move", f: { FILE: "wave_demo" } }, { t: "r1_hand", f: { SIDE: "right", POSE: "open" } }] },
    { t: "r1_hand", f: { SIDE: "right", POSE: "thumbs_up" } }, { t: "r1_say", f: { TEXT: t("exs.hello2"), VOICE: SAYV } }, { t: "r1_arm_pose", f: { POSE: "rest" } }], 40, 40),
  [t("ex.rps")]: () => {
    place([{ t: "r1_start" }, { t: "r1_say", f: { TEXT: t("exs.rps0") } }, { t: "r1_arm_pose", f: { POSE: "right_up" } }, { t: "r1_hand", f: { SIDE: "right", POSE: "fist" } }], 40, 30);
    place([{ t: "r1_when_sign", f: { SIGN: "Closed_Fist" } }, { t: "r1_hand", f: { SIDE: "right", POSE: "paper" } }, { t: "r1_say", f: { TEXT: t("exs.rps1") } }], 40, 230);
    place([{ t: "r1_when_sign", f: { SIGN: "Open_Palm" } }, { t: "r1_hand", f: { SIDE: "right", POSE: "scissors" } }, { t: "r1_say", f: { TEXT: t("exs.rps2") } }], 40, 380);
    place([{ t: "r1_when_sign", f: { SIGN: "Victory" } }, { t: "r1_hand", f: { SIDE: "right", POSE: "rock" } }, { t: "r1_say", f: { TEXT: t("exs.rps3") } }], 40, 530);
  },
  [t("ex.aihost")]: () => place([{ t: "r1_start" }, { t: "r1_led", f: { C: "160,0,255" } }, { t: "r1_say", f: { TEXT: t("exs.ai1") } },
    { t: "r1_ai_chat", f: { N: 5 } }, { t: "r1_say", f: { TEXT: t("exs.ai2") } }], 40, 40),
  [t("ex.party")]: () => place([{ t: "r1_start" }, { t: "r1_together", do: [{ t: "r1_dance", f: { ID: "601" } }, { t: "r1_led", f: { C: "160,0,255" } }] },
    { t: "r1_repeat", f: { N: 3 }, do: [{ t: "r1_hand", f: { SIDE: "both", POSE: "rock_on" } }, { t: "r1_wait", f: { S: 0.5 } }, { t: "r1_hand", f: { SIDE: "both", POSE: "open" } }, { t: "r1_wait", f: { S: 0.5 } }] },
    { t: "r1_joke" }], 40, 40),
  [t("ex.count")]: () => place([{ t: "r1_start" }, { t: "r1_arm_pose", f: { POSE: "right_up" } }, { t: "r1_hand", f: { SIDE: "right", POSE: "fist" } },
    ...["one", "two", "three", "four", "five"].flatMap((p, i) => [{ t: "r1_hand", f: { SIDE: "right", POSE: p } }, { t: "r1_say", f: { TEXT: String(i + 1) } }]),
    { t: "r1_arm_pose", f: { POSE: "rest" } }], 40, 40),
  [t("ex.mirror")]: () => place([{ t: "r1_start" }, { t: "r1_say", f: { TEXT: t("exs.mirror") } }, { t: "r1_arm_pose", f: { POSE: "right_up" } },
    { t: "r1_mirror", f: { SIDE: "right", S: 15 } }, { t: "r1_arm_pose", f: { POSE: "rest" } }], 40, 40),
  [t("ex.aipicks")]: () => place([{ t: "r1_start" }, { t: "r1_ai_do", f: { TEXT: t("exs.aipick") } }], 40, 40),
};
function loadExample(name) { ws.clear(); EXAMPLES[name](); ws.scrollCenter(); $("projectName").value = name.replace(/[^a-z0-9]+/gi, "_").replace(/^_|_$/g, "").toLowerCase(); }

// ---------------------------------------------------------------- code tab
function yaml(v, ind = "") {
  if (Array.isArray(v)) return v.length && typeof v[0] === "object" ? v.map((x) => `\n${ind}- ` + yaml(x, ind + "  ").trimStart()).join("") : JSON.stringify(v);
  if (v && typeof v === "object") return Object.entries(v).map(([k, x]) => `\n${ind}${k}: ` + (typeof x === "object" ? yaml(x, ind + "  ") : JSON.stringify(x))).join("");
  return JSON.stringify(v);
}
function refreshCode() {
  const p = compile(ws);
  let s = "kind: dance\ntitle: " + JSON.stringify($("projectName").value) + "\nsteps:" + yaml(toSteps(p.main), "  ");
  if (Object.keys(p.signs).length || p.words.length) s += "\n\n" + t("code.triggers");
  $("code").textContent = s;
}

// ---------------------------------------------------------------- runtime
async function armRows(name) { return armCache[name] || (armCache[name] = await api("/api/arm/" + name)); }

function stepsToNodes(steps) {
  return steps.map((s) => {
    const [k, a] = Object.entries(s)[0];
    if (k === "repeat") return { kind: "repeat", times: a.times, children: stepsToNodes(a.steps) };
    if (k === "parallel" || k === "random") return { kind: k, children: stepsToNodes(a) };
    return { step: s };
  });
}

async function liveStep(step) {
  if (!live) return null;
  const r = await api("/api/step", { step, live: true });
  return r.ai;
}

async function exec(nodes, sig) {
  for (const n of nodes) {
    if (sig.aborted) return;
    if (n.id) ws.highlightBlock(n.id);
    if (n.kind === "repeat") { for (let i = 0; i < n.times && !sig.aborted; i++) await exec(n.children, sig); continue; }
    if (n.kind === "parallel") { await Promise.all(n.children.map((c) => exec([c], sig))); continue; }
    if (n.kind === "random") { if (n.children.length) await exec([n.children[Math.floor(Math.random() * n.children.length)]], sig); continue; }
    if (n.kind === "chat") { await chatTurns(n.turns, sig); continue; }
    if (n.kind === "mirror") { await mirror(n.side, n.secs, sig); continue; }
    if (n.kind === "describe") { await runStep({ say: { text: vision.source === "off" ? t("exs.camoff") : vision.describe(), voice: "eleven" } }, sig); continue; }
    if (n.kind === "copyarms") { await copyArms(n.secs, sig); continue; }
    if (n.kind === "follow") { await follow(n.secs, sig); continue; }
    await runStep(n.step, sig);
  }
}

async function runStep(step, sig) {
  const [k, a] = Object.entries(step)[0];
  logLine("▶ " + k + " " + (typeof a === "object" ? JSON.stringify(a) : a));
  const R = robot;
  switch (k) {
    case "fsm": banner(t("bn.factory", { a })); await Promise.all([liveStep(step), R.sway(6000, sig)]); banner(""); return;
    case "arm_preset": banner(t("bn.gesture", { a })); await Promise.all([liveStep(step), R.sway(2500, sig)]); banner(""); return;
    case "loco": { const c = typeof a === "object" ? a.cmd : a; banner(`🚶 ${c}${a.seconds ? " " + a.seconds + " s" : ""}`);
      await Promise.all([liveStep(step), sleep((a.seconds || 1) * 1000, sig)]); banner(""); return; }
    case "arm_pose": await Promise.all([liveStep(step), R.moveTo(a.q, a.max_vel || 0.8, sig)]); return;
    case "arm_joint": { const q = R.q.slice(); q[a.j] = R.clampJoint(a.j, a.rad);
      await Promise.all([liveStep({ arm_pose: { q, max_vel: 0.8 } }), R.moveTo(q, 0.8, sig)]); return; }
    case "arm_traj": await Promise.all([liveStep(step), R.playTraj(await armRows(a.file), a.speed || 1, sig)]); return;
    case "hand": case "grab": case "release": {
      const q = k === "grab" ? Array(6).fill(a.strength || 0.6) : k === "release" ? Array(6).fill(0) : a.q || LIB.hands[a.pose];
      if (!q) throw new Error(t("m.unknownhand", { p: a.pose }));
      await Promise.all([liveStep(step), R.hand(a.side || "right", q, a.ms || (k === "grab" ? 1500 : 600), sig)]); return; }
    case "say": { const t = typeof a === "string" ? a : a.text; const v = typeof a === "string" ? "robot" : a.voice;
      if (live) { bubble(t); await liveStep(step); await sleep(Math.max(800, t.length * 55), sig); bubble(""); } else await speak(t, SPEECH, sig, v); return; }
    case "led": $("chipMode").style.background = `rgb(${a.join(",")})`; await liveStep(step); return;
    case "wait": await sleep(a * 1000, sig); return;
    case "dance": { const d = LIB.dances[a]; if (!d) throw new Error(t("m.noprog", { p: a })); await exec(stepsToNodes(d.steps), sig); return; }
    case "ai": return aiStep(a, sig);
    default: await liveStep(step);
  }
}

async function aiStep(a, sig) {
  status(t("st.thinking"));
  const persona = LIB.personas[a.persona || "host"] || { commands: {} };
  let out;
  if (live) { out = await liveStep({ ai: { ...a, act: false, voice: "eleven" } }) || {}; }
  else out = await api("/api/ai", { text: a.prompt, persona: a.persona || "host", language: $("aiLang").value });
  status(t("st.running"));
  if (!live && out.reply) await speak(out.reply, $("aiLang").value, sig);
  else if (out.reply) { bubble(out.reply); await sleep(Math.max(1500, out.reply.length * 55), sig); bubble(""); }
  if (a.act !== false && out.command && persona.commands[out.command]) await runCommand(persona, out.command, sig);
}

async function runCommand(persona, cmd, sig) {
  const todo = persona.commands[cmd];
  logLine(t("ai.chose", { c: cmd }));
  await exec(stepsToNodes(typeof todo === "string" ? [{ dance: todo }] : todo), sig);
}

async function mirror(side, secs, sig) {
  if (vision.source === "off") { await modal(t("m.camoff.t"), t("m.camoff.b")); return; }
  const end = performance.now() + secs * 1000; let lastLive = 0;
  while (performance.now() < end && !sig.aborted) {
    const q = vision.fingerCurl();
    if (q) {
      robot.hand(side, q, 120);
      if (live && performance.now() - lastLive > 350) { lastLive = performance.now(); liveStep({ hand: { side, q: q.map((v) => +v.toFixed(2)), ms: 300 } }).catch(() => {}); }
    }
    await sleep(120, sig);
  }
}

async function copyArms(secs, sig) {
  if (vision.source === "off") { await modal(t("m.camoff.t"), t("m.camoff.b")); return; }
  vision.want.pose = true; $("vPose").checked = true;
  const end = performance.now() + secs * 1000; let lastLive = 0;
  while (performance.now() < end && !sig.aborted) {
    const q = vision.armTargets();
    if (q) {
      robot.moveTo(q, 1.0, sig);
      if (live && performance.now() - lastLive > 600) { lastLive = performance.now(); liveStep({ arm_pose: { q: robot.q.map((v) => +v.toFixed(3)), max_vel: 0.6 } }).catch(() => {}); }
    }
    await sleep(300, sig);
  }
}

async function follow(secs, sig) {
  if (vision.source === "off") { await modal(t("m.camoff.t"), t("m.camoff.b")); return; }
  vision.want.objects = true; $("vObjects").checked = true;
  banner(live ? t("bn.follow.live") : t("bn.follow.sim"));
  const end = performance.now() + secs * 1000;
  try {
    while (performance.now() < end && !sig.aborted) {
      const c = vision.followCommand();
      if (c) {
        robot.drive(c.vx, 0, c.wz, 0.5);
        if (live && (c.vx || c.wz)) await liveStep({ loco: { cmd: "move", value: `"${c.vx.toFixed(2)} 0 ${c.wz.toFixed(2)}"`, seconds: 0.5 } }).catch(() => {});
      }
      await sleep(500, sig);
    }
  } finally {
    banner("");
    if (live) await liveStep({ loco: "stop_move" }).catch(() => {});
  }
}

async function start(nodes, label) {
  if (run) return;
  if (live && !(await liveGate())) return;
  run = new AbortController();
  status(label || t("st.running")); $("btnRun").disabled = true;
  try { await exec(nodes, run.signal); }
  catch (e) { logLine("❌ " + e.message); await modal(t("m.stopped"), `<p>${srv(e.message)}</p>`); }
  finally {
    ws.highlightBlock(null); banner(""); bubble("");
    if (live) api("/api/end", {}).catch(() => {});
    run = null; status(t("st.ready")); $("btnRun").disabled = false;
  }
}
async function stopAll() {
  if (run) run.abort();
  speechSynthesis && speechSynthesis.cancel(); if (audio) audio.pause();
  if (live) await api("/api/stop", {}).catch(() => {});
  robot.hand("both", Array(6).fill(0), 800); status(t("st.stopped"));
}

// ---------------------------------------------------------------- live mode
let liveConfirmed = false;
async function liveGate() {
  if (!STATUS.live_allowed) {
    await modal(t("m.simonly.t"), t("m.simonly.b"));
    setMode(false); return false;
  }
  if (liveConfirmed) return true;
  const ok = await modal(t("m.real.t"), t("m.real.b"), { ok: t("start"), input: "" });
  liveConfirmed = (ok || "").trim().toUpperCase() === "GO";
  if (!liveConfirmed) setMode(false);
  return liveConfirmed;
}
function setMode(isLive) {
  live = isLive;
  $("modeSim").classList.toggle("on", !live); $("modeLive").classList.toggle("on", live);
  $("chipMode").textContent = live ? t("chip.live") : t("chip.sim"); $("chipMode").classList.toggle("live", live);
  $("chipMode").style.background = "";
}

// ---------------------------------------------------------------- AI chat
const history = [];
function addMsg(who, text, cmd) {
  const d = document.createElement("div"); d.className = "msg " + who; d.textContent = text;
  if (cmd) { const c = document.createElement("div"); c.className = "cmd"; c.textContent = "▶ " + cmd; d.appendChild(c); }
  $("chat").appendChild(d); $("chat").scrollTop = 1e9;
}
async function chat(text) {
  if (!text.trim()) return;
  addMsg("me", text);
  // "when someone says…" blocks
  const prog = compile(ws);
  const hit = prog.words.find((w) => text.toLowerCase().includes(w.word));
  if (hit && !run) { start(hit.nodes, t("st.heard", { w: hit.word })); return; }
  const persona = $("persona").value || "host";
  if ($("operator").checked) {   // a human speaks through the robot: no AI
    const sig0 = (run && run.signal) || new AbortController().signal;
    if (live) await liveStep({ say: { text, voice: "eleven" } }).catch((e) => logLine("❌ " + e.message)); else await speak(text, SPEECH, sig0);
    return;
  }
  status(t("st.thinking"));
  const out = await api("/api/ai", { text, persona, history: history.slice(-10), language: $("aiLang").value }).catch((e) => ({ reply: "⚠️ " + srv(e.message) }));
  status(run ? t("st.running") : t("st.ready"));
  history.push({ role: "user", content: text }, { role: "assistant", content: JSON.stringify(out) });
  addMsg("bot", out.reply + (out.mock ? t("ai.mock") : ""), [out.emotion && "😶 " + moveTitle(out.emotion, out.emotion), out.command].filter(Boolean).join(" · "));
  const sig = (run && run.signal) || new AbortController().signal;
  const emo = $("autoEmo").checked && out.emotion && LIB.dances[out.emotion] ? out.emotion : null;
  if (live) {
    if (out.reply) await liveStep(emo ? { parallel: [{ say: { text: out.reply, voice: "eleven" } }, { dance: emo }] } : { say: { text: out.reply, voice: "eleven" } }).catch((e) => logLine("❌ " + e.message));
  } else if (out.reply) {
    await Promise.all([speak(out.reply, $("aiLang").value, sig), emo ? exec(stepsToNodes([{ dance: emo }]), sig) : null]);
  }
  const p = LIB.personas[persona];
  if ($("chatAct").checked && out.command && p && p.commands[out.command]) {
    if (run) await runCommand(p, out.command, run.signal); else await start(stepsToNodes(typeof p.commands[out.command] === "string" ? [{ dance: p.commands[out.command] }] : p.commands[out.command]), t("st.ai", { c: out.command }));
  }
  chatWaiters.forEach((w) => w()); chatWaiters = [];
}
function chatTurns(n, sig) {
  showTab("ai"); $("chatInput").focus();
  return new Promise(async (resolve) => {
    sig.addEventListener("abort", resolve);
    for (let i = 0; i < n && !sig.aborted; i++) { status(t("st.listening", { i: i + 1, n })); await new Promise((r) => chatWaiters.push(r)); }
    resolve();
  });
}
let ptt = null;
async function pttStart() {
  if (ptt) return;
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
    const ctx = new AudioContext({ sampleRate: 16000 });
    const src = ctx.createMediaStreamSource(stream), proc = ctx.createScriptProcessor(4096, 1, 1), chunks = [];
    proc.onaudioprocess = (e) => chunks.push(new Float32Array(e.inputBuffer.getChannelData(0)));
    src.connect(proc); proc.connect(ctx.destination);
    ptt = { stream, ctx, proc, chunks };
    $("pttBtn").classList.add("rec"); status(t("st.recording"));
  } catch (e) { modal(t("m.mic"), `<p>${e.message}</p>`); }
}
async function pttStop() {
  if (!ptt) return;
  const { stream, ctx, proc, chunks } = ptt; ptt = null;
  proc.disconnect(); stream.getTracks().forEach((t) => t.stop()); await ctx.close();
  $("pttBtn").classList.remove("rec"); status(t("st.robotvoice"));
  const n = chunks.reduce((a, c) => a + c.length, 0);
  if (n < 1600) { status(t("st.ready")); return; }
  const pcm = new Int16Array(n); let o = 0;
  for (const c of chunks) for (let i = 0; i < c.length; i++) pcm[o++] = Math.max(-32768, Math.min(32767, c[i] * 32767));
  try {
    const r = await fetch("/api/voice?live=" + (live ? 1 : 0), { method: "POST", body: pcm.buffer });
    if (!live && r.ok) { const a = new Audio(URL.createObjectURL(await r.blob())); await a.play(); }
  } catch (e) { logLine(t("log.voice", { e: e.message })); }
  status(run ? t("st.running") : t("st.ready"));
}

let rec = null;
function micToggle() {
  const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SR) return modal(t("m.nomic.t"), t("m.nomic.b"));
  if (rec) { rec.stop(); return; }
  rec = new SR(); rec.lang = /lith/i.test($("aiLang").value) ? "lt-LT" : "en-US"; rec.interimResults = true;
  $("micBtn").classList.add("rec");
  rec.onresult = (e) => { const r = e.results[e.results.length - 1]; $("chatInput").value = r[0].transcript; if (r.isFinal) { const t = r[0].transcript; $("chatInput").value = ""; chat(t); } };
  rec.onend = () => { $("micBtn").classList.remove("rec"); rec = null; };
  rec.start();
}

// ---------------------------------------------------------------- joints tab
function buildSliders() {
  const box = $("sliders"); box.innerHTML = `<div class="slhead">${t("jt.head")}</div>`;
  JOINTS.forEach((name, i) => {
    const j = robot.joints[name], r = j && j.range ? j.range : [-1.5, 1.5];
    const d = document.createElement("div"); d.className = "sl";
    d.innerHTML = `<label>${JOINT_LABELS[i]}<span id="jv${i}">0°</span></label><input type="range" min="${r[0]}" max="${r[1]}" step="0.01" value="0" id="js${i}" ${j ? "" : `disabled title='${t("jt.nomodel")}'`}>`;
    box.appendChild(d);
    d.querySelector("input").addEventListener("input", (e) => { const q = robot.q.slice(); q[i] = +e.target.value; robot.setPose(q); $("jv" + i).textContent = Math.round(q[i] * 57.3) + "°"; });
    d.querySelector("input").addEventListener("change", () => { if (live && $("jointsLive").checked && liveConfirmed) liveStep({ arm_pose: { q: robot.q, max_vel: 0.5 } }).catch((e) => logLine("❌ " + e.message)); });
  });
  for (const s of ["left", "right"]) {
    box.insertAdjacentHTML("beforeend", `<div class="slhead">${t("jt.hand", { s: t(s === "left" ? "jt.handL" : "jt.handR") })}</div>`);
    [0, 1, 2, 3, 4, 5].map((k) => t("finger." + k)).forEach((f, i) => {
      const d = document.createElement("div"); d.className = "sl hand";
      d.innerHTML = `<label>${f}</label><input type="range" min="0" max="1" step="0.05" value="0">`;
      box.appendChild(d);
      d.querySelector("input").addEventListener("input", (e) => { const q = robot.handQ[s].slice(); q[i] = +e.target.value; robot.handQ[s] = q; robot.apply(); });
      d.querySelector("input").addEventListener("change", () => { if (live && $("jointsLive").checked && liveConfirmed) liveStep({ hand: { side: s, q: robot.handQ[s] } }).catch(() => {}); });
    });
  }
}
function syncSliders() { robot.q.forEach((v, i) => { const s = $("js" + i); if (s) { s.value = v; $("jv" + i).textContent = Math.round(v * 57.3) + "°"; } }); }

// ---------------------------------------------------------------- timeline (keyframes, Choregraphe-style)
let keyframes = [], kfSel = -1;
function renderKf() {
  const el = $("kfList");
  if (!keyframes.length) { el.innerHTML = `<span class="muted">${t("jt.kfnone")}</span>`; return; }
  el.innerHTML = "";
  keyframes.forEach((k, i) => {
    const d = document.createElement("div"); d.className = "kf" + (i === kfSel ? " on" : "");
    d.innerHTML = `#${i + 1} <input type="number" step="0.1" min="0" value="${k.t.toFixed(1)}" title="${t("jt.seconds")}">s <button title="${t("jt.delete")}">✕</button>`;
    d.onclick = (e) => { if (e.target.tagName === "INPUT") return; if (e.target.tagName === "BUTTON") { keyframes.splice(i, 1); kfSel = -1; return renderKf(); }
      kfSel = i; robot.moveTo(k.q, 1.5).then(syncSliders); renderKf(); };
    d.querySelector("input").onchange = (e) => { k.t = Math.max(0, +e.target.value); keyframes.sort((a, b) => a.t - b.t); renderKf(); };
    el.appendChild(d);
  });
}
function kfRows(hz = 50) {
  // smoothstep between keyframes, sampled like a recorded CSV: [t, q0..q12]
  const rows = [], k = keyframes;
  for (let i = 0; i + 1 < k.length; i++) {
    const a = k[i], b = k[i + 1], n = Math.max(1, Math.round((b.t - a.t) * hz));
    for (let s = 0; s < n; s++) { let u = s / n; u = u * u * (3 - 2 * u); rows.push([a.t + (b.t - a.t) * s / n, ...a.q.map((v, j) => v + (b.q[j] - v) * u)]); }
  }
  const last = k[k.length - 1]; rows.push([last.t, ...last.q]);
  return rows.map((r) => r.map((v) => +v.toFixed(4)));
}
$("kfAdd").onclick = () => { const t = keyframes.length ? keyframes[keyframes.length - 1].t + 1 : 0; keyframes.push({ t, q: robot.q.slice() }); kfSel = keyframes.length - 1; renderKf(); };
$("kfClear").onclick = () => { keyframes = []; kfSel = -1; renderKf(); };
$("kfPlay").onclick = async () => { if (keyframes.length < 2) return modal(t("tl.title"), t("tl.need2")); await robot.playTraj(kfRows(), 1); syncSliders(); };
$("kfSave").onclick = async () => {
  if (keyframes.length < 2) return modal(t("tl.title"), t("tl.need2"));
  const name = await modal(t("tl.savetitle"), t("tl.savebody"), { ok: t("save"), input: t("tl.default") });
  if (!name) return;
  try { const r = await api("/api/arm_save", { name, rows: kfRows() }); LIB = await api("/api/library"); setLibrary(LIB); delete armCache[r.name];
    const b = place([{ t: "r1_arm_move", f: { FILE: r.name } }], 60, 60); b.select(); status(t("st.savedarm", { n: r.name })); }
  catch (e) { modal(t("m.notsaved"), `<p>${srv(e.message)}</p>`); }
};

// ---------------------------------------------------------------- wiring
function showTab(name) {
  document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("on", t.dataset.tab === name));
  document.querySelectorAll(".panel").forEach((p) => p.classList.toggle("on", p.id === "tab-" + name));
  if (name === "joints") syncSliders();
  setTimeout(() => Blockly.svgResize(ws), 0);
}
document.querySelectorAll(".tab").forEach((t) => (t.onclick = () => showTab(t.dataset.tab)));
document.querySelectorAll("[data-view]").forEach((b) => (b.onclick = () => robot.view(b.dataset.view)));
$("modeSim").onclick = () => setMode(false);
$("langBox").replaceWith(langSwitch(async () => { if (run) await stopAll(); return true; }));  // reload rebuilds blocks + menus
$("aiLang").value = SPEECH;
$("modeLive").onclick = async () => { setMode(true); if (!(await liveGate())) setMode(false); };
$("btnRun").onclick = () => start(compile(ws).main);
$("btnStop").onclick = stopAll;
$("btnSave").onclick = async () => {
  const name = await modal(t("m.save.t"), t("m.save.b"), { ok: t("save"), input: $("projectName").value });
  if (!name) return;
  try { await api("/api/save", { name, title: name, steps: toSteps(compile(ws).main), blocks: Blockly.serialization.workspaces.save(ws) }); LIB = await api("/api/library"); setLibrary(LIB); buildDeck(); status(t("st.saved")); }
  catch (e) { modal(t("m.notsaved"), `<p>${srv(e.message)}</p>`); }
};
$("btnMenu").onclick = () => $("menu").classList.toggle("hidden");
document.addEventListener("click", (e) => { if (!$("menu").contains(e.target) && e.target !== $("btnMenu")) $("menu").classList.add("hidden"); });
$("btnNew").onclick = () => { ws.clear(); place([{ t: "r1_start" }], 40, 40); };
$("btnDownload").onclick = () => {
  const a = document.createElement("a"); a.download = ($("projectName").value || "program") + ".r1.json";
  a.href = URL.createObjectURL(new Blob([JSON.stringify(Blockly.serialization.workspaces.save(ws), null, 1)])); a.click();
};
$("fileOpen").onchange = async (e) => { const f = e.target.files[0]; if (!f) return; Blockly.serialization.workspaces.load(JSON.parse(await f.text()), ws); $("projectName").value = f.name.split(".")[0]; };
$("btnLoadLib").onclick = async () => {
  const names = Object.keys(LIB.dances);
  const pick = await modal(t("m.lib.t"), `<p>${names.join(" · ")}</p><p>${t("m.lib.b")}</p>`, { ok: t("play"), input: names[0] || "" });
  if (pick && LIB.dances[pick]) start(stepsToNodes(LIB.dances[pick].steps), pick);
};
$("chatForm").onsubmit = (e) => { e.preventDefault(); const t = $("chatInput").value; $("chatInput").value = ""; chat(t); };
$("micBtn").onclick = micToggle;
$("copyCode").onclick = () => navigator.clipboard.writeText($("code").textContent);
$("jointsReset").onclick = () => { robot.moveTo(Array(13).fill(0), 1.2).then(syncSliders); robot.hand("both", Array(6).fill(0), 400); };
$("jointsBlock").onclick = async () => {
  const name = await modal(t("m.pose.t"), t("m.pose.b"), { ok: t("add"), input: t("m.pose.def", { n: ws.getBlocksByType("r1_pose_custom").length + 1 }) });
  if (!name) return;
  const b = place([{ t: "r1_pose_custom", f: { NAME: name }, data: JSON.stringify(robot.q.map((v) => +v.toFixed(3))) }], 60, 60);
  b.select(); showTab("code");
};
$("camSource").onchange = async (e) => {
  try { await vision.start(e.target.value); } catch (x) { modal(t("cam.err.title"), `<p>${srv(x.message)}</p><p>${t("cam.err.server")}</p>`); e.target.value = "off"; }
};
document.addEventListener("keydown", (e) => {
  if (e.target.closest && e.target.closest("input, textarea, .blocklyWidgetDiv")) return;
  if (e.code === "Space") { e.preventDefault(); stopAll(); return; }
  if ($("driveOn").checked && KEYMAP[e.code]) { held.add(e.code); e.preventDefault(); return; }
  if (/^[0-9]$/.test(e.key)) { const name = hotkeys[(+e.key + 9) % 10]; if (name) playNow({ dance: name }, moveTitle(name, LIB.dances[name].title)); return; }
  if (e.key === "Enter" && !run) start(compile(ws).main);
});

// ---------------------------------------------------------------- deck (stream-deck style buttons)
const CATS = ["Emotions", "Reactions", "Viral", "Movies", "Fight", "Objects"];
let hotkeys = [];
function playNow(step, label) {
  if (run) return status(t("st.busy"));
  start(stepsToNodes([step]), label);
}
function appendBlock(spec) {
  const startB = ws.getBlocksByType("r1_start")[0] || place([{ t: "r1_start" }], 40, 40);
  let last = startB; while (last.getNextBlock()) last = last.getNextBlock();
  const b = build([spec]); last.nextConnection.connect(b.previousConnection); b.select(); status(t("st.added"));
}
function deckButton(emoji, title, secs, onPlay, onAdd, key) {
  const b = document.createElement("button"); b.className = "dbtn ghost";
  b.innerHTML = `${key ? `<span class="key">${key}</span>` : ""}<span class="em">${emoji}</span><span class="t">${title}</span><span class="s">${secs ? secs + " s" : t("robot")}</span><button class="add" title="${t("deck.add")}">＋</button>`;
  b.onclick = (e) => { if (e.target.classList.contains("add")) { e.stopPropagation(); onAdd(); } else onPlay(); };
  return b;
}
function buildDeck() {
  const deck = $("deck"); deck.innerHTML = ""; hotkeys = [];
  for (const cat of CATS) {
    const items = Object.entries(LIB.dances).filter(([, d]) => d.category === cat);
    if (!items.length) continue;
    const sec = document.createElement("div"); sec.className = "deckcat"; sec.innerHTML = `<h4>${catLabel(cat)}</h4>`;
    const grid = document.createElement("div"); grid.className = "deckgrid";
    items.forEach(([name, d]) => {
      let key = "";
      if (cat === "Emotions" && hotkeys.length < 10) { hotkeys.push(name); key = String(hotkeys.length % 10); }
      const title = moveTitle(name, d.title);
      grid.appendChild(deckButton(d.emoji || "▶", title, d.seconds, () => playNow({ dance: name }, title), () => appendBlock({ t: "r1_play", f: { NAME: name } }), key));
    });
    sec.appendChild(grid); deck.appendChild(sec);
  }
  const sec = document.createElement("div"); sec.className = "deckcat"; sec.innerHTML = `<h4>${t("deck.factory")}</h4>`;
  const grid = document.createElement("div"); grid.className = "deckgrid";
  for (const [label, id] of FACTORY_DANCES) { const [em, ...t] = label.split(" "); grid.appendChild(deckButton(em, t.join(" "), 0, () => playNow({ fsm: +id }, label), () => appendBlock({ t: "r1_dance", f: { ID: id } }))); }
  for (const [label, id] of GESTURES) { const [em, ...t] = label.split(" "); grid.appendChild(deckButton(em, t.join(" "), 0, () => playNow({ arm_preset: +id }, label), () => appendBlock({ t: "r1_gesture", f: { ID: id } }))); }
  sec.appendChild(grid); deck.appendChild(sec);
  // compact emotion row for the operator under the chat
  $("emoRow").innerHTML = "";
  Object.entries(LIB.dances).filter(([, d]) => d.category === "Emotions" || d.category === "Reactions").forEach(([name, d]) => {
    const b = document.createElement("button"); b.className = "ghost"; b.textContent = d.emoji; b.title = moveTitle(name, d.title);
    b.onclick = () => playNow({ dance: name }, b.title); $("emoRow").appendChild(b);
  });
}

// ---------------------------------------------------------------- drive (telepresence MVP)
const held = new Set(); let driveBusy = false, lastPad = {};
const KEYMAP = { KeyW: [0.25, 0, 0], KeyS: [-0.15, 0, 0], KeyA: [0, 0, 0.5], KeyD: [0, 0, -0.5], KeyQ: [0, 0.15, 0], KeyE: [0, -0.15, 0] };
function driveVector(pad) {
  let vx = 0, vy = 0, wz = 0;
  for (const k of held) { const v = KEYMAP[k]; if (v) { vx += v[0]; vy += v[1]; wz += v[2]; } }
  if (pad) { vx += -pad.axes[1] * 0.25; vy += -pad.axes[0] * 0.15; wz += -(pad.axes[2] || 0) * 0.5; }
  const dz = (v, m) => (Math.abs(v) < 0.03 ? 0 : Math.max(-m, Math.min(m, v)));
  return [dz(vx, 0.25), dz(vy, 0.15), dz(wz, 0.5)];
}
let driving = false;
setInterval(async () => {
  const pad = navigator.getGamepads ? [...navigator.getGamepads()].find(Boolean) : null;
  $("padStatus").textContent = pad ? "🎮 " + pad.id.slice(0, 28) : t("drv.nopad");
  if (pad) {
    const b = (i) => pad.buttons[i] && pad.buttons[i].pressed, edge = (i) => b(i) && !lastPad[i];
    if (edge(9)) stopAll();
    if ($("driveOn").checked) {
      if (edge(0)) handAction("right", "grab"); if (edge(1)) handAction("right", "release");
      if (edge(2) && LIB.dances.happy) playNow({ dance: "happy" }, moveTitle("happy", "Happy")); if (edge(3) && LIB.dances.cheer) playNow({ dance: "cheer" }, moveTitle("cheer", "Cheer"));
    }
    lastPad = Object.fromEntries(pad.buttons.map((x, i) => [i, x.pressed]));
  }
  if (!$("driveOn").checked) return;
  const [vx, vy, wz] = driveVector(pad);
  document.querySelectorAll(".keygrid kbd").forEach((k) => k.classList.toggle("on", held.has("Key" + k.textContent)));
  if (vx || vy || wz) {
    robot.drive(vx, vy, wz, 0.45); driving = true;
    if (live && !driveBusy && liveConfirmed) { driveBusy = true; liveStep({ loco: { cmd: "move", value: `"${vx.toFixed(2)} ${vy.toFixed(2)} ${wz.toFixed(2)}"`, seconds: 0.5 } }).catch(() => {}).finally(() => (driveBusy = false)); }
  } else if (driving) {
    driving = false;
    if (live && liveConfirmed) liveStep({ loco: "stop_move" }).catch(() => {});
  }
}, 450);
function handAction(side, what) {
  const step = what === "grab" ? { grab: { side, strength: 0.6 } } : what === "release" ? { release: { side } } : { hand: { side, pose: what } };
  const q = what === "grab" ? Array(6).fill(0.6) : what === "release" ? Array(6).fill(0) : LIB.hands[what];
  robot.hand(side, q, 600); if (live && liveConfirmed) liveStep(step).catch((e) => logLine("❌ " + e.message));
}
document.querySelectorAll("[data-hand]").forEach((b) => (b.onclick = () => { const [s, w] = b.dataset.hand.split(","); handAction(s, w); }));
$("driveHome").onclick = () => robot.resetBase();
$("driveOn").onchange = async (e) => { if (e.target.checked && live && !(await liveGate())) e.target.checked = false; };
document.addEventListener("keyup", (e) => held.delete(e.code));
window.addEventListener("blur", () => held.clear());

// ---------------------------------------------------------------- vision wiring
$("vObjects").onchange = (e) => (vision.want.objects = e.target.checked);
$("vColors").onchange = (e) => (vision.want.colors = e.target.checked);
$("vPose").onchange = (e) => (vision.want.pose = e.target.checked);
$("vDescribe").onclick = () => { const s = vision.source === "off" ? t("exs.camoff") : vision.describe(); addMsg("bot", s); speak(s, SPEECH, new AbortController().signal); };
$("pttBtn").onpointerdown = (e) => { e.preventDefault(); pttStart(); };
$("pttBtn").onpointerup = $("pttBtn").onpointerleave = () => pttStop();
setInterval(() => {   // picture-in-picture of the camera in the 3D view
  const on = vision.running && vision.el; $("pip").classList.toggle("hidden", !on);
  if (!on) return;
  try { const c = $("pipCanvas").getContext("2d"); c.drawImage(vision.el, 0, 0, 240, 180); c.drawImage($("overlay"), 0, 0, 240, 180); } catch (e) { /* stream not ready */ }
}, 100);

// ---------------------------------------------------------------- boot
const robot = new Robot3D($("three"));
const vision = new Vision({ video: $("video"), img: $("mjpeg"), canvas: $("overlay"), empty: $("camEmpty"),
  onSign: (sign, icon) => {
    $("seen").textContent = icon;
    const nodes = compile(ws).signs[sign];
    if (nodes && nodes.length && !run) { logLine(t("log.saw", { x: icon })); start(nodes, t("st.saw", { x: icon })); }
  },
  onObject: (name) => {
    const nodes = compile(ws).signs["obj:" + name];
    if (nodes && nodes.length && !run) { const n = tf("obj." + name, name); logLine(t("log.sawa", { x: n })); start(nodes, t("st.saw", { x: n })); }
  },
  onColor: (color) => {
    const nodes = compile(ws).signs["color:" + color];
    if (nodes && nodes.length && !run) { const c = tf("color." + color, color); logLine(t("log.saw", { x: c })); start(nodes, t("st.saw", { x: c })); }
  } });
setInterval(() => { if (vision.running) $("seen").textContent = vision.current ? ({ Closed_Fist: "✊", Open_Palm: "✋", Victory: "✌️", Thumb_Up: "👍", Pointing_Up: "☝️", ILoveYou: "🤟", Thumb_Down: "👎", person: "🙂" }[vision.current] || "—") : "—"; }, 300);

(async () => {
  try {
    [LIB, STATUS] = await Promise.all([api("/api/library"), api("/api/status")]);
  } catch (e) { modal(t("m.server.t"), t("m.server.b")); }
  setLibrary(LIB);
  $("persona").innerHTML = Object.entries(LIB.personas).map(([k, p]) => `<option value="${k}">${tf("persona." + k, p.name)}</option>`).join("");
  $("aiKey").textContent = STATUS.ai_key ? t("ai.key.on") : t("ai.key.off");
  $("examples").innerHTML = ""; for (const name of Object.keys(EXAMPLES)) { const b = document.createElement("button"); b.className = "ghost"; b.textContent = name; b.onclick = () => { loadExample(name); $("menu").classList.add("hidden"); }; $("examples").appendChild(b); }
  let saved = null; try { saved = JSON.parse(localStorage.getItem("r1studio") || "null"); } catch (e) { /* ignore */ }
  if (saved && saved.blocks) Blockly.serialization.workspaces.load(saved, ws); else loadExample(t("ex.hello"));
  refreshCode();
  await robot.load();
  buildSliders();
  buildDeck();
  status(t("st.ready"));
  let since = Date.now() / 1000;
  setInterval(async () => { if (!live) return; try { const l = await api("/api/log?since=" + since); l.forEach((e) => { logLine(e.line); since = e.t; }); } catch (e) { /* offline */ } }, 1500);
})();
