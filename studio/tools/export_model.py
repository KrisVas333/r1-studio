"""Export Unitree's R1 MuJoCo model → web/model/r1.json + r1.bin for the three.js viewer.
Run with the sim venv:  ~/r1/sim/.venv/bin/python tools/export_model.py"""
import json
import os
import sys

import mujoco
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
SIM = os.path.expanduser("~/r1/sim")
sys.path.insert(0, SIM)
sys.argv = sys.argv[:1]
import r1sim  # noqa: E402  (standing height + scene path)

m = mujoco.MjModel.from_xml_path(r1sim.SCENE)
out_dir = os.path.join(HERE, "..", "web", "model")
os.makedirs(out_dir, exist_ok=True)
blob, bodies = bytearray(), []


def quat_to_mat(q):
    r = np.zeros(9)
    mujoco.mju_quat2Mat(r, np.asarray(q, float))
    return r.reshape(3, 3)


for b in range(1, m.nbody):
    body = {"name": mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_BODY, b),
            "parent": int(m.body_parentid[b]) - 1,
            "pos": m.body_pos[b].tolist(), "quat": m.body_quat[b].tolist(), "joint": None, "meshes": []}
    for j in range(m.njnt):
        if m.jnt_bodyid[j] == b and m.jnt_type[j] == mujoco.mjtJoint.mjJNT_HINGE:
            body["joint"] = {"name": mujoco.mj_id2name(m, mujoco.mjtObj.mjOBJ_JOINT, j).replace("_joint", ""),
                             "axis": m.jnt_axis[j].tolist(), "pos": m.jnt_pos[j].tolist(),
                             "range": m.jnt_range[j].tolist() if m.jnt_limited[j] else None}
    for g in range(m.ngeom):
        if m.geom_bodyid[g] != b or m.geom_type[g] != mujoco.mjtGeom.mjGEOM_MESH or m.geom_group[g] != 1:
            continue
        mid = m.geom_dataid[g]
        v0, nv = m.mesh_vertadr[mid], m.mesh_vertnum[mid]
        f0, nf = m.mesh_faceadr[mid], m.mesh_facenum[mid]
        verts = m.mesh_vert[v0:v0 + nv] @ quat_to_mat(m.geom_quat[g]).T + m.geom_pos[g]
        faces = m.mesh_face[f0:f0 + nf].astype(np.uint32)
        vo = len(blob); blob += verts.astype(np.float32).tobytes()
        fo = len(blob); blob += faces.tobytes()
        body["meshes"].append({"v": [vo, int(nv)], "f": [fo, int(nf)], "rgba": m.geom_rgba[g].tolist()})
    bodies.append(body)

sim = r1sim.Sim()
json.dump({"source": "unitreerobotics/unitree_mujoco unitree_robots/r1", "standing_z": float(sim.base[2]),
           "bodies": bodies}, open(os.path.join(out_dir, "r1.json"), "w"))
open(os.path.join(out_dir, "r1.bin"), "wb").write(bytes(blob))
print("bodies", len(bodies), "bin MB", round(len(blob) / 1e6, 1), "joints",
      [b["joint"]["name"] for b in bodies if b["joint"]][:6], "...")
