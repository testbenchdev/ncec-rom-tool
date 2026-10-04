"""RomRaider 形式 ROM 定義(XML)のパーサ。NCEC (LFG7xx) 用。"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field

STORAGE_SIZE = {"uint8": 1, "int8": 1, "uint16": 2, "int16": 2,
                "uint32": 4, "int32": 4, "float": 4}


@dataclass
class Scaling:
    name: str
    toexpr: str = "x"      # raw -> real
    frexpr: str = "x"      # real -> raw
    fmt: str = "%.2f"
    units: str = ""
    storagetype: str = "uint8"
    endian: str = "big"
    inc: float = 1.0
    vmin: float = 0.0
    vmax: float = 0.0

    @property
    def size(self) -> int:
        return STORAGE_SIZE.get(self.storagetype, 1)

    def to_real(self, raw: float) -> float:
        return _safe_eval(self.toexpr, raw)

    def to_raw(self, real: float) -> float:
        return _safe_eval(self.frexpr, real)


@dataclass
class Axis:
    name: str
    address: int
    elements: int
    scaling: str
    kind: str  # "X Axis" / "Y Axis" / "Static"
    static_values: list[str] = field(default_factory=list)


@dataclass
class Table:
    name: str
    category: str
    ttype: str  # 1D/2D/3D
    address: int
    elements: int
    scaling: str
    swapxy: bool = False
    level: int = 1
    axes: list[Axis] = field(default_factory=list)
    desc: str = ""                              # テーブル固有の説明(LibreTuner定義由来)
    fixed_dims: tuple[int, int] | None = None   # (rows, cols) を定義が明示する場合に優先

    @property
    def x_axis(self) -> Axis | None:
        return next((a for a in self.axes if a.kind == "X Axis"), None)

    @property
    def y_axis(self) -> Axis | None:
        return next((a for a in self.axes if a.kind == "Y Axis"), None)


@dataclass
class RomDef:
    xmlid: str
    scalings: dict[str, Scaling]
    tables: list[Table]
    source: str = "romraider"   # "romraider"(XML) / "libretuner"(JSON)


_ALLOWED = re.compile(r'^[0-9xX.eE+\-*/() ]+$')


def _safe_eval(expr: str, x: float) -> float:
    expr = (expr or "x").strip()
    if expr == "x":
        return x
    if not _ALLOWED.match(expr):
        return x
    try:
        return float(eval(expr, {"__builtins__": {}}, {"x": x}))  # noqa: S307
    except Exception:
        return x


def _int(v, default=0):
    if v is None:
        return default
    try:
        return int(v, 16)
    except ValueError:
        try:
            return int(v)
        except ValueError:
            return default


def _parse_scaling(el) -> Scaling:
    return Scaling(
        name=el.get("name", ""),
        toexpr=el.get("toexpr", "x"),
        frexpr=el.get("frexpr", "x"),
        fmt=el.get("format", "%.2f"),
        units=el.get("units", ""),
        storagetype=el.get("storagetype", "uint8"),
        endian=el.get("endian", "big"),
        inc=float(el.get("inc", "1") or 1),
        vmin=float(el.get("min", "0") or 0),
        vmax=float(el.get("max", "0") or 0),
    )


def _parse_axis(el) -> Axis:
    kind = el.get("type", "Static")
    statics = [c.text or "" for c in el if c.tag == "data"]
    return Axis(
        name=el.get("name", ""),
        address=_int(el.get("address")),
        elements=_int(el.get("elements"), 1),
        scaling=el.get("scaling", ""),
        kind=kind,
        static_values=statics,
    )


def parse(path) -> RomDef:
    tree = ET.parse(path)
    root = tree.getroot()
    rom = root.find("rom")
    romid = rom.find("romid")
    xmlid = romid.findtext("xmlid", "") if romid is not None else ""

    scalings: dict[str, Scaling] = {}
    for el in rom.findall("scaling"):
        s = _parse_scaling(el)
        scalings[s.name] = s

    tables: list[Table] = []
    for el in rom.findall("table"):
        axes = [_parse_axis(c) for c in el if c.tag == "table"]
        tables.append(Table(
            name=el.get("name", ""),
            category=el.get("category", ""),
            ttype=el.get("type", "1D"),
            address=_int(el.get("address")),
            elements=_int(el.get("elements"), 1),
            scaling=el.get("scaling", ""),
            swapxy=(el.get("swapxy", "false") == "true"),
            level=_int(el.get("level"), 1),
            axes=axes,
        ))
    return RomDef(xmlid=xmlid, scalings=scalings, tables=tables)
