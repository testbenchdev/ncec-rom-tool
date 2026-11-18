# NCEC ROM Tool

An open-source **read / edit / compare / flash / live-monitor** tool for the factory ECU of the
**Mazda MX-5 NC (chassis NCEC, LF-VE engine, Denso 279700-4073 / Renesas SH7058 PCM, CAL ID LFG7EG)**.
A hobby / learning project aiming at a LinkECU- or Haltech-style native-reflash tuning
environment for the stock ECU.

Current version: **2.81** (`VERSION`; change history in `CHANGELOG_ja.md`, Japanese).
日本語版: [README_ja.md](README_ja.md)

---

## ⚠️ Disclaimer & Safety (read first)

- This software comes with **NO WARRANTY**. The author is not liable for any damage
  (ECU bricking, vehicle faults, legal violations, etc.). **Use entirely at your own risk.**
- Modifying an ECU can **destroy the engine, cause a fire, or leave the car undriveable.**
  Do not change ignition timing, fuel targets, limiters, electronic-throttle or torque
  tables unless you understand them.
- **Strongly recommended to work on a spare / bench ECU.** Keep your original read-out
  (ROM images live in the `rom_data/` folder). Do not cut power while flashing (about 10 minutes on Windows, about 1 minute under WSL2).
- Compliance with road-use and emissions regulations is the user's responsibility —
  **defeating emissions controls on a road vehicle is illegal in most jurisdictions.**
- This repository **does not contain any ECU firmware (ROM image), SBL, or the Renesas manual.**
  Supply a dump read from your own ECU.

---

## Status

