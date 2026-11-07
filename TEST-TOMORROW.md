# Rytojaus bandymas: R1 iš Mac, be EDU kompiuterio

**Tikslas:** robotas pasako vieną sakinį, pakeičia spalvą ir garsumą. Niekas nejuda.
**Reikia:** Mac, Ethernet laidas, USB‑C adapteris, gamyklinis pultelis, 20 min.
**Taisyklė:** jokių rankų komandų. Pirmiausia filmuojam ėjimą (žr. 7).

Komandas rašyk **Terminale**. Antrą terminalo langą atidaryk su **Cmd+N**.

---

## 1. Laidas ir ping

**Daryk:** laidas į viršutinį dešinįjį lizdą po kaklu. Tada:
```
~/r1/connect.sh en16
```
**Turi matyti:** `✅ 192.168.123.161 answers`
**Jei ne:** paleisk `~/r1/connect.sh` be nieko. Jis parodo adapterio vardą (pvz. `en7`). Paleisk dar kartą su tuo vardu. Robotas turi būti įjungtas ilgiau nei 1 min.

## 2. Paleisk tiltą

**Daryk (1 langas):**
```
~/r1/start-robot.sh mac --allow-commands
```
**Turi matyti:** `commands ALLOWED (arm with GO)` ir `MAC-DIRECT`.
**Jei ne:** `already running` reiškia, kad kažkas jau veikia. Spausk **Ctrl+C** ir paleisk dar kartą.

## 3. Ar robotas matomas

**Daryk (2 langas):**
```
curl -s localhost:8090/state
```
**Turi matyti:** `"connected": true`, `"volume": 100` (ar kitas skaičius).
**Jei ne:** `"note"` parašo priežastį. `en16 not found` = laidas ar adapteris. Palauk 5 s ir kartok.

## 4. Vienas sakinys per roboto garsiakalbį

**Daryk:**
```
curl -s -X POST localhost:8080/api/bridge/arm -d '{"go":"GO"}'
curl -s -X POST localhost:8080/api/bridge/say -d '{"text":"Hello, I am R1"}'
```
**Turi matyti:** `{"ok": true ...}` ir **išgirsti** robotą.
**Jei ne:** `Not armed` = pakartok pirmą eilutę. `Commands are off` = 2 žingsnį paleisk su `--allow-commands`. Tylu, bet `ok` = garsumas (6 žingsnis).

## 5. LED spalva

**Daryk:**
```
curl -s -X POST localhost:8080/api/bridge/led -d '{"r":0,"g":0,"b":255}'
```
**Turi matyti:** `{"ok": true ...}` ir **mėlyną** šviesą.
**Jei ne:** užrašyk, ką atsakė. LED gali neturėti šio modelio. Eik toliau.

## 6. Garsumas

**Daryk:**
```
curl -s -X POST localhost:8080/api/bridge/volume -d '{"n":60}'
curl -s localhost:8090/state
```
**Turi matyti:** `"volume": 60` (po 10 s).
**Jei ne:** užrašyk atsakymą. Grąžink: `-d '{"n":100}'`.

## 7. Ėjimo kadrai su pulteliu (PRIEŠ bet kokį rankų darbą)

**Daryk:** filmuok ėjimą, posūkius, šokius **tik su gamykliniu pulteliu**.
**Turi matyti:** robotas vaikšto kaip visada.
**Kodėl dabar:** pirma rankų komanda einant užrakina robotą (**FSM 816**). Ėjimas dingsta iki perkrovimo. Todėl rankas bandom tik po filmavimo, ant stovo.

## 8. Sustabdyk

**Daryk:**
```
curl -s -X POST localhost:8080/api/stop -d '{}'
```
Tada 1 lange **Ctrl+C**.
**Turi matyti:** `{"ok": true}`, tiltas išsijungia.
**Jei ne:** uždaryk terminalo langą. Robotui tai nieko nedaro.

---

**Po bandymo užrašyk:** kas veikė (1–8), ką robotas pasakė, ar matėsi LED, kiek užtruko.
