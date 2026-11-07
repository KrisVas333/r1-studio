# Contributing / Prisidėti

## 🇱🇹 Lietuviškai

**Paleisk simuliatoriuje (Mac arba Linux, robotas nereikalingas):**
```bash
git clone https://github.com/KrisVas333/r1-studio ~/r1 && cd ~/r1
cd sim && git clone --depth 1 --filter=blob:none --sparse https://github.com/unitreerobotics/unitree_mujoco \
  && (cd unitree_mujoco && git sparse-checkout set unitree_robots/r1) \
  && python3 -m venv .venv && .venv/bin/pip install mujoco pyyaml numpy "imageio[ffmpeg]" && cd ..
sim/.venv/bin/python studio/server.py     # atidaryk http://localhost:8080
```

**Testai prieš kiekvieną pakeitimą:**
```bash
cd studio && ../sim/.venv/bin/python -m unittest tests.test_server
cd ../r1ctl && ../sim/.venv/bin/python -m unittest discover tests
```

**Klaida ar idėja:** atidaryk *Issue* GitHub'e. Parašyk, ką darei, ką tikėjaisi ir ką pamatei. Pridėk ekrano nuotrauką ir naršyklės konsolės klaidą, jei yra.

**Pakeitimas:** padaryk *fork*, atskirą šaką, mažą *Pull Request* su vienu tikslu. Aprašyme nurodyk, kaip tikrinai.

**Tekstai:** visi sąsajos tekstai yra `studio/web/js/i18n.js` (`raktas: [angliškai, lietuviškai]`). Naujas tekstas = naujas raktas abiem kalbomis.

**⚠️ Saugos taisyklė:** nekeisk įjungimo (GO), STOP, greičio ribų, `arm_safe.json` ar `gate()` serveryje, kol pakeitimas nepatikrintas su tikru robotu, pakabintu ant stovo, su suaugusiu prie roboto pultelio. PR aprašyme parašyk, kada ir kaip tikrinai.

## 🇬🇧 English

**Run in the simulator (Mac or Linux, no robot needed):** the commands above, then open http://localhost:8080.

**Tests before every change:** the two `unittest` lines above.

**Bug or idea:** open an Issue. Say what you did, what you expected and what you saw. Add a screenshot and any browser console error.

**Change:** fork, one branch, a small Pull Request with one purpose. Say how you tested it.

**Text:** all UI strings live in `studio/web/js/i18n.js` (`key: [English, Lithuanian]`). New text means a new key in both languages.

**⚠️ Safety rule:** do not change arming (GO), STOP, speed caps, `arm_safe.json` or the server's `gate()` without a test on the real robot hanging on a gantry, with an adult on the hardware remote. Write in the PR when and how you tested it.