| Feature | State |
|---|---|
| Load ROM, edit maps by category (LibreTuner definition, 922 tables), JA / EN UI. **Search by name or by an address starting with `0x`** (v2.71) | ✅ |
| Checksum auto-correction on save | ✅ |
| **Split view** (single / 2 side by side / 2 stacked / 3 / 4 panes; drag the borders; tables can also open in **separate windows**). Fixed axis headers. Layout, tables, zoom and windows are restored next time (v2.80) | ✅ |
| **Control and monitor side by side** (⇔ shows the paired copy next to it with the same selection; equal/different status and red marks on differing cells). **Paired editing** (on by default) writes both copies (v2.80) | ✅ |
| **Table editing**: range selection, typing into many cells, increment (small/large), set / add / % / multiply, horizontal / vertical / 2D interpolation along the axis values, smoothing, fill down/right, copy/paste with spreadsheets, revert to saved, **undo/redo** (patches included), marks on cells changed since saving, selection average/min/max (v2.80) | ✅ |
| **Configurable keyboard shortcuts** (Settings → Keyboard shortcuts…; about 60 actions, defaults close to commercial engine-management software; ECU flashing has none) (v2.80) | ✅ |
| Editor and dashboard **remember their window size and position** (including maximised; off-screen positions are ignored) (v2.80) | ✅ |
| Under WSL (WSLg) right-click menus are **drawn inside the window** (WSLg shows a separate menu window late: it flashes on an outside click and lingers about 1 s after closing). Submenus fold out, long lists use columns; Windows keeps native menus (v2.81) | ✅ Checked with real clicks on WSLg |
| Every table description (dimensions, axes, type, unit) checked against the ROM and the code (v2.71 addendum): 439 tables with axes match the ECU's own table descriptors; the 23 control/monitor pairs show each other's address. The formerly unconfirmed tables were reverse-engineered (closed-loop target = enrichment %, fan timers = 25 ms / 100 ms counts, the 12 DBW tables = anti-jerk filters etc.). The axis input RAM (this ROM's real address, 275 tables) is shown, and RAM-address search uses it | ✅ |
| ECU read-out (UDS 0x23, no SBL needed) / ECU↔ROM and ROM↔ROM compare | ✅ |
| **Flashing over CAN** (SBL model) | ✅ Verified on a bench ECU and in the car via the OBD-II port — **SBL not included; you must supply it** |
| Live monitoring (OBD-II Mode 01) + DTCs + active-cell tracking on maps (map following); RAM block-reads + conditional flush give **30–40 Hz on the bench**. **Map following uses absolute load (PID 0x43) only** (v2.71; calculated load used to leak in and shift the row) | ✅ |
| Live decimation (slow signals polled less often). **Duplicate signals (calculated load, pedal sensor E, brake switch 2) are not read by default**; signals that are axes of the open map are always read; live RAM is limited to two blocks per cycle (v2.71) | ✅ Verified by scheduler simulation; update rate not yet measured on hardware |
| Configure intervals in the GUI (Settings → Live PID intervals). One list for every signal: **Every cycle / 0.1 s / 0.2 s / 0.5 s / 1 s / 2 s / 5 s / 10 s / Ignore** (unified in v2.71; the dashboard uses the same list) | ✅ |
| DBW throttle 1:1 tool (cable-like pedal map; edits control + monitor copies; editor **DBW throttle** button) | ✅ Generated & self-verified; on-car effect not yet tested |
| Anti-lag (overrun pops/burble) patch — Settings → Apply patch → Anti-lag (**A: DFCO off / B: RPM gate / C: RPM gate + response, DFCO on / D: response, DFCO off**; **B and C take an active rpm of 1500–6000**); shows which maps changed | ✅ Generated, self-verified and emulator-verified; not on-car tested; cat/exhaust heat caution |
| **Faster rev-drop (rev-hang) patch** — editor **Faster rev drop** button; speeds the upshift rev-drop by engaging decel fuel cut (DFCO) sooner/harder. **Fuel-side only, throttle untouched = independent of the E-Gas monitor.** enter-count `0xC477D` + enlean rates `0xCC774` etc.; presets mild/strong | ✅ Generated, static + sh2emu verified; not on-car tested (staged bench) |
| Idle target (Idle Speed - Base): **edit the maps directly**, control and monitor copies to the same values (the patch was removed in v2.71) | ✅ |
| **°C conversion for the cooling-fan coolant thresholds** (the values are ECT-sensor A/D counts, not °C; opening a table shows "current value = switches at … °C", the formula and a guide table; the unit is shown as A/D) | ✅ From disassembly; the A/D-to-°C conversion and the 1 ms / 25 ms task periods were confirmed on the car (2026-11-17); the fan start temperature itself is not measured yet |
| Live RAM read via Mode23 (clutch `0xFFFF7100`, decel status, KR, EGT, knock, **gate APP `0xFFFF56C8`**, **injector pulse width `0xFFFF7380`** + derived **duty %**); clutch/decel/IPW confirmed on-car via `tools/ram_diff.py` and drive logs | ✅ Client done; needs the user-applied Mode23-enable patch on the ECU |
| Live knock: **knock level `0xFFFF4E20`** and **KR (knock retard) `0xFFFF7C44`** via Mode23 + dashboard tiles | ✅ KR confirmed against car logs (+1.7° then −0.17° per event, matching the calibration); the level is on an internal scale |
| Dashboard display modes (number / bar / gauge / graph) + smooth update | ✅ |
| Dashboard polish (OBD2monitor-style): gauge fits its tile, red alarm zone, vertical/horizontal bars, per-tile update interval | ✅ |
| Dashboard tuning: per-tile display color, scale with adjustable tick interval, graph time-window; thinner needle & smaller labels; **bar-graph tick labels for RPM etc. shown 1-digit (×1000)** | ✅ |
| Log analysis chart (stacked time-series of a recorded log) | ✅ |
| Dashboard (gauge tiles), logging and replay | ✅ |
| **Integrated manual (HTML with table of contents, JA / EN)**: setup, usage, tuning, flashing, analysis and the full map analysis in one document (rebuilt by `tools/build_docs.py`); auto-generated PDF manual | ✅ |
| **Flat-shift patch** (final design: **read-only — no RAM/register writes**; selectable ignition retard / cut; active only *while* clutch `0xFFFF7100` + APP + RPM + VSS gates hold; `test_mode` for standstill checks) | ✅ **Both methods confirmed on the car (2026-11-01)**; flashing the car's own ECU not advised — use a bench/spare ECU |
| ROM images are kept in `rom_data/` (default location for save / read-out / compare; the start-up ROM and the security-key computation also read from it; copyright ROM — excluded from git) | ✅ |
| Other-PC support: auto-inject the bundled `libusb-package` DLL into pyusb's default backend (avoids `NoBackendError`; no admin / PATH changes) | ✅ Verified on old & new PCs |

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
- The **flat-shift patch** (`ncecu/flatshift.py`, final design) is **read-only — it writes nothing to
  RAM or registers**. No fixed scratch RAM, no hard-timer window (the v2.50 window/scratch approach was
  dropped because the car has no stable free RAM visible over Mode23). Having no writes removes the
  main bricking risk.
- It is active **only *while* clutch `0xFFFF7100` = 1 AND APP > threshold AND RPM > threshold AND vehicle
  speed > minimum**. The "window" is how long you hold the clutch (driver-controlled); the RPM threshold
  acts as an upper limit. Releasing the clutch ends it. The throttle stays open while driving.
- **Selectable method** (CAL `method`): **0 = retard** (subtract degrees from the final advance, plus a
  variable floor for deeper-than-stock retard) or **1 = cut** (repoint the coil-charge handler to skip
  charging = no spark).
- **`test_mode=1`** ignores the vehicle-speed gate only (clutch + RPM + APP still apply) for standstill
  checks; a manual-start clutch press won't cut ignition because RPM is too low to pass the gate.
- CAL at `0xDE300`–`0xDE318`: `app/rpm/vss/retard/floor` (float) + `method/test_mode` (u32).
  Defaults: APP 80 % / 7000 rpm / 10 km/h / retard 20° / cut floor −10° / method 0 / test_mode 0.
- Apply it with the editor's **Flat-shift** button (dialog for method/gates/test_mode, shows what
  changed), or `tools/patch_flatshift_retard.py`; the values then appear in the tree under
  **Patch - Flat Shift** (out-of-range input is rejected). Standstill check: `tools/flatshift_debug.py`
  (reads the written config over Mode23 and evaluates the gate live). Details and the on-car test procedure:
  `docs/tuning_flatshift_ja.md` (JA).
