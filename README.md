# NCEC ROM Tool

An open-source **read / edit / compare / flash / live-monitor** tool for the factory ECU of the
**Mazda MX-5 NC (chassis NCEC, LF-VE engine, Denso 279700-4073 / Renesas SH7058 PCM, CAL ID LFG7EG)**.
A hobby / learning project aiming at a LinkECU- or Haltech-style native-reflash tuning
environment for the stock ECU.

Current version: **2.30** (`VERSION`; change history in `CHANGELOG_ja.md`, Japanese).
日本語版: [README_ja.md](README_ja.md)

---

## ⚠️ Disclaimer & Safety (read first)

- This software comes with **NO WARRANTY**. The author is not liable for any damage
  (ECU bricking, vehicle faults, legal violations, etc.). **Use entirely at your own risk.**
- Modifying an ECU can **destroy the engine, cause a fire, or leave the car undriveable.**
  Do not change ignition timing, fuel targets, limiters, electronic-throttle or torque
  tables unless you understand them.
- **Strongly recommended to work on a spare / bench ECU.** Keep your original read-out.
  Do not cut power while flashing (about 10 minutes).
- Compliance with road-use and emissions regulations is the user's responsibility —
  **defeating emissions controls on a road vehicle is illegal in most jurisdictions.**
- This repository **does not contain any ECU firmware (ROM image), SBL, or the Renesas manual.**
  Supply a dump read from your own ECU.

---

## Status

| Feature | State |
|---|---|
| Load ROM, edit maps by category (LibreTuner definition, 909 tables), JA / EN UI | ✅ |
| Checksum auto-correction on save | ✅ |
| ECU read-out (UDS 0x23, no SBL needed) / ECU↔ROM and ROM↔ROM compare | ✅ |
| **Flashing over CAN** (SBL model) | ✅ Verified on a bench ECU and in the car via the OBD-II port — **SBL not included; you must supply it** |
| Live monitoring (OBD-II Mode 01, >10 Hz) + DTCs + active-cell tracking on maps | ✅ |
| Live PID decimation (poll slow PIDs less often; faster RPM update) | ✅ Offline-verified; on-engine effect not yet measured |
| Configure per-PID poll intervals in the GUI (Settings → Live PID intervals); the live-RAM channels (KR/clutch/EGT/knock) are listed there too | ✅ |
| DBW throttle 1:1 tool (cable-like pedal map; edits control + monitor copies; editor **DBW throttle** button) | ✅ Generated & self-verified; on-car effect not yet tested |
| Anti-lag (overrun pops/burble) patch — editor **Anti-lag** button (A: DFCO off / B: RPM gate / C: response); shows which maps changed | ✅ Generated & self-verified; not on-car tested; cat/exhaust heat caution |
| Live RAM read (dashboard shows KR/clutch/EGT via Mode23) | ✅ Client done; needs the user-applied Mode23-enable patch on the ECU |
| Live knock (Proto-Knock): knock count / magnitude / retard RAM read + dashboard tiles | ✅ RE'd (bench==car ROM); count confirmed, magnitude/retard candidates — confirm on car |
| Dashboard display modes (number / bar / gauge / graph) + smooth update | ✅ |
| Dashboard polish (OBD2monitor-style): gauge fits its tile, red alarm zone, vertical/horizontal bars, per-tile update interval | ✅ |
| Dashboard tuning: per-tile display color, scale with adjustable tick interval, graph time-window; thinner needle & smaller labels | ✅ |
| Log analysis chart (stacked time-series of a recorded log) | ✅ |
| Dashboard (gauge tiles), logging and replay | ✅ |
| Auto-generated PDF manual / full map analysis (JA / EN) | ✅ |
| **Flat-shift ignition-retard patch** (draft 3, apply and edit in the editor) | ⚠️ Emulator-verified only, **not yet tested on hardware** |

### Flashing
Writing this ECU requires an **SBL (Secondary Boot Loader)** for NC1 (flash start 0x2000, 0x1800 bytes).
The authentication, sequence (`10 85` → `27` → `B1 00 B2 00` → RequestDownload 0x8000/0xFF800 →
SBL + program → TransferExit → reset), checksum handling and block length are implemented and
hardware-verified. **No SBL is distributed with this project.** The editor's **ECU書き込み (ECU Write)** button
looks for `Decryption_sbl/sbl_nc1_flash_0x2000.bin` by default; the CLI is
`tools/flash_writeback.py` (dry run unless `--confirm`).

### Flat shift (no-lift shift)
- The stock clutch-gated throttle cut (`@0x0C53BC`, 6500 rpm) only works **below 2 km/h**
  (`@0x0C53B8`). It acts as a standstill free-rev / launch limiter, **not** as a flat shift while driving.
  (The v1.10 notes claimed otherwise; corrected in v1.20.)
- The **ignition-retard patch** (`ncecu/flatshift.py`, draft 3) subtracts a retard from the final spark
  advance — before the stock max-retard clamp — while the clutch is pressed AND APP > threshold AND
  RPM > threshold AND vehicle speed > minimum. The throttle stays open while driving.
  Defaults: 80 % / 7000 rpm / 10 km/h / 20°.
