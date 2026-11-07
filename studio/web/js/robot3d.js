// 3D R1 from Unitree's MuJoCo model (exported by tools/export_model.py) + simple 5-finger hands.
import * as THREE from "three";
import { OrbitControls } from "../vendor/OrbitControls.js";
import { JOINTS } from "./blocks.js";

export class Robot3D {
  constructor(el) {
    this.el = el;
    this.scene = new THREE.Scene();
    this.camera = new THREE.PerspectiveCamera(35, 1, 0.05, 50);
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    this.renderer.setPixelRatio(Math.min(2, devicePixelRatio));
    el.appendChild(this.renderer.domElement);
    this.controls = new OrbitControls(this.camera, this.renderer.domElement);
    this.controls.enableDamping = true;
    this.joints = {};       // name → {pivot, axis, range}
    this.q = Array(13).fill(0);
    this.handQ = { left: Array(6).fill(0), right: Array(6).fill(0) };
    this.fingers = { left: [], right: [] };
    this.extra = 0;         // factory-move "dance" sway (sim only)
    this.base = new THREE.Group(); this.scene.add(this.base);  // moved by drive()
    this.scene.add(new THREE.HemisphereLight(0xffffff, 0xb0b0a8, 2.2));
    const sun = new THREE.DirectionalLight(0xffffff, 1.6); sun.position.set(2, 4, 3); this.scene.add(sun);
    const grid = new THREE.GridHelper(6, 24, 0xcfcfc8, 0xe2e2dc); this.scene.add(grid);
    const ring = new THREE.Mesh(new THREE.RingGeometry(1.95, 2.0, 64), new THREE.MeshBasicMaterial({ color: 0xD90429, side: THREE.DoubleSide }));
    ring.rotation.x = -Math.PI / 2; ring.position.y = 0.002; this.scene.add(ring); // the 2 m safety line
    this.view("front");
    new ResizeObserver(() => this.resize()).observe(el);
    this.resize();
    const tick = () => { this.controls.update(); this.renderer.render(this.scene, this.camera); requestAnimationFrame(tick); };
    tick();
  }

  resize() {
    const w = this.el.clientWidth, h = this.el.clientHeight;
    this.renderer.setSize(w, h); this.camera.aspect = w / Math.max(1, h); this.camera.updateProjectionMatrix();
  }

  view(name) {
    const v = { front: [[0, 1.0, -2.6], [0, 0.8, 0]], side: [[2.6, 1.0, -0.2], [0, 0.8, 0]], close: [[0, 1.0, -1.0], [0, 0.85, 0]] }[name];
    this.camera.position.set(...v[0]); this.controls.target.set(...v[1]);
  }

  async load(url = "model/r1.json") {
    const meta = await (await fetch(url)).json();
    const bin = await (await fetch(url.replace(".json", ".bin"))).arrayBuffer();
    const mat = new THREE.MeshStandardMaterial({ color: 0xdfe2ea, metalness: 0.35, roughness: 0.45 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x2a2a2e, metalness: 0.2, roughness: 0.6 });
    // MuJoCo is z-up; three.js is y-up → rotate the whole robot
    this.root = new THREE.Group(); this.root.rotation.x = -Math.PI / 2; this.root.rotation.z = Math.PI / 2;
    this.base.add(this.root);
    const groups = [];
    meta.bodies.forEach((b, i) => {
      const g = new THREE.Group();
      g.position.set(...b.pos);
      g.quaternion.set(b.quat[1], b.quat[2], b.quat[3], b.quat[0]);
      let holder = g;
      if (b.joint) {
        const pivot = new THREE.Group(); pivot.position.set(...b.joint.pos);
        const inner = new THREE.Group(); inner.position.set(...b.joint.pos.map((v) => -v));
        g.add(pivot); pivot.add(inner); holder = inner;
        this.joints[b.joint.name] = { pivot, axis: new THREE.Vector3(...b.joint.axis), range: b.joint.range };
      }
      for (const m of b.meshes) {
        const geo = new THREE.BufferGeometry();
        geo.setAttribute("position", new THREE.BufferAttribute(new Float32Array(bin, m.v[0], m.v[1] * 3), 3));
        geo.setIndex(new THREE.BufferAttribute(new Uint32Array(bin, m.f[0], m.f[1] * 3), 1));
        geo.computeVertexNormals();
        const lum = m.rgba[0] + m.rgba[1] + m.rgba[2];
        holder.add(new THREE.Mesh(geo, lum < 1 ? dark : mat));
      }
      groups.push({ g, holder, name: b.name });
      (b.parent >= 0 ? groups[b.parent].holder : this.root).add(g);
    });
    this.root.position.y = 0; groups[0].g.position.z = meta.standing_z;
    for (const s of ["left", "right"]) {
      const wrist = groups.find((x) => x.name === `${s}_wrist_roll_link` || x.name === `${s}_wrist_yaw_link`)
        || groups.filter((x) => x.name.startsWith(s) && x.name.includes("wrist")).pop();
      if (wrist) this.addHand(wrist.holder, s);
    }
    this.apply();
  }