- **Confirmed on the car (2026-11-01)**: retard drops the timing advance (PID 0x0E) by ~20° while active;
  cut leaves timing unchanged but λ (PID 0x34) goes lean, battery voltage holds (charge skipped), and RPM
  caps near the threshold. Both methods work on real hardware.
- It changes ignition control and raises exhaust temperature (especially cut). Keep it brief and
  **validate on a bench / spare ECU first** (timing light, or live timing advance PID 0x0E). Do not flash
  the car's own ECU.

### Faster rev-drop (rev-hang reduction)
- Speeds the rev-drop when you lift on an upshift (engine free-spinning with the clutch in), using
  **decel fuel cut (DFCO) only** — the electronic throttle is never touched, so it is independent of the
  E-Gas L2 monitor (the opposite "reduce" direction to a blip, which the monitor rejects).
- Main lever: **lower the decel enter-count `0xC477D` (stock 30)** so fuel cuts sooner on lift. Secondary:
  raise the enlean rates `0xCC774` (6×5) / `0xCC694` / `0xCC698` / `0xCC6A0` to reach full cut faster. The
  **anti-stall floor `0xC47FC` (2312.5 rpm) and the fuel-restore thresholds are left stock**, so the stall
  protection is unchanged.
- Apply with the editor's **Faster rev drop** button (presets off/mild/strong, or custom), or
  `tools/patch_revdrop.py`. The default is inert (stock-equivalent). It reuses the same addresses as
  `ncecu/antilag.py` in the opposite direction, so **only one of the two per ROM**. See `docs/revdrop_ja.md` (JA,
  including the staged bench procedure).

### Anti-lag (overrun pops)
The engine is naturally aspirated, so this makes sound only. Fuel burns in the exhaust: mind catalyst and exhaust heat.

| | Name | DFCO | Active | Retard | Tip-in recovery |
|---|---|---|---|---|---|
| **A** | DFCO off (burble at all RPM) | off | all RPM | deep (~22°) | stock |
| **B** | RPM gate (recommended) | **on** | above the active rpm | 20° | stock |
| **C** | RPM gate + response (new in v2.71) | **on** | above the active rpm | shallow (12°) | fast |
| **D** | Response, DFCO off (the "C" of v2.70 and earlier) | off | all RPM | shallow (12°) | fast |

- **Active rpm (B and C)**: 1500–6000 rpm in steps of 100, default 3000. The patch moves the breakpoints of the
  RPM axis `0xCC748` of the decel fuel-cut table `0xCC774`. Below the active rpm the fuel cut works normally
  (silent); pops fade in above it and are fully active 1000 rpm higher. With the default the axis stays stock,
  byte-identical to pattern B of v2.70.
- Verified by running the ECU's own table look-up (`0x20DC`) in the emulator; **not tested on the car**.

### Idle target — edit the maps directly
- The idle-speed patch was removed in v2.71. Edit **Idle Speed - Base** in the tree.
- In gear: control `0xD6C9C` / monitor `0xF4DEC`. Not in gear: control `0xD6CDC` / monitor `0xF4E2C`.
  Typing an address such as `0xD6C9C` in the search box opens the table.
- **Always set the control and monitor (Data Integrity) copies to the same values**; editing one side only can fault.
- Leave the slew rate (`0xD6AB8` family) alone: the monitor protects it (DTC P0606 and limp mode seen on the car).

### Cooling-fan temperatures — the values are A/D counts, not °C
- The coolant thresholds under **Engine Fan Control** (medium/high activation and deactivation at `0xBF9F8`–`0xBF9FE`,
  plus the six after-cooling tables) are 10-bit A/D counts of the ECT-sensor voltage (volts = value × 5 ÷ 1024).
  **A larger value means a lower temperature**, so raising it starts the fan earlier.
