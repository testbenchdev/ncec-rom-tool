"""LibreTuner 形式 ROM 定義(JSON)のローダ。NCEC (LFG7xx) 用。

LibreTuner の定義は 2 ファイルに分かれる:
  - main.json : プラットフォーム共通の構造。tables{key: {name,description,category,
                width,height,datatype,minimum,maximum,axisx?,axisy?}} と
                axes{key: {name,size,type,datatype}}
  - <CALID>.json : この CALID 固有のアドレス。tables{key: addr(10進)} / axes{key: addr}

これらを defs.RomDef / Table / Axis / Scaling に変換して返すので、rom.py・エディタは
RomRaider XML と同じインターフェースで扱える。romdrop XML がこの個体 ROM の約125テーブルで
次元を誤るのに対し、LibreTuner 定義は width/height を明示しており不一致は 9/875 のみ。
"""
from __future__ import annotations

import json
import pathlib

from .defs import Axis, RomDef, Scaling, Table

# LibreTuner datatype -> (storagetype, 表示フォーマット)
_DT = {
    "float":  ("float",  "%.3f"),
    "uint8":  ("uint8",  "%.0f"),
    "int8":   ("int8",   "%.0f"),
    "uint16": ("uint16", "%.0f"),
    "int16":  ("int16",  "%.0f"),
    "uint32": ("uint32", "%.0f"),
    "int32":  ("int32",  "%.0f"),
}


def _axis_scaling_name(dt: str) -> str:
    return f"__axis_{dt}"


def parse(main_path, calid_path) -> RomDef:
    main = json.loads(pathlib.Path(main_path).read_text(encoding="utf-8"))
    calid = json.loads(pathlib.Path(calid_path).read_text(encoding="utf-8"))

    mtabs: dict = main.get("tables", {})
    maxes: dict = main.get("axes", {})
    taddr: dict = calid.get("tables", {})   # key -> address(int)
    aaddr: dict = calid.get("axes", {})     # key -> address(int)

    scalings: dict[str, Scaling] = {}
    # 軸用の恒等スケーリング(型ごと)
    for dt, (st, fmt) in _DT.items():
        scalings[_axis_scaling_name(dt)] = Scaling(
            name=_axis_scaling_name(dt), toexpr="x", frexpr="x",
            fmt=fmt, storagetype=st)

    def _axis(axis_key: str, kind: str) -> Axis | None:
        spec = maxes.get(axis_key)
        if spec is None or axis_key not in aaddr:
            return None
        dt = spec.get("datatype", "float")
        if dt not in _DT:
            dt = "float"
        return Axis(
            name=spec.get("name", axis_key),
            address=int(aaddr[axis_key]),
            elements=int(spec.get("size", 1)),
            scaling=_axis_scaling_name(dt),
            kind=kind,
        )

    tables: list[Table] = []
    for key, addr in taddr.items():
        d = mtabs.get(key)
        if d is None:
            continue
        dt = d.get("datatype", "float")
        if dt not in _DT:
            dt = "float"
        st, fmt = _DT[dt]
        w = int(d.get("width", 1) or 1)
        h = int(d.get("height", 1) or 1)
        mn = float(d.get("minimum", 0.0) or 0.0)
        mx = float(d.get("maximum", 0.0) or 0.0)

        # テーブルごとの一意なスケーリング(目安範囲 min/max を保持)
        sc_name = f"sc::{key}"
        scalings[sc_name] = Scaling(
            name=sc_name, toexpr="x", frexpr="x", fmt=fmt,
            storagetype=st, vmin=mn, vmax=mx)

        axes: list[Axis] = []
        ax = _axis(d["axisx"], "X Axis") if d.get("axisx") else None
        ay = _axis(d["axisy"], "Y Axis") if d.get("axisy") else None
        if ax:
            axes.append(ax)
        if ay:
            axes.append(ay)

        if w > 1 and h > 1:
            ttype = "3D"
        elif w > 1 or h > 1:
            ttype = "2D"
        else:
            ttype = "1D"

        name = d.get("name", key)
        desc = d.get("description", "") or ""
        if desc.strip() == name.strip():
            desc = ""

        tables.append(Table(
            name=name,
            category=d.get("category", ""),
            ttype=ttype,
            address=int(addr),
            elements=w * h,
            scaling=sc_name,
            axes=axes,
            desc=desc,
            fixed_dims=(h, w),   # 行=height, 列=width(行優先格納)
        ))

    xmlid = calid.get("name") or calid.get("id") or main.get("name", "LibreTuner")
    return RomDef(xmlid=str(xmlid), scalings=scalings, tables=tables, source="libretuner")