  addHand(parent, s) {
    // A simple Revo2 stand-in: palm + 5 fingers that bend 0 (open) → 1 (closed)
    const m = new THREE.MeshStandardMaterial({ color: 0x2F6FEB, metalness: 0.2, roughness: 0.45 });
    const hand = new THREE.Group(); hand.position.set(0.135, 0, 0); hand.scale.setScalar(1.4); parent.add(hand);
    const palm = new THREE.Mesh(new THREE.BoxGeometry(0.07, 0.02, 0.065), m); palm.position.x = 0.035; hand.add(palm);
    // Both hands: forearm forward = thumb up (+z), palm facing the body's midline. ⚠️ assumed, not seen on our robot yet.
    const spec = [[0.02, 0.04, 0.035, true], [0.07, 0.024, 0.045], [0.07, 0.008, 0.05], [0.07, -0.008, 0.047], [0.07, -0.024, 0.04]];
    spec.forEach(([x, z, len, thumb], i) => {
      const f = new THREE.Group(); f.position.set(x, 0, z);
      const seg = new THREE.Mesh(new THREE.BoxGeometry(len, 0.014, 0.013), m); seg.position.x = len / 2; f.add(seg);
      if (thumb) f.rotation.y = -0.9;
      hand.add(f); this.fingers[s].push(f);
    });
  }

  clampJoint(i, v) {
    const j = this.joints[JOINTS[i]];
    return j && j.range ? Math.min(j.range[1], Math.max(j.range[0], v)) : v;
  }

  apply() {
    JOINTS.forEach((name, i) => {
      const j = this.joints[name];
      if (j) j.pivot.quaternion.setFromAxisAngle(j.axis, this.q[i] + (i === 10 ? this.extra : 0));
    });
    for (const s of ["left", "right"]) {
      const q = this.handQ[s];
      // Revo2 order: thumb, thumb_aux, index, middle, ring, pinky
      [q[0], q[2], q[3], q[4], q[5]].forEach((v, i) => { if (this.fingers[s][i]) this.fingers[s][i].rotation.z = (s === "left" ? -1 : 1) * v * 1.5 * (i ? 1 : 0.7); });
    }
    if (this.joints.waist_roll) this.joints.waist_roll.pivot.quaternion.setFromAxisAngle(this.joints.waist_roll.axis, this.extra * 0.3);
  }

  // Simulator walking for the Drive tab: robot faces -z in this scene
  drive(vx, vy, wz, dt) {
    const b = this.base, yaw = b.rotation.y;
    b.rotation.y += wz * dt;
    b.position.x += (-Math.sin(yaw) * vx - Math.cos(yaw) * vy) * dt;
    b.position.z += (-Math.cos(yaw) * vx + Math.sin(yaw) * vy) * dt;
  }

  resetBase() { this.base.position.set(0, 0, 0); this.base.rotation.set(0, 0, 0); }

  setPose(q) { this.q = q.map((v, i) => this.clampJoint(i, v)); this.apply(); }

  // Smooth move like r1_arm (smoothstep, max joint speed rad/s)
  moveTo(target, maxVel = 0.8, signal) {
    const start = this.q.slice(); target = target.map((v, i) => this.clampJoint(i, v));
    const dur = Math.max(0.2, Math.max(...target.map((v, i) => Math.abs(v - start[i]))) / maxVel) * 1000;
    return this.animate(dur, (s) => { s = s * s * (3 - 2 * s); this.q = start.map((v, i) => v + (target[i] - v) * s); this.apply(); }, signal);
  }

  async playTraj(rows, speed = 1, signal) {
    if (rows.length < 2) return;
    await this.moveTo(rows[0].slice(1), 0.6, signal);
    const t0 = rows[0][0], T = rows[rows.length - 1][0] - t0;
    let k = 0;
    await this.animate(T / speed * 1000, (s) => {
      const t = t0 + s * T;
      while (k + 1 < rows.length && rows[k + 1][0] <= t) k++;
      const a = rows[k + 1] ? (t - rows[k][0]) / Math.max(1e-3, rows[k + 1][0] - rows[k][0]) : 0;
      this.q = rows[k].slice(1).map((v, i) => v + ((rows[k + 1] || rows[k])[i + 1] - v) * Math.min(1, a));
      this.apply();
    }, signal);
  }

  hand(side, q, ms = 600, signal) {
    const sides = side === "both" ? ["left", "right"] : [side];
    const start = sides.map((s) => this.handQ[s].slice());
    return this.animate(ms, (t) => { t = t * t * (3 - 2 * t); sides.forEach((s, n) => { this.handQ[s] = start[n].map((v, i) => v + (q[i] - v) * t); }); this.apply(); }, signal);
  }

  // "Factory move" placeholder: gentle sway so the sim shows something is happening
  sway(ms, signal) { return this.animate(ms, (t) => { this.extra = Math.sin(t * Math.PI * 2 * (ms / 1200)) * 0.35 * Math.sin(t * Math.PI); this.apply(); }, signal).then(() => { this.extra = 0; this.apply(); }); }

  animate(ms, fn, signal) {
    return new Promise((resolve) => {
      const t0 = performance.now();
      const step = (now) => {
        if (signal && signal.aborted) return resolve();
        const s = Math.min(1, (now - t0) / ms); fn(s);
        s < 1 ? requestAnimationFrame(step) : resolve();
      };
      requestAnimationFrame(step);
    });
  }
}