- Apply it with the editor's **Flat-shift** button, or `tools/patch_flatshift_retard.py`.
  The four values then appear in the tree under **Patch - Flat Shift Ignition Retard**
  (out-of-range input is rejected). Details: `docs/tuning_flatshift_ja.md` (Japanese).
- It changes ignition control and raises exhaust temperature. **Validate on a bench ECU first**
  (timing light, or live timing advance PID 0x0E).

---

## Requirements

- Python 3.11+ (developed on 3.14 / Windows 11)
- CAN adapter: **gs_usb family (candleLight, e.g. DSD TECH SH-C30L)**, 500 kbps, WinUSB driver via Zadig
- Dependencies: `pip install -r requirements.txt`
- GUI uses Python's built-in tkinter.

### ROM definitions (map definitions)
Map definitions use the **LibreTuner `mx5_nc` definitions (by speepsio)**. They are **not
bundled** here for licensing clarity. Download them and place `main.json` plus your
`<CALID>.json` (e.g. `LFG7EG.json`) into `defs/libretuner/`:
- https://github.com/LibreTuner/LibreTuner (`ui/resources/definitions/mx5_nc/`)

A few constants missing from that definition (the flat-shift items above) are defined in
`ncecu/flatshift.py` and shown by the editor as extra items.

---

## Install

```bash
git clone https://github.com/testbenchdev/ncec-rom-tool.git
cd ncec-rom-tool
pip install -r requirements.txt
# Put the LibreTuner mx5_nc definitions into defs/libretuner/ (see above)
python ncec_editor.py
```

## Usage (overview)

1. **Open ROM** — load your dump (`.bin`, 1 MB).
2. Pick a map in the left tree, edit cells (press Enter). Checksums are corrected on save.
3. **Live ▶** — connect to the running ECU (OBD-II / CAN) for live monitoring. Slow-changing PIDs are
   polled less often (see `DEFAULT_PID_INTERVALS` in `ncecu/livelog.py`) so fast PIDs (RPM etc.) update faster;
   **Dashboard** shows gauge tiles; **記録 ● (Record)** / **リプレイ (Replay)** for logs.
4. **Read ECU** to dump the ECU; **Compare ECU** / **Compare ROMs** for diffs.
5. **ECU書き込み (ECU Write)** to flash (spare / bench ECU recommended; SBL required).
6. **Flat-shift** (ignition-retard draft), **Anti-lag** (overrun pops; pick A/B/C), and **DBW throttle** (1:1) apply their patches to the open ROM and show which maps changed.
7. Toggle **JA / EN** with the language button; **Help** shows `docs/editor_help_ja.md`.
8. `python tools/gen_manual.py` generates a full PDF manual of every map.

## Documents (`docs/`)

| File | Content |
|---|---|
| `map_analysis.html` / `map_analysis_EN.md` | Full map analysis (English) |
| `map_analysis_JA.html` / `map_analysis_JA.md` | Full map analysis (Japanese) |
| `tuning_basics_ja.md` | Engine tuning basics for the NA LF-VE: air/fuel/spark, AFR, timing, limiters, DBW, workflow (JA) |
| `tuning_throttle_ja.md` | Throttle 1:1 (cable-like response): pedal maps, control+monitor copies, generator (JA) |
| `live_ramread_ja.md` | Live RAM read via Mode23: KR/clutch/EGT dashboard tiles, config, user-applied enable patch (JA) |
| `dashboard_chart_ja.md` | Dashboard display modes + smooth update, and the log analysis chart (JA) |
| `tuning_flatshift_ja.md` | Flat shift: stock throttle cut, spark path, ignition-retard patch, editor steps (JA) |
| `tuning_overrun_pops_ja.md` | Overrun pops / burble tuning (JA) |
| `editor_help_ja.md` | Editor help (JA) |
| `SETUP_ja.md` / `can_flash_ready_ja.md` | Setup and flash preparation (JA) |
| `PROJECT_HANDOFF_ja.md` | Project handoff / current state (JA) |

---

## License

The code in this project is released under the **GNU General Public License v3.0 (GPL-3.0)**
(for compatibility with the related projects it references). See `LICENSE`.

## Credits / References

- **LibreTuner** (https://github.com/LibreTuner/LibreTuner) — `mx5_nc` map definitions
  (by speepsio) and reference for the flash / security protocol. GPL-3.0.
- **RomDrop** (https://github.com/speepsio/romdrop) — reference for NC analysis and the
  checksum scheme.
- **nc-flash** (https://github.com/cdufresne81/nc-flash) — reference for the NC flash
  procedure / protocol.
- Renesas **SH7058 Hardware Manual** — primary source for the flash specification
  (not bundled in this repository).

This tool is a clean re-implementation based on the public information and open-source
projects above. It contains **no private IP such as the SBL**.

## Disclaimer (again)
No warranty — use at your own risk. Bench / spare ECU recommended. Compliance with road-use
and emissions law is the user's responsibility.
