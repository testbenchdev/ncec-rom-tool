"""ROM イメージのモデル: 定義に基づくテーブル値の読み書き（スケーリング適用）。"""
from __future__ import annotations

import struct

from .defs import Axis, RomDef, Scaling, Table


class Rom:
    def __init__(self, data: bytes, romdef: RomDef):
        self.data = bytearray(data)
        self.rd = romdef

    # ---- 低レベル raw 読み書き ----
    def _read_raw(self, addr: int, sc: Scaling) -> float:
        n = sc.size
        b = bytes(self.data[addr:addr + n])
        st = sc.storagetype
        if st == "float":
            return struct.unpack(">f", b)[0]
        signed = st.startswith("int")
        return int.from_bytes(b, "big", signed=signed)

    def _write_raw(self, addr: int, sc: Scaling, raw: float) -> None:
        n = sc.size
        st = sc.storagetype
        if st == "float":
            self.data[addr:addr + n] = struct.pack(">f", float(raw))
            return
        signed = st.startswith("int")
        lo = -(1 << (n * 8 - 1)) if signed else 0
        hi = (1 << (n * 8 - 1)) - 1 if signed else (1 << (n * 8)) - 1
        iv = max(lo, min(hi, int(round(raw))))
        self.data[addr:addr + n] = iv.to_bytes(n, "big", signed=signed)

    # ---- スケーリング済みの値 ----
    def read_value(self, addr: int, sc: Scaling) -> float:
        return sc.to_real(self._read_raw(addr, sc))

    def write_value(self, addr: int, sc: Scaling, real: float) -> None:
        self._write_raw(addr, sc, sc.to_raw(real))

    # ---- テーブル/軸 ----
    def _sc(self, name: str) -> Scaling:
        return self.rd.scalings.get(name) or Scaling(name=name)

    def read_axis(self, ax: Axis) -> list[float]:
        if ax.static_values:
            out = []
            for v in ax.static_values:
                try:
                    out.append(float(v))
                except ValueError:
                    out.append(v)
            return out
        sc = self._sc(ax.scaling)
        return [self.read_value(ax.address + i * sc.size, sc) for i in range(ax.elements)]

    def dims(self, t: Table) -> tuple[int, int]:
        """(rows, cols) を返す。1D=(1,n), 2D=(1,n)|(n,1), 3D=(y,x)。
        定義が次元を明示していればそれを最優先、次にECUディスクリプタ由来の検証済み補正。"""
        if t.fixed_dims:
            return t.fixed_dims
        try:
            from .corrections import corrected_dims
            cd = corrected_dims(t.address)
            if cd:
                return cd
        except Exception:
            pass
        xa, ya = t.x_axis, t.y_axis
        if t.ttype == "3D" and xa and ya:
            return ya.elements, xa.elements
        if t.ttype == "2D":
            # 1本の軸（X か Y）
            if ya and not xa:
                return ya.elements, 1
            if xa:
                return 1, xa.elements
            return 1, t.elements
        return 1, t.elements

    def read_table(self, t: Table) -> list[list[float]]:
        sc = self._sc(t.scaling)
        rows, cols = self.dims(t)
        grid = []
        idx = 0
        for r in range(rows):
            row = []
            for c in range(cols):
                row.append(self.read_value(t.address + idx * sc.size, sc))
                idx += 1
            grid.append(row)
        return grid

    def write_cell(self, t: Table, r: int, c: int, real: float) -> None:
        sc = self._sc(t.scaling)
        _, cols = self.dims(t)
        idx = r * cols + c
        self.write_value(t.address + idx * sc.size, sc, real)

    def bytes_out(self) -> bytes:
        return bytes(self.data)
