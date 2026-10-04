# NCEC ROM Map Editor

An open-source **read / edit / compare / live-monitor** tool for the factory ECU of the
**Mazda MX-5 NC (chassis NCEC, LF-VE engine, Denso / Renesas SH7058 PCM)**.
A hobby / learning project aiming at a LinkECU- or Haltech-style native-reflash tuning
environment for the stock ECU.

---

## ⚠️ Disclaimer & Safety (read first)

- This software comes with **NO WARRANTY**. The author is not liable for any damage
  (ECU bricking, vehicle faults, legal violations, etc.). **Use entirely at your own risk.**
- Modifying an ECU can **destroy the engine, cause a fire, or leave the car undriveable.**
  Do not change ignition timing, fuel targets, limiters, electronic-throttle or torque
  tables unless you understand them.
- **Strongly recommended to work on a spare / bench ECU.** Compliance with road-use and
  emissions regulations is the user's responsibility — **defeating emissions controls on a
  road vehicle is illegal in most jurisdictions.**
- This repository **does not contain any ECU firmware (ROM image)** — that is Mazda's
  copyrighted work. Supply a dump read from your own ECU.

---

## Status

| Feature | State |
|---|---|
| Load ROM, edit maps by category, JA / EN UI toggle | ✅ |
| Checksum auto-correction on save | ✅ |
| Live monitoring (OBD-II) + active-cell tracking + dashboard | ✅ |
| ECU read-out (Mode 23) / ECU↔ROM and ROM↔ROM compare | ✅ |
| Auto-generated PDF manual (all maps + interactions) | ✅ |
| **Flashing (writing to the ECU)** | ⚠️ **Pending an SBL** (see below) |

### About flashing
Writing this ECU requires an **SBL (Secondary Boot Loader)**. The authentication, sequence,
checksum handling and block length are all implemented and bench-verified — the host side is
**ready to flash once an SBL is supplied**. No public tool ships the SBL (each keeps it
private). Because the SBL is transmitted in the clear over CAN during a flash, it can be
extracted from an **NC1 flash-session `candump`**. Captures / pointers are very welcome —
please open an Issue or Discussion.

---

## Requirements

- Python 3.11+ (developed on 3.14 / Windows 11)
- CAN adapter: **gs_usb family (candleLight, etc.)**, 500 kbps
- Dependencies: `pip install -r requirements.txt`
- GUI uses Python's built-in tkinter.

### ROM definitions (map definitions)
Map definitions use the **LibreTuner `mx5_nc` definitions (by speepsio)**. They are **not
bundled** here for licensing clarity. Download them and place `main.json` plus your
`<CALID>.json` (e.g. `LFG7EG.json`) into `defs/libretuner/`:
- https://github.com/LibreTuner/LibreTuner (`ui/resources/definitions/mx5_nc/`)

---

## Install

```bash
git clone https://github.com/<yourname>/ncec-rom-tool.git
cd ncec-rom-tool
pip install -r requirements.txt
# Put the LibreTuner mx5_nc definitions into defs/libretuner/ (see above)
python ncec_editor.py
```

## Usage (overview)

1. **Open ROM** — load your dump (`.bin`, 1 MB).
2. Pick a map in the left tree, edit cells (press Enter). Checksums are corrected on save.
3. **Live ▶** — connect to the running ECU (OBD-II / CAN) for live monitoring;
   **Dashboard** shows large value tiles.
4. **Read ECU** to dump the ECU; **Compare ECU** / **Compare ROMs** for diffs.
5. Toggle **JA / EN** with the language button.
6. `python tools/gen_manual.py` generates a full PDF manual of every map.

See `docs/` and the generated `docs/map_editor_manual.pdf` for details.

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
