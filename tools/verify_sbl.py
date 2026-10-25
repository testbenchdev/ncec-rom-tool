"""復号済みSBL(.bin)の妥当性を読み取り専用で確認する。復号は一切しない。

真正な SH7058 フラッシュSBL なら必ず持つ特徴を照合する:
  - サイズ(生復号 5876/5452、または 0x1800 梱包済み)
  - エントロピー(コードは ~6。暗号/圧縮/ズレは ~8)
  - SH-2 命令ニブル比(コードらしさ)
  - フラッシュ制御レジスタ 0xFFFFE8xx(FCCS/FKEY等)への参照 ← これが最重要の決め手
  - 末尾 0xFF パディング量

使い方(PowerShell でそのまま):
  python -I tools/verify_sbl.py "C:/Users/user/Downloads/NECEECU/Decryption_sbl/sbl_nc1_decrypted.bin"
"""
from __future__ import annotations
import sys, pathlib, struct, math, collections

FLASH_REGS = {
    0xFFFFE800: "FCCS", 0xFFFFE801: "FPCS", 0xFFFFE802: "FECS",
    0xFFFFE804: "FKEY", 0xFFFFE805: "FMATS", 0xFFFFE806: "FTDAR",
}


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if len(sys.argv) < 2:
        print("usage: python -I tools/verify_sbl.py <decrypted_sbl.bin>")
        sys.exit(2)
    b = pathlib.Path(sys.argv[1]).read_bytes()
    n = len(b)

    ent = -sum((c / n) * math.log2(c / n) for c in collections.Counter(b).values())
    words = [struct.unpack_from(">H", b, i)[0] for i in range(0, n - 1, 2)]
    nib = collections.Counter(w >> 12 for w in words)
    codey = sum(nib[k] for k in (2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 14)) / len(words)
    tail = 0
    for x in reversed(b):
        if x == 0xFF:
            tail += 1
        else:
            break
    # フラッシュ制御レジスタ参照の検出:
    #   SH-2 の PC相対ロード命令を解決して、実際にロードされる定数を見る。
    #   - mov.w @(disp,PC),Rn (0x9nnn): 16bit値を符号拡張 → 0xE800 は 0xFFFFE800 になる
    #   - mov.l @(disp,PC),Rn (0xDnnn): 32bit値そのまま
    #   (0xE800 を素のバイト走査すると命令 mov #0,r8 と混同するので必ずロードを解決する)
    loaded = collections.Counter()
    for i in range(0, n - 1, 2):
        w = (b[i] << 8) | b[i + 1]
        op = w >> 12
        disp = w & 0xFF
        if op == 0x9:                       # mov.w @(disp,PC),Rn
            tgt = i + 4 + disp * 2
            if tgt + 1 < n:
                v = (b[tgt] << 8) | b[tgt + 1]
                v = (v - 0x10000) & 0xFFFFFFFF if (v & 0x8000) else v
                loaded[v] += 1
        elif op == 0xD:                     # mov.l @(disp,PC),Rn
            tgt = ((i + 4) & ~3) + disp * 4
            if tgt + 3 < n:
                loaded[(b[tgt] << 24) | (b[tgt + 1] << 16) | (b[tgt + 2] << 8) | b[tgt + 3]] += 1
    refs = collections.Counter({v: c for v, c in loaded.items() if 0xFFFFE800 <= v <= 0xFFFFE8FF})

    size_kind = {5876: "NC1 生復号(5876)", 5452: "NC2 生復号(5452)",
                 0x1800: "0x1800 梱包済み(flash.py にそのまま使える)"}.get(n, f"想定外サイズ {n}")
    print(f"file            : {sys.argv[1]}")
    print(f"size            : {n} (0x{n:X})  -> {size_kind}")
    print(f"entropy         : {ent:.2f} bit/B   (コード期待 ~5.5-7.2)")
    print(f"SH-2 codey ratio: {codey:.2f}        (コード期待 >=0.55)")
    print(f"trailing 0xFF   : {tail} (0x{tail:X})")
    print(f"first 8 words   : " + " ".join("%04X" % w for w in words[:8]))
    if refs:
        print("flash registers : " + ", ".join(f"0x{k:08X}({FLASH_REGS.get(k, '?')})x{v}"
                                                for k, v in sorted(refs.items())))
    else:
        print("flash registers : なし 0xFFFFE8xx のロードは未検出")
    periph = sorted(v for v in loaded if 0xFFFFE000 <= v <= 0xFFFFFFFF)
    if periph:
        print("周辺I/O定数     : " + ", ".join(f"0x{v:08X}" for v in periph[:16])
              + (" …" if len(periph) > 16 else ""))

    # 判定
    code_ok = (5.0 <= ent <= 7.4) and codey >= 0.5
    reg_ok = len(refs) > 0
    print()
    if reg_ok and code_ok:
        print("判定: ★ 真正なフラッシュSBLと整合(SH-2コード + フラッシュ制御レジスタ参照あり)。復号成功と判断してよい。")
    elif code_ok and not reg_ok:
        print("判定: △ SH-2コードらしくはあるが 0xFFFFE8xx 参照が無い。")
        print("      - これが『生復号(5876/5452)』なら、レジスタ参照がコード後半/別領域にある可能性。")
        print("      - rawではなく途中サイズなら復号ズレを疑う。サイズ表示を確認。")
    else:
        print("判定: × コードらしくない(エントロピー/ニブルが外れ)。鍵・サイズ・方向(後ろ向き)など復号手順を再確認。")


if __name__ == "__main__":
    main()