- Opening one of these tables shows the °C conversion in the description area (what temperature the current value
  switches at, the formula and a guide table); it updates when you commit a value.
- Car stock: medium ON at 100 °C, high ON at 108 °C. Bench-ECU original and the in-use ROM: 90 °C / 96 °C (about 10–12 °C earlier).
- Guide: 85 °C ≈ 143, 90 °C ≈ 125, 95 °C ≈ 109, 100 °C ≈ 96, 105 °C ≈ 84, 110 °C ≈ 74. Keep the activation value below the deactivation value.
- Derived from disassembly. The A/D-to-°C conversion matched the ECU's own coolant value on the car (2026-11-17, key on), but the temperature at which the fan actually starts has not been measured yet. See manual section 8.6.

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
2. Pick a map in the left tree, edit cells (type a number, press Enter). Checksums are corrected on save.
   The **View** menu splits the table area (Ctrl+1–5), opens separate windows and shows the paired control/monitor
   table; the **Edit** menu (or right-click) has interpolation, smoothing, % change etc. and undo (Ctrl+Z).
   Keys can be changed in **Settings → Keyboard shortcuts…**.
3. **Live ▶** — connect to the running ECU (OBD-II / CAN) for live monitoring. Slow-changing PIDs are
   polled less often (see `DEFAULT_PID_INTERVALS` in `ncecu/livelog.py`) so fast PIDs (RPM etc.) update faster;
   **Dashboard** shows gauge tiles; **記録 ● (Record)** / **リプレイ (Replay)** for logs.
4. **Read ECU** to dump the ECU; **Compare ECU** / **Compare ROMs** for diffs.
5. **ECU書き込み (ECU Write)** to flash (spare / bench ECU recommended; SBL required).
6. **Settings → Apply patch**: **Flat-shift** (final design, read-only: cut/retard method + clutch/APP/RPM/VSS gate + test_mode), **Anti-lag** (overrun pops; A–D, with an active rpm for B and C), **Faster rev drop** (speed the upshift rev-drop via DFCO, fuel-side only) and **DBW throttle** (1:1) apply their patches to the open ROM and show which maps changed. The idle target is edited directly in the maps.
7. Toggle **JA / EN** with the language button; **Help** shows the built-in help and opens the integrated manual (HTML).
8. `python tools/build_docs.py` rebuilds the integrated manual (HTML); `python tools/gen_manual.py` generates a full PDF manual of every map.

## Documents (`docs/`)

**Open `docs/map_analysis.html` (the integrated manual) in a browser first.** It has a table of contents and holds
the English manual plus the full map analysis with flowcharts. The Japanese edition, `docs/map_analysis_JA.html`,
is the complete one.

| File | Content |
|---|---|
| **`map_analysis.html`** / **`map_analysis_JA.html`** | **Integrated manual (English / Japanese)**, rebuilt by `tools/build_docs.py` |
| `manual_EN.md` | Source of the English manual (condensed) |
| `SETUP_ja.md` / `setup_wsl_ja.md` | Setup on Windows / WSL2 setup for fast flashing (JA) |
| `editor_help_ja.md` | Editor help, same as the in-app help (JA) |
| `dashboard_chart_ja.md` / `live_ramread_ja.md` | Dashboard and log chart / live RAM read (Mode23) and knock display (JA) |
| `tuning_basics_ja.md` | Tuning basics: reading load, timing, AFR, editing the idle target, cooling-fan temperatures (JA) |
| `tuning_flatshift_ja.md` | Flat shift: design, settings, on-car test procedure (JA) |
| `tuning_overrun_pops_ja.md` | Anti-lag (overrun pops) A–D and the active rpm (JA) |
| `revdrop_ja.md` | Faster rev-drop (DFCO) and the staged bench procedure (JA) |
| `tuning_throttle_ja.md` | Throttle 1:1 (JA) |
| `flash_ja.md` | Flashing: procedure, timings, recovery after a failed flash (JA) |
| `knock_re_ja.md` / `table_audit_ja.md` / `diag_findings.md` / `SH7058_hardware_notes.md` / `unit_fixes_i18n.md` | Analysis and reference: knock control, definition audit, diagnostic protocol, hardware, unit fixes |
| `map_editor_manual.pdf` / `map_editor_manual_EN.pdf` | PDF manual of every map — not in the public repository because it contains ROM values; build it locally with `python tools/gen_manual.py` |
| `ecu_diff_report.html` | Diff report: car ECU vs bench ECU (JA) — local only, not in the public repository (contains ROM values) |
| `map_notes.json` | Per-category notes data (used by the PDF manual) |

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
