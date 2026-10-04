"""最小限の SH-2(E) 整数命令エミュレータ（big-endian）。ROM解析用。
seed→key のような自己完結した整数ルーチンを実行できれば十分な範囲を実装。
未対応命令に当たったら UnsupportedInsn を送出する。"""


class UnsupportedInsn(Exception):
    pass


class SH2:
    def __init__(self, rom: bytes, ram_base=0xFFFE8000, ram_size=0x18000):
        self.rom = rom
        self.ram_base = ram_base
        self.ram = bytearray(ram_size)
        self.r = [0] * 16
        self.pr = 0
        self.gbr = 0
        self.mach = 0
        self.macl = 0
        self.T = 0
        self.pc = 0
        # SH-2E FPU (single precision only): FR0..FR15 stored as 32-bit int bit patterns
        self.fr = [0] * 16
        self.fpul = 0
        self.fpscr = 0

    # ---- memory ----
    def _ref(self, addr):
        addr &= 0xFFFFFFFF
        if addr < len(self.rom):
            return ("rom", addr)
        if self.ram_base <= addr < self.ram_base + len(self.ram):
            return ("ram", addr - self.ram_base)
        return ("none", addr)

    def rd(self, addr, size):
        kind, off = self._ref(addr)
        if kind == "rom":
            b = self.rom[off:off + size]
        elif kind == "ram":
            b = bytes(self.ram[off:off + size])
        else:
            b = b"\x00" * size
        v = int.from_bytes(b, "big")
        return v

    def wr(self, addr, size, val):
        kind, off = self._ref(addr)
        val &= (1 << (size * 8)) - 1
        if kind == "ram":
            self.ram[off:off + size] = val.to_bytes(size, "big")
        # ROM/none writes ignored

    @staticmethod
    def s8(v):
        return v - 0x100 if v & 0x80 else v

    @staticmethod
    def s16(v):
        return v - 0x10000 if v & 0x8000 else v

    @staticmethod
    def s32(v):
        return v - 0x100000000 if v & 0x80000000 else v

    # ---- FPU single-precision helpers (bits <-> float) ----
    @staticmethod
    def _f2b(f):
        import struct
        try:
            return int.from_bytes(struct.pack(">f", f), "big")
        except (OverflowError, ValueError):
            return 0x7F800000  # inf on overflow
    @staticmethod
    def _b2f(bits):
        import struct
        return struct.unpack(">f", (bits & 0xFFFFFFFF).to_bytes(4, "big"))[0]
    def _frf(self, i):
        return self._b2f(self.fr[i])
    def _setfr(self, i, f):
        self.fr[i] = self._f2b(f)

    def step(self):
        op = self.rd(self.pc, 2)
        self.pc = (self.pc + 2) & 0xFFFFFFFF
        self._exec(op, self.pc - 2)

    def _delay(self, cur):
        """遅延スロット命令を実行（分岐命令の次の命令）。"""
        op = self.rd(self.pc, 2)
        self.pc = (self.pc + 2) & 0xFFFFFFFF
        self._exec(op, self.pc - 2)

    def _exec(self, op, at):
        r = self.r
        n = (op >> 8) & 0xF
        m = (op >> 4) & 0xF
        nib0 = op & 0xF
        d4 = op & 0xF
        d8 = op & 0xFF
        hi = op >> 12

        if op == 0x0009:  # nop
            return
        if op == 0x000B:  # rts
            tgt = self.pr
            self._delay(at + 2)
            self.pc = tgt
            return
        if op == 0x0008:  # clrt
            self.T = 0; return
        if op == 0x0018:  # sett
            self.T = 1; return
        if op == 0x0028:  # clrmac
            self.mach = self.macl = 0; return
        if op == 0x001B:  # sleep
            raise UnsupportedInsn("sleep")

        if hi == 0xE:  # mov #imm,Rn
            r[n] = self.s8(d8) & 0xFFFFFFFF; return
        if hi == 0x9:  # mov.w @(disp,pc),Rn
            addr = (at + 4 + (d8 << 1))
            r[n] = self.s16(self.rd(addr, 2)) & 0xFFFFFFFF; return
        if hi == 0xD:  # mov.l @(disp,pc),Rn
            addr = ((at + 4) & ~3) + (d8 << 2)
            r[n] = self.rd(addr, 4); return
        if hi == 0x7:  # add #imm,Rn
            r[n] = (r[n] + self.s8(d8)) & 0xFFFFFFFF; return
        if hi == 0x8:
            sub = (op >> 8) & 0xF
            if sub == 0x8:  # cmp/eq #imm,R0
                self.T = 1 if (self.s32(r[0]) == self.s8(d8)) else 0; return
            if sub == 0xB:  # bf
                if self.T == 0:
                    self.pc = at + 4 + (self.s8(d8) << 1)
                return
            if sub == 0xF:  # bf/s
                if self.T == 0:
                    self._delay(at + 2); self.pc = at + 4 + (self.s8(d8) << 1)
                return
            if sub == 0x9:  # bt
                if self.T == 1:
                    self.pc = at + 4 + (self.s8(d8) << 1)
                return
            if sub == 0xD:  # bt/s
                if self.T == 1:
                    self._delay(at + 2); self.pc = at + 4 + (self.s8(d8) << 1)
                return
            if sub == 0x0:  # mov.b R0,@(disp,Rm)
                self.wr(r[m] + d4, 1, r[0]); return
            if sub == 0x1:  # mov.w R0,@(disp,Rm)
                self.wr(r[m] + (d4 << 1), 2, r[0]); return
            if sub == 0x4:  # mov.b @(disp,Rm),R0
                r[0] = self.s8(self.rd(r[m] + d4, 1)) & 0xFFFFFFFF; return
            if sub == 0x5:  # mov.w @(disp,Rm),R0
                r[0] = self.s16(self.rd(r[m] + (d4 << 1), 2)) & 0xFFFFFFFF; return
            raise UnsupportedInsn(f"8x {op:04X}")
        if hi == 0xA:  # bra
            disp = op & 0xFFF
            if disp & 0x800:
                disp -= 0x1000
            self._delay(at + 2); self.pc = at + 4 + (disp << 1); return
        if hi == 0xB:  # bsr
            disp = op & 0xFFF
            if disp & 0x800:
                disp -= 0x1000
            self.pr = at + 4
            self._delay(at + 2); self.pc = at + 4 + (disp << 1); return
        if hi == 0xC:
            sub = (op >> 8) & 0xF
            if sub == 0x7:  # mova @(disp,pc),R0
                r[0] = ((at + 4) & ~3) + (d8 << 2); return
            if sub == 0x8:  # tst #imm,R0
                self.T = 1 if (r[0] & d8) == 0 else 0; return
            if sub == 0x9:  # and #imm,R0
                r[0] &= d8; return
            if sub == 0xA:  # xor #imm,R0
                r[0] ^= d8; return
            if sub == 0xB:  # or #imm,R0
                r[0] |= d8; return
            if sub == 0xC:  # tst.b #imm,@(R0,GBR)
                self.T = 1 if (self.rd(self.gbr + r[0], 1) & d8) == 0 else 0; return
            raise UnsupportedInsn(f"Cx {op:04X}")

        if hi == 0x6:
            sub = nib0
            v = r[m]
            if sub == 0x3:  # mov Rm,Rn
                r[n] = r[m]; return
            if sub == 0x0:  # mov.b @Rm,Rn
                r[n] = self.s8(self.rd(r[m], 1)) & 0xFFFFFFFF; return
            if sub == 0x1:  # mov.w @Rm,Rn
                r[n] = self.s16(self.rd(r[m], 2)) & 0xFFFFFFFF; return
            if sub == 0x2:  # mov.l @Rm,Rn
                r[n] = self.rd(r[m], 4); return
            if sub == 0x4:  # mov.b @Rm+,Rn
                r[n] = self.s8(self.rd(r[m], 1)) & 0xFFFFFFFF
                if n != m: r[m] = (r[m] + 1) & 0xFFFFFFFF
                return
            if sub == 0x5:  # mov.w @Rm+,Rn
                r[n] = self.s16(self.rd(r[m], 2)) & 0xFFFFFFFF
                if n != m: r[m] = (r[m] + 2) & 0xFFFFFFFF
                return
            if sub == 0x6:  # mov.l @Rm+,Rn
                r[n] = self.rd(r[m], 4)
                if n != m: r[m] = (r[m] + 4) & 0xFFFFFFFF
                return
            if sub == 0x7:  # not
                r[n] = (~r[m]) & 0xFFFFFFFF; return
            if sub == 0x8:  # swap.b
                r[n] = (r[m] & 0xFFFF0000) | ((r[m] & 0xFF) << 8) | ((r[m] >> 8) & 0xFF); return
            if sub == 0x9:  # swap.w
                r[n] = ((r[m] << 16) | (r[m] >> 16)) & 0xFFFFFFFF; return
            if sub == 0xA:  # negc
                tmp = (0 - r[m] - self.T) & 0xFFFFFFFF
                self.T = 1 if (r[m] + self.T) > 0 or False else self.T
                # proper negc:
                res = (0 - r[m] - self.T)
                self.T = 1 if res < 0 else 0
                r[n] = res & 0xFFFFFFFF; return
            if sub == 0xB:  # neg
                r[n] = (0 - r[m]) & 0xFFFFFFFF; return
            if sub == 0xC:  # extu.b
                r[n] = r[m] & 0xFF; return
            if sub == 0xD:  # extu.w
                r[n] = r[m] & 0xFFFF; return
            if sub == 0xE:  # exts.b
                r[n] = self.s8(r[m] & 0xFF) & 0xFFFFFFFF; return
            if sub == 0xF:  # exts.w
                r[n] = self.s16(r[m] & 0xFFFF) & 0xFFFFFFFF; return
            raise UnsupportedInsn(f"6x {op:04X}")

        if hi == 0x2:
            sub = nib0
            if sub == 0x0:  # mov.b Rm,@Rn
                self.wr(r[n], 1, r[m]); return
            if sub == 0x1:  # mov.w Rm,@Rn
                self.wr(r[n], 2, r[m]); return
            if sub == 0x2:  # mov.l Rm,@Rn
                self.wr(r[n], 4, r[m]); return
            if sub == 0x4:  # mov.b Rm,@-Rn
                r[n] = (r[n] - 1) & 0xFFFFFFFF; self.wr(r[n], 1, r[m]); return
            if sub == 0x5:  # mov.w Rm,@-Rn
                r[n] = (r[n] - 2) & 0xFFFFFFFF; self.wr(r[n], 2, r[m]); return
            if sub == 0x6:  # mov.l Rm,@-Rn
                r[n] = (r[n] - 4) & 0xFFFFFFFF; self.wr(r[n], 4, r[m]); return
            if sub == 0x7:  # div0s
                self.T = ((r[n] >> 31) ^ (r[m] >> 31)) & 1; return
            if sub == 0x8:  # tst
                self.T = 1 if (r[n] & r[m]) == 0 else 0; return
            if sub == 0x9:  # and
                r[n] &= r[m]; return
            if sub == 0xA:  # xor
                r[n] ^= r[m]; return
            if sub == 0xB:  # or
                r[n] |= r[m]; return
            if sub == 0xC:  # cmp/str
                t = r[n] ^ r[m]
                self.T = 1 if any((t >> (8 * i)) & 0xFF == 0 for i in range(4)) else 0; return
            if sub == 0xD:  # xtrct
                r[n] = ((r[m] << 16) | (r[n] >> 16)) & 0xFFFFFFFF; return
            if sub == 0xE:  # mulu.w
                self.macl = (r[n] & 0xFFFF) * (r[m] & 0xFFFF) & 0xFFFFFFFF; return
            if sub == 0xF:  # muls.w
                self.macl = (self.s16(r[n] & 0xFFFF) * self.s16(r[m] & 0xFFFF)) & 0xFFFFFFFF; return
            raise UnsupportedInsn(f"2x {op:04X}")

        if hi == 0x3:
            sub = nib0
            a = r[n]; b = r[m]
            if sub == 0x0:  # cmp/eq
                self.T = 1 if a == b else 0; return
            if sub == 0x2:  # cmp/hs (unsigned)
                self.T = 1 if (a & 0xFFFFFFFF) >= (b & 0xFFFFFFFF) else 0; return
            if sub == 0x3:  # cmp/ge (signed)
                self.T = 1 if self.s32(a) >= self.s32(b) else 0; return
            if sub == 0x6:  # cmp/hi
                self.T = 1 if (a & 0xFFFFFFFF) > (b & 0xFFFFFFFF) else 0; return
            if sub == 0x7:  # cmp/gt
                self.T = 1 if self.s32(a) > self.s32(b) else 0; return
            if sub == 0x4:  # div1
                raise UnsupportedInsn("div1")
            if sub == 0x8:  # sub
                r[n] = (a - b) & 0xFFFFFFFF; return
            if sub == 0xA:  # subc
                res = a - b - self.T
                self.T = 1 if res < 0 else 0
                r[n] = res & 0xFFFFFFFF; return
            if sub == 0xB:  # subv
                res = self.s32(a) - self.s32(b)
                self.T = 1 if res < -0x80000000 or res > 0x7FFFFFFF else 0
                r[n] = res & 0xFFFFFFFF; return
            if sub == 0xC:  # add
                r[n] = (a + b) & 0xFFFFFFFF; return
            if sub == 0xE:  # addc
                res = a + b + self.T
                self.T = 1 if res > 0xFFFFFFFF else 0
                r[n] = res & 0xFFFFFFFF; return
            if sub == 0xF:  # addv
                res = self.s32(a) + self.s32(b)
                self.T = 1 if res < -0x80000000 or res > 0x7FFFFFFF else 0
                r[n] = res & 0xFFFFFFFF; return
            if sub == 0xD:  # dmuls.l
                res = (self.s32(a) * self.s32(b)) & 0xFFFFFFFFFFFFFFFF
                self.mach = (res >> 32) & 0xFFFFFFFF; self.macl = res & 0xFFFFFFFF; return
            if sub == 0x5:  # dmulu.l
                res = (a * b) & 0xFFFFFFFFFFFFFFFF
                self.mach = (res >> 32) & 0xFFFFFFFF; self.macl = res & 0xFFFFFFFF; return
            raise UnsupportedInsn(f"3x {op:04X}")

        if hi == 0x4:
            sub = op & 0xFF
            low = nib0
            if sub == 0x00:  # shll
                self.T = (r[n] >> 31) & 1; r[n] = (r[n] << 1) & 0xFFFFFFFF; return
            if sub == 0x01:  # shlr
                self.T = r[n] & 1; r[n] = (r[n] >> 1); return
            if sub == 0x04:  # rotl
                self.T = (r[n] >> 31) & 1
                r[n] = ((r[n] << 1) | self.T) & 0xFFFFFFFF; return
            if sub == 0x05:  # rotr
                self.T = r[n] & 1
                r[n] = ((r[n] >> 1) | (self.T << 31)) & 0xFFFFFFFF; return
            if sub == 0x24:  # rotcl
                newt = (r[n] >> 31) & 1
                r[n] = ((r[n] << 1) | self.T) & 0xFFFFFFFF; self.T = newt; return
            if sub == 0x25:  # rotcr
                newt = r[n] & 1
                r[n] = ((r[n] >> 1) | (self.T << 31)) & 0xFFFFFFFF; self.T = newt; return
            if sub == 0x20:  # shal
                self.T = (r[n] >> 31) & 1; r[n] = (r[n] << 1) & 0xFFFFFFFF; return
            if sub == 0x21:  # shar
                self.T = r[n] & 1; r[n] = (self.s32(r[n]) >> 1) & 0xFFFFFFFF; return
            if sub == 0x08:  # shll2
                r[n] = (r[n] << 2) & 0xFFFFFFFF; return
            if sub == 0x09:  # shlr2
                r[n] = (r[n] >> 2); return
            if sub == 0x18:  # shll8
                r[n] = (r[n] << 8) & 0xFFFFFFFF; return
            if sub == 0x19:  # shlr8
                r[n] = (r[n] >> 8); return
            if sub == 0x28:  # shll16
                r[n] = (r[n] << 16) & 0xFFFFFFFF; return
            if sub == 0x29:  # shlr16
                r[n] = (r[n] >> 16); return
            if sub == 0x0B:  # jsr @Rn
                tgt = r[n]; self.pr = at + 4
                self._delay(at + 2); self.pc = tgt; return
            if sub == 0x2B:  # jmp @Rn
                tgt = r[n]
                self._delay(at + 2); self.pc = tgt; return
            if sub == 0x0E:  # ldc Rn,SR (ignore)
                return
            if sub == 0x0A:  # lds Rn,MACH
                self.mach = r[n]; return
            if sub == 0x1A:  # lds Rn,MACL
                self.macl = r[n]; return
            if sub == 0x2A:  # lds Rn,PR
                self.pr = r[n]; return
            if sub == 0x22:  # sts.l PR,@-Rn
                r[n] = (r[n] - 4) & 0xFFFFFFFF; self.wr(r[n], 4, self.pr); return
            if sub == 0x26:  # lds.l @Rn+,PR
                self.pr = self.rd(r[n], 4); r[n] = (r[n] + 4) & 0xFFFFFFFF; return
            if sub == 0x5A:  # lds Rn,FPUL
                self.fpul = r[n]; return
            if sub == 0x6A:  # lds Rn,FPSCR
                self.fpscr = r[n]; return
            if sub == 0x52:  # sts.l FPUL,@-Rn
                r[n] = (r[n] - 4) & 0xFFFFFFFF; self.wr(r[n], 4, self.fpul); return
            if sub == 0x56:  # lds.l @Rn+,FPUL
                self.fpul = self.rd(r[n], 4); r[n] = (r[n] + 4) & 0xFFFFFFFF; return
            if sub == 0x62:  # sts.l FPSCR,@-Rn
                r[n] = (r[n] - 4) & 0xFFFFFFFF; self.wr(r[n], 4, self.fpscr); return
            if sub == 0x66:  # lds.l @Rn+,FPSCR
                self.fpscr = self.rd(r[n], 4); r[n] = (r[n] + 4) & 0xFFFFFFFF; return
            if sub == 0x10:  # dt
                r[n] = (r[n] - 1) & 0xFFFFFFFF
                self.T = 1 if r[n] == 0 else 0; return
            if sub == 0x11:  # cmp/pz
                self.T = 1 if self.s32(r[n]) >= 0 else 0; return
            if sub == 0x15:  # cmp/pl
                self.T = 1 if self.s32(r[n]) > 0 else 0; return
            if sub == 0x29:  # shlr16 handled; (dup guard)
                r[n] = (r[n] >> 16); return
            if low == 0xC:  # ldc.l @Rn+,xxx etc - ignore register bank ops safely
                r[n] = (r[n] + 4) & 0xFFFFFFFF; return
            raise UnsupportedInsn(f"4x {op:04X} sub{sub:02X}")

        if hi == 0x5:  # mov.l @(disp,Rm),Rn
            r[n] = self.rd(r[m] + (d4 << 2), 4); return
        if hi == 0x1:  # mov.l Rm,@(disp,Rn)
            self.wr(r[n] + (d4 << 2), 4, r[m]); return
        if hi == 0x0:
            sub = nib0
            if sub == 0xC:  # mov.b @(R0,Rm),Rn
                r[n] = self.s8(self.rd(r[0] + r[m], 1)) & 0xFFFFFFFF; return
            if sub == 0xD:  # mov.w @(R0,Rm),Rn
                r[n] = self.s16(self.rd(r[0] + r[m], 2)) & 0xFFFFFFFF; return
            if sub == 0xE:  # mov.l @(R0,Rm),Rn
                r[n] = self.rd(r[0] + r[m], 4); return
            if sub == 0x4:  # mov.b Rm,@(R0,Rn)
                self.wr(r[0] + r[n], 1, r[m]); return
            if sub == 0x5:  # mov.w Rm,@(R0,Rn)
                self.wr(r[0] + r[n], 2, r[m]); return
            if sub == 0x6:  # mov.l Rm,@(R0,Rn)
                self.wr(r[0] + r[n], 4, r[m]); return
            if sub == 0x7:  # mul.l
                self.macl = (r[n] * r[m]) & 0xFFFFFFFF; return
            if sub == 0xA:
                t = (op >> 4) & 0xF
                if t == 0x2:  # sts MACL,Rn
                    r[n] = self.macl; return
                if t == 0x0:  # sts MACH,Rn
                    r[n] = self.mach; return
                if t == 0x5:  # sts FPUL,Rn
                    r[n] = self.fpul; return
                if t == 0x6:  # sts FPSCR,Rn
                    r[n] = self.fpscr; return
                if t == 0x2A or False:
                    pass
            if op & 0xFF == 0x29:  # movt
                r[n] = self.T; return
            if sub == 0x9 and ((op >> 4) & 0xF) == 0x2:  # movt alt
                r[n] = self.T; return
            if sub == 0x3:  # bsrf/braf
                t = (op >> 4) & 0xF
                if t == 0x0:  # braf Rn
                    tgt = at + 4 + r[n]; self._delay(at + 2); self.pc = tgt; return
                if t == 0x2:  # bsrf Rn
                    self.pr = at + 4; tgt = at + 4 + r[n]
                    self._delay(at + 2); self.pc = tgt; return
            if sub == 0x2:  # sts/stc variants -> store system reg to Rn (approx)
                r[n] = 0; return
            raise UnsupportedInsn(f"0x {op:04X}")

        if hi == 0xF:
            import math
            lo = op & 0xF
            if lo == 0x0:  # FADD
                self._setfr(n, self._frf(n) + self._frf(m)); return
            if lo == 0x1:  # FSUB
                self._setfr(n, self._frf(n) - self._frf(m)); return
            if lo == 0x2:  # FMUL
                self._setfr(n, self._frf(n) * self._frf(m)); return
            if lo == 0x3:  # FDIV
                d = self._frf(m)
                self._setfr(n, self._frf(n) / d if d != 0 else float("inf")); return
            if lo == 0x4:  # FCMP/EQ
                self.T = 1 if self._frf(n) == self._frf(m) else 0; return
            if lo == 0x5:  # FCMP/GT
                self.T = 1 if self._frf(n) > self._frf(m) else 0; return
            if lo == 0x6:  # FMOV.S @(R0,Rm),FRn
                self.fr[n] = self.rd(r[0] + r[m], 4); return
            if lo == 0x7:  # FMOV.S FRm,@(R0,Rn)
                self.wr(r[0] + r[n], 4, self.fr[m]); return
            if lo == 0x8:  # FMOV.S @Rm,FRn
                self.fr[n] = self.rd(r[m], 4); return
            if lo == 0x9:  # FMOV.S @Rm+,FRn
                self.fr[n] = self.rd(r[m], 4); r[m] = (r[m] + 4) & 0xFFFFFFFF; return
            if lo == 0xA:  # FMOV.S FRm,@Rn
                self.wr(r[n], 4, self.fr[m]); return
            if lo == 0xB:  # FMOV.S FRm,@-Rn
                r[n] = (r[n] - 4) & 0xFFFFFFFF; self.wr(r[n], 4, self.fr[m]); return
            if lo == 0xC:  # FMOV FRm,FRn
                self.fr[n] = self.fr[m]; return
            if lo == 0xE:  # FMAC FR0,FRm,FRn
                self._setfr(n, self._frf(0) * self._frf(m) + self._frf(n)); return
            if lo == 0xD:  # special, m selects sub-op, n = FR reg
                sub = m
                if sub == 0x0:  # FSTS FPUL,FRn
                    self.fr[n] = self.fpul; return
                if sub == 0x1:  # FLDS FRn,FPUL
                    self.fpul = self.fr[n]; return
                if sub == 0x2:  # FLOAT FPUL,FRn
                    self._setfr(n, float(self.s32(self.fpul))); return
                if sub == 0x3:  # FTRC FRn,FPUL
                    f = self._frf(n)
                    try:
                        iv = int(f)
                    except (ValueError, OverflowError):
                        iv = 0x7FFFFFFF
                    if iv > 0x7FFFFFFF: iv = 0x7FFFFFFF
                    if iv < -0x80000000: iv = -0x80000000
                    self.fpul = iv & 0xFFFFFFFF; return
                if sub == 0x4:  # FNEG
                    self._setfr(n, -self._frf(n)); return
                if sub == 0x5:  # FABS
                    self._setfr(n, abs(self._frf(n))); return
                if sub == 0x6:  # FSQRT
                    v = self._frf(n)
                    self._setfr(n, math.sqrt(v) if v >= 0 else float("nan")); return
                if sub == 0x8:  # FLDI0
                    self.fr[n] = 0x00000000; return
                if sub == 0x9:  # FLDI1
                    self.fr[n] = 0x3F800000; return
                raise UnsupportedInsn(f"Fx D sub{sub:X} {op:04X}")
            raise UnsupportedInsn(f"Fx {op:04X}")

        raise UnsupportedInsn(f"{op:04X}")
