// Camera + vision in the browser (MediaPipe, offline from /vendor):
// hand signs · objects (80 everyday COCO classes) · colors · body pose. Source: this computer's camera
// or the robot/server stream (/api/camera.mjpg).
import { FilesetResolver, GestureRecognizer, ObjectDetector, PoseLandmarker } from "../vendor/vision_bundle.mjs";

const NAMES = { Closed_Fist: "✊", Open_Palm: "✋", Victory: "✌️", Thumb_Up: "👍", Thumb_Down: "👎", Pointing_Up: "☝️", ILoveYou: "🤟", person: "🙂" };
const COLORS = { red: [[0, 15], [345, 360]], orange: [[16, 40]], yellow: [[41, 70]], green: [[71, 170]], blue: [[171, 255]], purple: [[256, 344]] };

export class Vision {
  constructor({ video, img, canvas, empty, onSign, onObject, onColor }) {
    Object.assign(this, { video, img, canvas, empty, onSign, onObject, onColor });
    this.ctx = canvas.getContext("2d");
    this.source = "off"; this.last = null; this.stable = 0; this.cooldown = {};
    this.want = { objects: true, colors: true, pose: false };
    this.objects = []; this.color = null; this.pose = null; this.frame = 0;
    this.scratch = document.createElement("canvas"); this.scratch.width = 64; this.scratch.height = 48;
  }

  async init() {
    if (this.rec) return;
    const files = await FilesetResolver.forVisionTasks("vendor/wasm");
    this.rec = await GestureRecognizer.createFromOptions(files, { baseOptions: { modelAssetPath: "vendor/gesture_recognizer.task" }, runningMode: "VIDEO", numHands: 1 });
    this.det = await ObjectDetector.createFromOptions(files, { baseOptions: { modelAssetPath: "vendor/efficientdet_lite0.tflite" }, runningMode: "VIDEO", scoreThreshold: 0.45, maxResults: 5 });
    this.poser = await PoseLandmarker.createFromOptions(files, { baseOptions: { modelAssetPath: "vendor/pose_landmarker_lite.task" }, runningMode: "VIDEO", numPoses: 1 });
  }

  async start(source) {
    this.stop();
    this.source = source;
    if (source === "off") return;
    await this.init();
    if (source === "webcam") {
      this.stream = await navigator.mediaDevices.getUserMedia({ video: { width: 640, height: 480 } });
      this.video.srcObject = this.stream; await this.video.play();
      this.video.classList.remove("hidden"); this.img.classList.add("hidden"); this.el = this.video;
    } else {
      this.img.crossOrigin = "anonymous";
      this.img.src = "/api/camera.mjpg?" + Date.now();
      this.img.classList.remove("hidden"); this.video.classList.add("hidden"); this.el = this.img;
    }
    this.empty.classList.add("hidden");
    this.running = true; this.loop();
  }

  stop() {
    this.running = false;
    if (this.stream) this.stream.getTracks().forEach((t) => t.stop());
    this.stream = null; this.img.src = ""; this.empty.classList.remove("hidden");
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
    this.objects = []; this.pose = null; this.landmarks = null; this.current = null;
  }

  fire(kind, key, fn, ms = 2500) {
    const now = performance.now();
    if ((this.cooldown[kind + key] || 0) > now) return;
    this.cooldown[kind + key] = now + ms; fn();
  }

  loop() {
    if (!this.running) return;
    const el = this.el, w = el.videoWidth || el.naturalWidth, h = el.videoHeight || el.naturalHeight;
    if (w && h) {
      this.canvas.width = w; this.canvas.height = h;
      const t = performance.now(), c = this.ctx;
      this.frame++;
      c.clearRect(0, 0, w, h);
      // hands: every frame
      let res = null;
      try { res = this.rec.recognizeForVideo(el, t); } catch (e) { /* frame not ready */ }
      let sign = null;
      if (res && res.landmarks && res.landmarks.length) {
        c.fillStyle = "#D90429";
        for (const p of res.landmarks[0]) { c.beginPath(); c.arc(p.x * w, p.y * h, 4, 0, 7); c.fill(); }
        const g = res.gestures[0] && res.gestures[0][0];
        sign = g && g.categoryName !== "None" && g.score > 0.6 ? g.categoryName : null;
        this.landmarks = res.landmarks[0];
      } else this.landmarks = null;
      if (sign && sign === this.last) this.stable++; else { this.stable = 0; this.last = sign; }
      if (sign && this.stable === 6) this.fire("sign", sign, () => this.onSign(sign, NAMES[sign] || sign));
      this.current = sign;
      // objects: every 3rd frame
      if (this.want.objects && this.frame % 3 === 0) {
        try { this.objects = this.det.detectForVideo(el, t + 0.1).detections.map((d) => ({ name: d.categories[0].categoryName, score: d.categories[0].score, box: d.boundingBox })); } catch (e) { /* skip */ }
        for (const o of this.objects) this.fire("obj", o.name, () => this.onObject(o.name), 4000);
      }
      if (this.want.objects) for (const o of this.objects) {
        const b = o.box; c.strokeStyle = "#2F6FEB"; c.lineWidth = 3; c.strokeRect(b.originX, b.originY, b.width, b.height);
        c.save(); c.scale(-1, 1); c.fillStyle = "#2F6FEB"; c.font = "bold 18px Inter, sans-serif";
        c.fillText(`${o.name} ${Math.round(o.score * 100)}%`, -(b.originX + b.width), Math.max(18, b.originY - 4)); c.restore();
      }
      // body pose: every 2nd frame when wanted
      if (this.want.pose && this.frame % 2 === 0) {
        try { const p = this.poser.detectForVideo(el, t + 0.2); this.pose = p.landmarks && p.landmarks[0] ? p.landmarks[0] : null; } catch (e) { this.pose = null; }
      }
      if (this.want.pose && this.pose) {
        c.strokeStyle = "#12A150"; c.lineWidth = 4;
        for (const [a, b] of [[11, 13], [13, 15], [12, 14], [14, 16], [11, 12], [11, 23], [12, 24], [23, 24]]) {
          c.beginPath(); c.moveTo(this.pose[a].x * w, this.pose[a].y * h); c.lineTo(this.pose[b].x * w, this.pose[b].y * h); c.stroke();
        }
      }
      // colors: every 10th frame, centre of the image
      if (this.want.colors && this.frame % 10 === 0) {
        this.color = this.dominantColor(el, w, h);
        if (this.color) this.fire("color", this.color, () => this.onColor(this.color), 4000);
      }
    }
    requestAnimationFrame(() => this.loop());
  }

