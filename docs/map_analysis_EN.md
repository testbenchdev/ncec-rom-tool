# NCEC ECU Map Analysis — Consolidated Notes (English)

**Scope:** Reverse-engineering notes for a spare Mazda NCEC (Roadster / MX-5) ECU — Renesas SH7058, CAL ID **LFG7EG**.
**Base ROM:** `ncec_rom_dump.bin` · **Definitions:** LibreTuner (LFG7EG) · **Coverage:** all **124 categories / 875 tables** investigated.

> ⚠️ These notes are based on **reading values/units from one bench ECU**. **No flashing was performed** (no SBL obtained, so writing is not possible). Numbers are the as-read calibration of this single unit and may differ on other units/CAL IDs.
>
> See `unit_fixes_i18n.md` for the list of unit-label fixes applied to `ncecu/i18n.py`. A table marked 🔧 below had a unit fix.

---

## Table of Contents

1. [Fuel — Target AFR](#a-fuel--target-afr) (5)
2. [Fuel — Compensation / Injection / Status](#b-fuel--compensation--injection--status) (38)
3. [Spark — Correction](#c-spark--correction) (14)
4. [Spark — Base / Limit](#d-spark--base--limit) (10)
5. [Spark — Idle / Limit Correction](#e-spark--idle--limit-correction) (8)
6. [Variable Cam Timing (VVT)](#f-variable-cam-timing-vvt) (2)
7. [Intake (IMRC / IMTV)](#g-intake-imrc--imtv) (2)
8. [Drive-by-Wire Throttle](#h-drive-by-wire-throttle) (4)
9. [Idle Speed Control](#i-idle-speed-control) (3)
10. [Data Integrity / Monitoring](#j-data-integrity--monitoring) (15)
11. [Diagnostics (DTC)](#k-diagnostics-dtc) (2)
12. [Limiters (RPM / VSS / Load)](#l-limiters-rpm--vss--load) (5)
13. [Patches (Code)](#m-patches-code) (6)
14. [Sensors / Vehicle](#n-sensors--vehicle) (7)
15. [WIP / Misc](#o-wip--misc) (1)
16. [Other (Emissions / Fan / Gear Ratio)](#other-emissions--fan--gear-ratio) (5)

Format: **Category** (table count) — role. *Units/notes.*

---

## A. Fuel — Target AFR

- **Fuel Target CL - Base (no patch required)** (1) — Closed-loop target AFR base map (λ, RPM×Load). CL normally targets stoich (λ1). *Values 0.021–1.3 rise with load (opposite of a plain stoich target), so this may be a weight/blend coefficient or a different scale; left as labeled (λ). Not a normal tuning target.*
- **Fuel Target CL - Base (requires patch)** (3) 🔧 — Free-settable closed-loop target AFR that becomes active after the base patch is applied (Stoich AFR / idle & non-idle targets). *Unit AFR. Unpatched unit runs factory stoich (~14.57).*
- **Fuel Target CL - Base Patch** (2) — Patch toggle (applied / not-applied markers) that rewrites ROM code rather than a calibration value.
- **Fuel Target OL - Base** (4) — Core open-loop (power-enrichment) map: how much richer than stoich at high load/WOT. *Value = % enrichment over stoich (0 = stoich, up to ~36% rich); 4 sheets by 2 conditions.*
- **Warm-Up Fuel Target OL - Base** (11) — Cold-enrichment (open-loop) warm-up targets: richer when cold for post-start stability / catalyst light-off, returning to normal as it warms.

---

## B. Fuel — Compensation / Injection / Status

- **Fuel Comp CL - Decel Recovery** (3) — On return from fuel cut to closed loop, applies a brief enrichment then decays to zero to prevent a lean spike. *% correct.*
- **Fuel Comp CL - RO2S Emissions Monitor No Activity Check** (2) — OBD monitor for rear-O2 sensor activity (detects dead/stuck sensor, P013x). *% correct.*
- **Fuel Comp CL - RO2S Trim (ZERO)** (2) 🔧(none) — Rear-O2-based fuel trim path, both **zeroed/disabled** on this unit. *×/% correct; no unit change — rear O2 is used only for cat-efficiency trims here.*
- **Fuel Comp CL - STFT Correction Coefficients** (4) — Short-term fuel trim control gains/bias defined per airflow (MAF) zone.
- **Fuel Comp CL - STFT Transition Delay** (2) — Delay before STFT begins/changes state under certain conditions. *Value = delay count/time.*
- **Fuel Comp CL - Transition to Closed Loop** (5) — Conditions/limits for switching from open loop (start/power) to closed loop (O2 feedback).
- **Fuel Comp CL - Warm Up Cat Efficiency Check RO2S Trim** (3) — Rear-O2 fine-trim paired with the cat-efficiency dither monitor.
- **Fuel Comp CL - Warm-Up Cat Efficency Check** (4) — OBD catalyst-efficiency monitor (P0421): ECU deliberately dithers AFR to gauge O2 storage. *× and % correct.*
- **Fuel Comp OL - Corrective Spark Enrichment** (6) — Protective enrichment to cool when spark is heavily retarded. *Activation (RPM/Load/cat-temp) + enrichment amount.*
- **Fuel Comp OL - Decel Fuel Cut** (6) — On DFCO entry, leans out gradually instead of cutting abruptly. *All × (ratios) correct.*
- **Fuel Comp OL - Decel Fuel Restore** (7) — Returns fuel after DFCO via an enrichment rate for a smooth, shock-free transition. *Rate = ×, enrichment = %.*
- **Fuel Comp OL - Decel Fuel Restore Idle Thresholds** (20) — Restore-fuel decision near idle: ECU estimates idle RPM and restores before RPM falls through to prevent stall.
- **Fuel Comp OL - Power Enleanment** (22) — Factory-active power-enleanment: after initial enrichment at high load, leans slightly once warm for economy/temperature (up to ~14% lean). *Active on this unit; 4 groups.*
- **Fuel Comp OL - Power Enleanment (OEM Bypassed)** (10) — The OEM-bypassed variant; values make it never activate here (effectively off).
- **Fuel Comp OL - Start-Up Enrichment (Catalyst)** (26) — Post-cold-start enrichment (with spark retard) to heat exhaust for fast catalyst light-off, decaying over time. *% / ×; X = ECT °C. 2 banks × ECT × base/decay + IMRC factor.*
- **Fuel Comp OL/CL - IMRC Transition** (4) 🔧(none) — Transient enrichment to cover the VE change when the IMRC intake switches by RPM. *% reasonable; TP-threshold reset disabled (999 sentinel); no unit change.*
- **Fuel Comp OL/CL - Increasing Load Enrichment** (15) — Transient (wall-wetting) enrichment on sudden load increase (tip-in). *Trigger (load delta) + amount (%, by ECT) + decay rate; 4 systems.*
- **Fuel Comp OL/CL - LTFT** (5) — Long-term fuel trim: learns the average STFT offset to absorb steady errors (injector aging, MAF drift).
- **Fuel Comp OL/CL - LTFT MAF Breakpoints** (12) — Airflow-zone boundaries (g/s) that split LTFT learning (6 breakpoints + hysteresis).
- **Fuel Comp OL/CL - MAF Thresholds WIP** (2) — WIP: airflow thresholds that disable rear-O2 trim.
- **Fuel Comp OL/CL - Radiant Intake Heat** (1) 🔧(none) — Hot-restart / hot-idle enrichment to prevent heat-soak lean stumble. *0–10%, correct.*
- **Fuel IPW - Base** (1) — Base injector pulse-width reference constant. *10.492 ms.*
- **Fuel IPW - Cranking** (4) — Cranking (start) injection calibration.
- **Fuel IPW - Dynamic Trim Mult A (Large)** (6) — Transient (wall-wetting) compensation, "large/slow bulk" coefficients. *× correct.*
- **Fuel IPW - Dynamic Trim Mult B (Small)** (6) — Transient compensation, "small/fast" coefficients (2×3 like A). *× correct.*
- **Fuel IPW - Dynamic Trim Mult C** (2) — Transient wall-wetting coefficient set C, scaled by ECT. *× correct.*
- **Fuel IPW - Minimum** (1) — Minimum injector pulse-width clamp. *0.803 ms (flat).*
- **Fuel IPW - Offset and Scaling** (7) — Injector characterization (dead-time + flow scaling); the key set when swapping injectors.
- **Fuel Status OL (Primary) - APP** (4) — CL→OL (power) transition decided by pedal (primary condition).
- **Fuel Status OL (Secondary) - APP** (3) — Secondary pedal trigger. *% correct.*
- **Fuel Status OL (Secondary) - Load** (7) — CL→OL transition by engine load (secondary): load thresholds per RPM for normal/high-knock/high-ECT.
- **Fuel Status OL - Decel** (6) — State transitions for decel fuel cut (overrun DFCO).
- **Fuel Status OL Delay Reset (Secondary)** (8) — Thresholds and reset values that reset the delayed-OL counter.
- **Fuel Status OL Delay Reset (Secondary) - Load** (2) — Load version of the delay reset. *Load = unitless, correct.*
- **Fuel Status OL Delay Reset (Secondary) - RPM** (2) — RPM version of the delay reset. *rpm correct.*
- **Fuel Status OL Delayed (Secondary) - Catalyst Temp** (4) — Catalyst-temperature condition for delayed OL. *°C correct; uses estimated cat temp.*
- **Fuel Status OL Delayed (Secondary) - RPM** (4) — RPM window for delayed secondary OL. *rpm correct.*
- **Fuel Status OL Delayed (Secondary) - TD** (2) — Throttle-duty condition for delayed OL. *% correct.*

---

## C. Spark — Correction

- **Spark Comp - Cold Advance** (9) 🔧 — Cold advance for combustion stability / warm-up (ECT, or ECT×Load). *Fix: "Add Timer" °→unitless (timer, not angle); "Add Retard Rate | Timer Expired" kept ° (°/cycle rate).*
- **Spark Comp - EGR Advance** (4) — With EGR flowing, combustion slows so timing can be advanced without knock for economy. *Advance map (RPM×Load) × actual/target EGR ratio multiplier.*
- **Spark Correction - Feedback WIP (AT)** (1) — Max clamp for AT feedback spark retard. *39.73°. WIP.*
- **Spark Correction - High ECT Spark Corection WIP (AT Only)** (10) — 10 scalars (Index 0–9 array) of spark correction (°) for high-ECT, AT only. *Curve 1→10→20→…→0. WIP; sign depends on caller. ("Corection" is a source typo.)*
- **Spark Correction - High RPM and ECT** (8) 🔧 — Retard to avoid heat/knock when both RPM and ECT are high. *Fix: RPM Threshold[/Hys] °→rpm, ECT Threshold[/Hys] °→°C. Rate/Limit=0 here (effectively inactive).*
- **Spark Correction - Knock Retard** (16) 🔧 — Knock-sensor-based retard (KR): defines listen window, accumulates retard on knock, restores advance when clear. *Fix: load °→unitless, rpm °→rpm, delay °→unitless; KR amount/max/rate kept °.*
- **Spark Correction - Stumble Recovery** (1) — MT, neutral, idle, ECT ≥70 °C: adds advance (up to +10°) when load spikes (stumble) to add torque and prevent stall.
- **Spark Correction - Tip-In Anti Lug** (9) 🔧 — Retard to prevent lugging on low-RPM/high-gear tip-in. *Fix: Minimum RPM Threshold °→rpm (anti-lug-scoped).*
- **Spark Correction - Tip-In First Gear** (11) — Tip-in retard in 1st gear (more aggressive than From-Stop); base retard × TP/RPM/IAT multipliers. *AT variants zeroed.*
- **Spark Correction - Tip-In From Stop** (5) — Tip-in retard from a stop to smooth torque onset. *Base retard (A/C off 11°, on 6.5°) + ramp-in/out multipliers (VSS-dependent decay).*
- **Spark Correction - Tip-In High Speed** (10) 🔧 — Tip-in retard at high vehicle speed (X = sub-RPM). *Fix: Delay °→unitless, APP Increasing/Decreasing °→× ; Base Retard=°, Multiplier=× kept. Delay/Base all 0 here.*
- **Spark Correction - Tip-In Shared** (3) — ECT-based multiplier gate shared by all tip-in retard maps. *MT active above ~80 °C; AT zeroed.*
- **Spark Correction - Transition from Decel** (9) — Spark control returning from decel/fuel-cut to accel: retard to limit a torque step, then restore advance. *Base Retard + Restore Advance Rate.*
- **Spark Correction - Transition from In-Gear to Idle** (5) 🔧 — Spark control when dropping from in-gear to idle (retard to curb flare). *Fix: Transition Timer Reset °→unitless; Retard Limit/Rate=°, Multiplier=× kept.*

---

## D. Spark — Base / Limit

- **Ignition Coil Dwell Time** (3) — Coil charge (dwell) time [ms]; longer = stronger spark but more heat/current. *Falls with RPM, rises at low battery voltage.*
- **Spark Base - High Fuel Request** (4) — Base ignition advance map used in high-fuel-request (high-load/rich) regions. *RPM×Load, °BTDC. ° all correct (no fix needed).*
- **Spark Base - High Fuel Request Transition** (3) 🔧 — Boundary conditions that switch between low/high fuel-request base maps (not advance values). *Fix: fuel-request thresholds → (Lambda)→λ, (%)/hysteresis→%, delay→unitless; so #2→%, #3→unitless.*
- **Spark Base - Low Fuel Request** (4) — Base ignition advance for low-fuel-request (lean/cruise). *RPM×Load, °BTDC.*
- **Spark Base / Idle Transition** (3) 🔧 — Conditions switching the spark map between idle and running-base. *Fix: RPM Threshold °→rpm, Enrichment Threshold °→% (start-up enrichment is %).*
- **Spark Base Comp - ECT / IAT Combined** (6) — Temperature correction added to base advance (avoids misfire/knock when cold/hot). *Temp→correction map × operating-point scale × apply rate.*
- **Spark Base Limit** (4) — Upper clamp (ceiling) on total ignition advance after all corrections. *RPM×Load, °BTDC.*
- **Spark Base Limit Comp - Power** (3) 🔧 — High-load override/relax of the advance ceiling tied to fuel power-enleanment set/clear. *Fix: 3× %→° (condition clause misfired into % block). All 0 here (inactive).*
- **Spark Limits** (11) — Final clamps (advance ceiling / retard floor) on the final spark timing for safety/driveability. *°; e.g. Max Advance +50°, fault default 9.86°, retard floors −13.5 to −27.75°.*
- **Spark To Cylinders** (5) — Final stage distributing timing to each cylinder. *Attack-rate limiter 5°/update + per-cylinder trims (all 0 = even).*

---

## E. Spark — Idle / Limit Correction

- **Spark Idle / Base Limit - Transition** (3) — Slew rate (°/cycle) blending the two advance-ceiling maps (idle vs running base).
- **Spark Idle / Base Limit Correction - Special Warm-Up WIP** (14) 🔧 — Experimental warm-up control of the idle/base advance ceiling (WIP). *Fix: "Warm-Up Fuel Target" unitless→° (advance target ~18°); scoped to this WIP category.*
- **Spark Idle Limit** (2) — Advance ceiling available to the idle governor (real spark advance °, X=idle RPM / Y=idle load).
- **Spark Idle Limit Correction - AC Cycle Transition** (3) 🔧 — Spark correction to absorb idle disturbance when the A/C clutch cycles. *Fix: "Duration" °→unitless (hold time/count); also fixes PS-cycle Duration; "Value" (advance°) kept.*
- **Spark Idle Limit Correction - Idle Error** (8) — Governor advance vs idle-speed error (±rpm): add advance if under target, retard if over. *Multiple systems by condition.*
- **Spark Idle Limit Correction - PS Cycle Transition** (9) — Spark correction absorbing idle disturbance when power-steering pressure switch cycles.
- **Spark Idle Load - Alternator Compensation** (2) — "Decrement (release)" side of the alternator idle-load comp: decays the added load back to 0 when actual charging exceeds command.
- **Spark Idle Load - PSP Compensation** (6) 🔧 — Power-steering idle-load additive amount (pairs with the DI PSP water-temp gate). *Fix: Numerator/Divisor/Divisor Sub °→unitless (dimensionless constants); multipliers kept ×.*

---

## F. Variable Cam Timing (VVT)

- **Variable Cam Timing - Base** (3) 🔧 — VVT (intake cam phase) activation condition and target angle. *Fix: ECT Threshold/Hysteresis °→°C (poisoned by "cam timing"); VCT Target kept ° (cam angle). Activate ≥63 °C (hys 5 °C); target 0–25°.*
- **Variable Cam Timing - DO NOT MODIFY** (12) 🔧 — Internal VVT control (crank→cam sync offset, error gains/correction, OCV). Factory ID values — do not modify. *Fix: RPM Threshold[/Hys] °→rpm; Correction to Apply °→unitless (−600..400 isn't cam angle). Multipliers=×, CKP/CMP Offset=°, OCV=% kept.*

---

## G. Intake (IMRC / IMTV)

- **Intake Manifold Runner Control (AT Only)** (16) 🔧(axis) — LF-VE variable intake runner control, AT-only switching logic (when to switch = exit threshold; how fast = transition). *Axis fix only: X aliased to "IMRC transition progress (%)"; unit_of unchanged (°C/rpm/%, Load/Divisor/Bias unitless).*
- **Intake Manifold Tuning Valve** (6) — IMTV resonance/tuning valve; opening links a secondary intake path to optimize charging. *Primary (high-RPM) + secondary (mid-RPM, throttle) open conditions.*

---

## H. Drive-by-Wire Throttle

- **DBW - Cruise Control** (17) — PI-control tables holding vehicle speed via electronic throttle. *Input is mainly set-speed error (km/h); values −16..+16 are the error, not absolute speed.*
- **DBW - Throttle Angle Commanded Conversion** (2) — Internal % ↔ angle(°) conversion between ECU command (%) and the throttle body / feedback (degrees).
- **DBW - Throttle Duty Desired** (1) — Special-condition pedal→throttle map (brake on, VSS < 2 km/h, AT). *% (throttle duty); near 1:1 with a low-pedal deadband. WIP.*
- **DBW - Throttle Duty Desired Comp - Aggregate** (5) — Estimated airflow (volumetric/mass) that the control side defines/clamps as input to the aggregate throttle-duty correction.

---

## I. Idle Speed Control

- **Idle Speed - Base** (1) — Actually Idle Speed **Max**: upper clamp on target idle (2000 rpm) so corrections can't run idle away. *rpm.*
- **Idle Speed Comp** (4) — Decay rate (rpm/cycle) that ramps the start-up idle bump back to zero after start.
- **Idle Transition Delay** (10) — Delay before declaring the idle state when the pedal is released, plus reset conditions (ECT>75 / VSS>20 / gear>1.5 / TD), preventing premature idle entry. *Units already correct (no "comp" contamination).*

---

## J. Data Integrity / Monitoring

- **Data Integrity** (overview) — ECU fail-safe layer: dual-check of DBW throttle and torque, i.e. the standard drive-by-wire "torque monitoring" (EGAS / E-Gas Level-2).
- **Data Integrity Checks - DBW Throttle Duty Commanded Limits** (3) — Clamps/monitors the final commanded throttle duty vs pedal plausibility. *X=APP 0–100%, 1×9.*
- **Data Integrity Checks - DBW Throttle Duty Desired** (8) — Monitor-side copy of the pedal→desired-throttle map (by gear etc.) for plausibility checking.
- **Data Integrity Checks - DBW Throttle Duty Desired + Comp to Torque Request** (4) — Converts commanded throttle to a *requested torque* and cross-checks the main torque structure. *Torque expressed as BMEP in **kPa** (per "in kpa" in the name), not N·m.*
- **Data Integrity Checks - DBW Throttle Duty Desired Comp - Aggregate** (3) — Back-calculates the expected throttle-duty correction from estimated airflow to monitor the desired duty.
- **Data Integrity Checks - Idle Speed - Base** (2) — Monitor-side copy of target base idle RPM. *rpm.*
- **Data Integrity Checks - Idle Speed Comp** (8) — Monitor-side copy of the start-up idle bump (decays over time).
- **Data Integrity Checks - Spark Idle Load - AC Comp** (4) 🔧 — Idle-load addition when the A/C compressor engages. *Fix: °→unitless (load); block extended by category ("spark idle load - ac comp").*
- **Data Integrity Checks - Spark Idle Load - Alternator Comp** (6) 🔧 — Idle-load top-up for alternator (charging) load. *Fix: °/%→ Estimated MAF Add g/s, others unitless; +2 non-DI decrement-rate tables unitless.*
- **Data Integrity Checks - Spark Idle Load - Base** (2) 🔧 — Reference engine load targeted by the idle spark governor. *Fix: °→unitless (0.135–0.5 is load, not advance).*
- **Data Integrity Checks - Spark Idle Load - PSP Comp** (1) — Power-steering comp water-temp scale (gate) multiplier. *×.*
- **Data Integrity Checks - Spark Idle Load - VSS Comp** (5) 🔧 — Vehicle-speed correction to idle spark load (active only near standstill). *Fix: #1–4 °/km/h→unitless; added guard so "vss threshold"→km/h excludes spark-idle-load; #5 × kept.*
- **Data Integrity Thresholds - DBW Throttle Duty Target** (2) — Dual-compute monitor: if the two desired-throttle-duty values differ beyond threshold, set DTC P0601 and go fail-safe. *% (throttle duty); normal 5.6–22%, cruise 90% (disable).*
- **Data Integrity Thresholds - DBW Torque Request** (3) — Torque monitor: allowed requested-torque upper/lower bounds by APP×RPM; exceeding sets a checksum/integrity fault (limp). *N·m; up to ~160/199; cruise = 2000 (disable sentinel).*
- **Data Integrity Thresholds - DBW Torque Request ** (1) — Trailing-space duplicate category (source def quirk) with a single **BYPASSED - WIP** table (unused; data copied from the throttle-duty-% table; unit left N·m, ambiguous).

---

## K. Diagnostics (DTC)

- **DTC Flags B** (126) 🔧 — Enable/disable flags for each DTC (P00xx–P2xxx). All 1×1 uint8, value 0/1 (111 enabled, 15 disabled here). *Fix: 37 of 126 were mis-unit'd by sensor keywords (°/kPa/°C/V/%/g/s/rpm/km/h) → all unitless (boolean flags).*
- **DTC Thresholds** (27) 🔧 — Trip thresholds / activation counts / timers for various DTCs (P0172/P0171 fuel trim, P0421 cat, P0126 thermostat, P0125 CL, P0016/P0011 cam correlation, P0134 A/F sensor, P0638 throttle, P0601 internal, P2135 TPS2). *Fix: 9 tables (Timer °→unitless; Impedance AFR→Ω; Sync Offset →°; TP Threshold →%; Activation Count ×5 →unitless). Fuel-trim %, Load unitless, ECT °C, Req-Torque N·m, TP-factor g/s kept.*

---

## L. Limiters (RPM / VSS / Load)

- **Engine Limiters - RPM** (11) — RPM-limit protection, two systems: fuel cut (injection stop) and throttle cut (close throttle).
- **Engine Limiters - RPM** (sub-topic) — Note on the 7000–7500 rpm band: ignition/fuel map RPM axes stop at 7000 while rev (fuel-cut) is 7500; explains what is used above 7000.
- **Engine Limiters - VSS** (4) — Vehicle-speed limiter conditions (VSS and RPM thresholds + hysteresis). *km/h / rpm correct.*
- **Engine Load - Limits** (5) — Upper/lower clamps on computed engine Load (~1.0 = full). *Load is the Y axis of spark/fuel/VVT maps, so this guards over/under estimation.*
- **Engine Load - Scaling** (2) — The most fundamental Load (VE) calibration map. *Load drives spark/fuel/VVT axes — widest influence.*

---

## M. Patches (Code)

- **Patch - Decel** (overview) — DFCO (decel fuel cut) overview: cuts injection during overrun for economy/emissions; behavior tuned via the Fuel Comp OL decel cut/restore tables.
- **Patch - Decel Fuel Cutoff ** (1) — SH7058 code patch (not a map value) that NOPs a branch to disable DFCO. *unpatched 36610 (0x8F02 branch) → patched 9 (0x0009 NOP). Unitless (opcode). Currently unpatched.*
- **Patch - Engine Displacement** (4) 🔧 — Swaps the displacement constant: 3 code pointers (A/B/C) redirect to a new location holding the real displacement (cc). *Fix: Patch Address A/B/C cc→unitless (ROM addresses, 0xC9498→0xFBA00); the "replace NaN … in cc" value kept cc.*
- **Patch - Immobilizer Disable** (1) — Code patch that NOPs the immobilizer key-check branch. *unpatched 36616 (0x8F08) → patched 9 (NOP). Unitless. Currently unpatched (immobilizer active). For bench/swap/standalone use on one's own ECU.*
- **Patch - Open Loop Short Term Fuel Trim Fix** (1) — One-byte code patch fixing open-loop STFT behavior (STFT should be held in OL). *unpatched 141 (0x8D BT/S) → patched 160 (0xA0 BRA). Unitless. Currently unpatched.*
- **Patch - UDS Read Memory By Address (Mode 23)** (3) — Three code patches enabling UDS service 0x23 (ReadMemoryByAddress) for RAM/ROM dumping. *@0x7F734 36631→9 (NOP); @0x84C04 0→16; @0x84C07 6→15. Unitless. All unpatched.*

---

## N. Sensors / Vehicle

- **Engine Sensors - AFS** (3) — "AFS" here = the front **A/F (lambda) sensor**, not airflow: sensor-current → equivalence ratio (λ) characterization. *(Airflow is "Engine Sensors - MAF".)*
- **Engine Sensors - ECT** (1) — Coolant-temp sensor transfer curve (voltage → °C), NTC thermistor, monotonic. *1×39, 0.14–4.54 V → 150…−40 °C.*
- **Engine Sensors - IAT** (1) — Intake-air-temp sensor transfer curve (voltage → °C), NTC thermistor. *1×16, 0.06–4.75 V → 119…−40 °C.*
- **Engine Sensors - KS** (6) — Knock-sensor signal processing / detection calibration. *(Retard response is in Spark Correction - Knock Retard.)*
- **Engine Sensors - KS - DO NOT MODIFY** (33) — Low-level knock DSP (windowing, gating, adaptive noise tracking). Mazda/Denso tuned to the LF engine — do not modify.
- **Engine Sensors - MAF** (7) — MAF (airflow meter) calibration and high-load compensation.
- **Engine Sensors - MAP** (3) — MAP sensor calibration and fault fallback (LF-VE is MAF-based; MAP is auxiliary). *No unit errors.*

---

## O. WIP / Misc

- **WIP - Alternator** (18) 🔧 — Alternator charging control (target voltage / field duty / conditions); WIP with many Undefined/ZEROED/DISABLED entries. *Fix: "Voltage Desired Add | RPM LT 5K…" rpm→V; "WIP Limit | RPM…" rpm→× (condition-clause misfires). Base RPM Threshold kept rpm; Field Duty %, VSS Air-Flow Temp Add °C, Sensor Scaling V kept.*

---

## Other (Emissions / Fan / Gear Ratio)

- **Emission System - Catalyst** (4) — Catalyst-temperature estimation model (no cat-temp sensor); used for overheat protection enrichment and emissions/efficiency logic.
- **Emission System - EGR** (6) — EGR recirculates exhaust to lower combustion temperature (NOx) and pumping loss (part-load economy); active at part-load/cruise, zero at idle and WOT.
- **Emission System - EVAP** (4) — Evaporative-emissions canister purge (EVAPCP) command (base + correction).
- **Engine Fan Control** (23) — Radiator fan (low/med/high) control by ECT, VSS, A/C and after-cooling. *5 groups; timers in seconds.*
- **Gear Ratio** (7) — Transmission gear ratios + final drive used to detect the current gear. *Dimensionless (ratio), matches NC 6MT. Must be updated for gearbox/diff changes or gear detection drifts.*

---

### Notes

- Items marked **🔧** had a unit-label fix in `ncecu/i18n.py`; **🔧(none)** means the note confirms the existing label is correct (no change). Full details: `unit_fixes_i18n.md`.
- Trailing-space duplicate categories and definition-name typos (`Corection`, `Detla`, `Sarpk`, `Multipier`, `displacment`) originate in the LibreTuner definition files and were left unchanged.
- The Japanese edition (`map_analysis_JA.md`) contains the full, verbatim note bodies for every category.