  dominantColor(el, w, h) {
    const s = this.scratch, x = s.getContext("2d", { willReadFrequently: true });
    x.drawImage(el, w / 3, h / 3, w / 3, h / 3, 0, 0, s.width, s.height);
    const px = x.getImageData(0, 0, s.width, s.height).data, count = {};
    let total = 0;
    for (let i = 0; i < px.length; i += 4) {
      const r = px[i] / 255, g = px[i + 1] / 255, b = px[i + 2] / 255, mx = Math.max(r, g, b), mn = Math.min(r, g, b), d = mx - mn;
      total++;
      if (mx < 0.25 || d / (mx || 1) < 0.45) continue;  // dark or grey
      let hue = mx === r ? 60 * (((g - b) / d) % 6) : mx === g ? 60 * ((b - r) / d + 2) : 60 * ((r - g) / d + 4);
      if (hue < 0) hue += 360;
      for (const [name, ranges] of Object.entries(COLORS)) if (ranges.some(([a, z]) => hue >= a && hue <= z)) count[name] = (count[name] || 0) + 1;
    }
    const best = Object.entries(count).sort((a, b) => b[1] - a[1])[0];
    return best && best[1] / total > 0.22 ? best[0] : null;
  }

  // what the camera sees, in words
  describe() {
    const names = [...new Set(this.objects.map((o) => o.name))];
    const parts = [];
    if (names.length) parts.push(names.length === 1 ? `a ${names[0]}` : names.slice(0, -1).map((n) => "a " + n).join(", ") + " and a " + names.slice(-1));
    if (this.color) parts.push(`something ${this.color}`);
    if (this.current) parts.push(`a hand sign ${NAMES[this.current] || ""}`);
    return parts.length ? "I can see " + parts.join(", and ") + "." : "Hmm, I don't see anything I know yet.";
  }

  // finger curl 0..1 for the "copy my hand" mirror, Revo2 order
  fingerCurl() {
    const l = this.landmarks; if (!l) return null;
    const d = (a, b) => Math.hypot(l[a].x - l[b].x, l[a].y - l[b].y);
    const c = (tip, base) => Math.max(0, Math.min(1, 1.9 - d(tip, 0) / Math.max(1e-6, d(base, 0))));
    const t = c(4, 2); return [t, t, c(8, 5), c(12, 9), c(16, 13), c(20, 17)];
  }

  // person's arms → robot arm joints (mirror: their right arm drives the robot's left, like a mirror).
  // 2D camera estimate: shoulder raise from upper-arm angle, elbow from the angle at the elbow.
  armTargets() {
    const p = this.pose; if (!p) return null;
    const ang = (a, b) => Math.atan2(p[b].x - p[a].x, p[b].y - p[a].y);   // 0 = pointing down
    const bend = (s, e, w) => { const a = ang(s, e), b = ang(e, w); let d = Math.abs(a - b); if (d > Math.PI) d = 2 * Math.PI - d; return d; };
    const side = (s, e, w, sign) => {
      const up = ang(s, e) * sign;            // + = arm swung out to that side / up
      const raise = Math.max(0, Math.min(2.8, Math.abs(up)));
      const out = Math.max(0, Math.min(1.4, up > 0 ? Math.sin(Math.min(Math.PI / 2, raise)) * 1.3 : 0));
      const elbow = 1.4 - Math.min(2.2, bend(s, e, w)) / 2.2 * 2.2;   // straight 1.4 → folded -0.8
      return { pitch: -raise * Math.cos(Math.min(1.2, out)), out, elbow: Math.max(-0.8, Math.min(1.4, elbow)) };
    };
    const L = side(12, 14, 16, -1), R = side(11, 13, 15, 1);   // image is mirrored
    const q = Array(13).fill(0);
    q[0] = L.pitch; q[1] = L.out; q[3] = L.elbow;
    q[5] = R.pitch; q[6] = -R.out; q[8] = R.elbow;
    return q;
  }

  // follow: the biggest person → turn + forward/back (0 when centred and ~1.5 m away)
  followCommand() {
    const people = this.objects.filter((o) => o.name === "person");
    if (!people.length) return null;
    const p = people.sort((a, b) => b.box.width * b.box.height - a.box.width * a.box.height)[0];
    const w = this.el.videoWidth || this.el.naturalWidth || 640, h = this.el.videoHeight || this.el.naturalHeight || 480;
    const cx = (p.box.originX + p.box.width / 2) / w - 0.5;  // -0.5 left … +0.5 right (unmirrored image)
    const size = p.box.height / h;                           // ~0.6 at about 1.5 m (⚠️ to calibrate)
    const wz = Math.abs(cx) > 0.08 ? Math.max(-0.4, Math.min(0.4, -cx * 1.2)) : 0;
    const vx = size < 0.45 ? 0.15 : size > 0.8 ? -0.1 : 0;
    return { vx, vy: 0, wz, size };
  }
}
export { NAMES };
