"""NCEC ROM マップエディタ 詳細取説(PDF)生成スクリプト。

ROM(実値)と LibreTuner 定義を読み、概要 / 使用方法 / 各マップの詳細(ヒートマップ画像+
意味・調整・注意)を PDF 出力する。改変があれば本スクリプトを再実行すれば最新版に更新される。

出力: docs/map_editor_manual.pdf
依存: PyMuPDF(pymupdf), Pillow(PIL) のみ。
使い方: python tools/gen_manual.py
"""
from __future__ import annotations

import datetime
import math
import pathlib
import struct
import sys

import pymupdf as fitz
from PIL import Image, ImageDraw, ImageFont

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ncecu import ltdef, i18n, flash as flashmod  # noqa: E402
from ncecu.rom import Rom  # noqa: E402

ROM_PATH = ROOT / "ncec_rom_dump.bin"
MAIN_JSON = ROOT / "defs" / "libretuner" / "main.json"
CALID_JSON = ROOT / "defs" / "libretuner" / "LFG7EG.json"
OUT_PDF = ROOT / "docs" / "map_editor_manual.pdf"
TMP = ROOT / "docs" / "_manual_img"
NOTES_PATH = ROOT / "docs" / "map_notes.json"   # 質問から蓄積した解説(§6)

# ---- 色(ヒートマップ・編集GUIと同じ系統)----
HEAT_STOPS = [(0.0, (40, 70, 160)), (0.25, (30, 150, 170)), (0.5, (40, 160, 80)),
              (0.75, (210, 180, 50)), (1.0, (200, 60, 50))]


def heat_color(v, lo, hi):
    if hi <= lo:
        return (120, 120, 120)
    t = max(0.0, min(1.0, (v - lo) / (hi - lo)))
    for i in range(len(HEAT_STOPS) - 1):
        t0, c0 = HEAT_STOPS[i]
        t1, c1 = HEAT_STOPS[i + 1]
        if t <= t1:
            f = (t - t0) / (t1 - t0) if t1 > t0 else 0
            return tuple(int(c0[k] + (c1[k] - c0[k]) * f) for k in range(3))
    return (200, 60, 50)


def _font(path_candidates, size):
    for p in path_candidates:
        try:
            return ImageFont.truetype(p, size)
        except OSError:
            continue
    return ImageFont.load_default()


FNUM = [r"C:\Windows\Fonts\consola.ttf", r"C:\Windows\Fonts\cour.ttf"]
FJP = [r"C:\Windows\Fonts\meiryo.ttc", r"C:\Windows\Fonts\YuGothR.ttc",
       r"C:\Windows\Fonts\msgothic.ttc"]


def _isnan(v):
    return isinstance(v, float) and math.isnan(v)


def render_heatmap(grid, xvals, yvals, xlabel, ylabel, title, path, vfmt="%.1f"):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    cw, chh = 48, 22
    lx = 86 if yvals else 20       # 左: Y値見出し
    ty = 64                         # 上: タイトル+X値見出し
    W = lx + cols * cw + 16
    H = ty + rows * chh + 16
    img = Image.new("RGB", (W, H), (255, 255, 255))
    d = ImageDraw.Draw(img)
    fn = _font(FNUM, 11)
    fj = _font(FJP, 12)
    fjs = _font(FJP, 11)
    d.text((10, 8), title, font=fj, fill=(20, 20, 20))
    if xlabel:
        d.text((lx, 30), f"{xlabel} →", font=fjs, fill=(60, 80, 120))
    if ylabel:
        d.text((6, 46), f"↓{ylabel}", font=fjs, fill=(60, 80, 120))
    flat = [v for row in grid for v in row if isinstance(v, (int, float)) and not _isnan(v)]
    lo, hi = (min(flat), max(flat)) if flat else (0, 1)
    # X 見出し
    if xvals:
        for j in range(cols):
            xv = xvals[j] if j < len(xvals) else ""
            s = (vfmt % xv) if isinstance(xv, float) else str(xv)
            d.text((lx + j * cw + 3, 48), s, font=fn, fill=(70, 80, 100))
    for i in range(rows):
        if yvals:
            yv = yvals[i] if i < len(yvals) else ""
            s = (vfmt % yv) if isinstance(yv, float) else str(yv)
            d.text((6, ty + i * chh + 5), s, font=fn, fill=(70, 80, 100))
        for j in range(cols):
            v = grid[i][j]
            x0, y0 = lx + j * cw, ty + i * chh
            if _isnan(v):
                d.rectangle([x0, y0, x0 + cw - 1, y0 + chh - 1], fill=(210, 210, 210))
                d.text((x0 + cw // 2 - 4, y0 + 4), "—", font=fn, fill=(120, 120, 120))
                continue
            col = heat_color(v, lo, hi)
            d.rectangle([x0, y0, x0 + cw - 1, y0 + chh - 1], fill=col)
            lum = 0.3 * col[0] + 0.6 * col[1] + 0.1 * col[2]
            tc = (10, 10, 10) if lum > 120 else (245, 245, 245)
            d.text((x0 + 3, y0 + 4), (vfmt % v) if isinstance(v, float) else str(v),
                   font=fn, fill=tc)
    img.save(path)
    return W, H


class Doc:
    def __init__(self):
        self.doc = fitz.open()
        self.font = fitz.Font("cjk")
        self.W, self.H = 595.0, 842.0
        self.ml, self.mr, self.mt, self.mb = 52, 52, 56, 52
        self.ink = (0.12, 0.14, 0.16)
        self.accent = (0.10, 0.36, 0.52)
        self.sub = (0.40, 0.45, 0.50)
        self.warn = (0.70, 0.20, 0.15)
        self.page = None
        self._writers = {}
        self.y = 0
        self._start_page()

    def _start_page(self):
        if self.page is not None:
            self._flush()
        self.page = self.doc.new_page(width=self.W, height=self.H)
        self._writers = {}
        self.y = self.mt
        n = self.doc.page_count
        self._tw(self.sub).append((self.W - self.mr - 30, self.H - 28),
                                  f"- {n} -", font=self.font, fontsize=9)

    def _flush(self):
        for color, tw in self._writers.items():
            tw.write_text(self.page, color=color)
        self._writers = {}

    def _tw(self, color):
        if color not in self._writers:
            self._writers[color] = fitz.TextWriter(self.page.rect)
        return self._writers[color]

    def _wrap(self, text, size, width):
        lines = []
        for raw in text.split("\n"):
            if raw == "":
                lines.append("")
                continue
            cur = ""
            for ch in raw:
                if self.font.text_length(cur + ch, size) > width and cur:
                    lines.append(cur)
                    cur = ch
                else:
                    cur += ch
            lines.append(cur)
        return lines

    def _need(self, h):
        if self.y + h > self.H - self.mb:
            self._start_page()

    def para(self, text, size=10, color=None, gap=4, lead=1.42, indent=0):
        color = color or self.ink
        width = self.W - self.ml - self.mr - indent
        lh = size * lead
        for ln in self._wrap(text, size, width):
            self._need(lh)
            self._tw(color).append((self.ml + indent, self.y + size), ln,
                                   font=self.font, fontsize=size)
            self.y += lh
        self.y += gap

    def bullet(self, text, size=10, gap=2, indent=12):
        width = self.W - self.ml - self.mr - indent - 10
        lh = size * 1.4
        lines = self._wrap(text, size, width)
        for k, ln in enumerate(lines):
            self._need(lh)
            if k == 0:
                self._tw(self.accent).append((self.ml + indent, self.y + size), "•",
                                             font=self.font, fontsize=size)
            self._tw(self.ink).append((self.ml + indent + 12, self.y + size), ln,
                                      font=self.font, fontsize=size)
            self.y += lh
        self.y += gap

    def h1(self, text):
        self._need(40)
        self.y += 6
        self._tw(self.accent).append((self.ml, self.y + 17), text,
                                     font=self.font, fontsize=17)
        self.y += 23
        self.page.draw_line((self.ml, self.y), (self.W - self.mr, self.y),
                            color=self.accent, width=1.2)
        self.y += 10

    def h2(self, text):
        self._need(28)
        self.y += 4
        self._tw(self.accent).append((self.ml, self.y + 13), text,
                                     font=self.font, fontsize=13)
        self.y += 20

    def spacer(self, h=6):
        self.y += h

    def image(self, path, w, h, maxw=None):
        maxw = maxw or (self.W - self.ml - self.mr)
        scale = min(1.0, maxw / w)
        dw, dh = w * scale, h * scale
        self._need(dh + 6)
        rect = fitz.Rect(self.ml, self.y, self.ml + dw, self.y + dh)
        self.page.insert_image(rect, filename=str(path))
        self.y += dh + 6

    def save(self, path):
        self._flush()
        self.doc.save(str(path), deflate=True, garbage=4)


# ---------------- 内容 ----------------
def f32(data, off):
    return struct.unpack(">f", data[off:off + 4])[0]


# 各マップ詳細の定義(カテゴリ or 名前マッチ + 深掘り解説)
# kind: "map3d"(ヒートマップ), "scalars"(アドレス指定の値表)
KEY_MAPS = [
    {"kind": "find", "match": lambda t: t.category.startswith("Spark Base") and t.ttype == "3D"
     and "High Fuel Request" in t.name and "Transition" not in t.name,
     "title": "点火ベース(基本進角) Spark Base",
     "what": "回転数×負荷に対する基本点火時期(進角)。エンジンのトルク・燃費・ノック耐性を"
             "決める最重要マップ。高負荷ほど進角を控えめ、低〜中負荷で進角を稼ぐのが一般形。",
     "adjust": "値↑(進角)=トルク/燃費向上だがノックのリスク増。値↓(遅角)=安全側だが出力低下。"
               "高負荷・低回転の領域ほどノックしやすいので、上げるなら1〜2°ずつ・ノック監視下で。",
     "caution": "ハイオク前提の値をレギュラーで使うとノック→エンジン損傷。純正+2°を超える変更は"
                "必ず実走ノックログ(またはノックセンサ監視)とセットで。"},
    {"kind": "find", "match": lambda t: t.category.startswith("Ignition Coil Dwell") and t.ttype == "3D",
     "title": "点火コイル ドウェル時間 Dwell",
     "what": "点火コイルの通電(充電)時間[ms]。回転数×電圧で、必要な火花エネルギーを得る時間を規定。",
     "adjust": "コイル交換(社外・GDIコイル等)時に合わせる。短すぎると高回転・高負荷で失火、"
               "長すぎるとコイル発熱・寿命低下。純正コイルなら基本変更不要。",
     "caution": "むやみに全体を延ばさない(発熱でコイル故障)。変更はコイルメーカー推奨値を基準に。"},
    {"kind": "find", "match": lambda t: t.category.startswith("Fuel Target OL") and t.ttype == "3D",
     "title": "目標空燃比 開ループ Fuel Target OL",
     "what": "高負荷(開ループ)時の目標空燃比(λ/AFR)。全開加速時など、O2フィードバックを離れて"
             "この目標で燃調する領域。",
     "adjust": "リッチ=燃焼温度低下で安全・出力寄り(パワーAFRは概ねλ0.85〜0.88)。リーン=燃費だが"
               "高負荷では危険。高負荷域はリッチ側に余裕を持たせるのが安全。",
     "caution": "高負荷でのリーンは即ノック/溶損リスク。薄くする変更は最小限+実測(ワイドバンドAFR)で確認。"},
    {"kind": "find", "match": lambda t: t.name.startswith("Fuel Target CL - Base") and t.ttype == "3D",
     "title": "目標空燃比 閉ループ Fuel Target CL",
     "what": "閉ループ時の目標空燃比(通常ストイキ=λ1付近)。O2センサでこの目標に追従する。",
     "adjust": "基本は変更不要。触媒保護・排ガスの要なので、ストイキから外す理由がなければ触らない。",
     "caution": "λ1から外すと排ガス悪化・触媒劣化・チェックランプ。原則据え置き。"},
    {"kind": "find", "match": lambda t: t.category.startswith("Variable Cam Timing")
     and t.ttype == "3D" and "DO NOT MODIFY" not in t.category,
     "title": "可変バルブタイミング VVT",
     "what": "回転数×負荷に対する吸気(排気)カムの目標進角。トルクの出方(低速寄り/高速寄り)や"
             "充填効率・内部EGRに影響。",
     "adjust": "中回転トルクを狙って進角、などで特性を調整できる。効果は体感しやすいが最適点は要実測。",
     "caution": "過度な進角はバルブ挙動・ノック・アイドル不安定の原因。小刻みに。'DO NOT MODIFY'系は触らない。"},
    {"kind": "find", "match": lambda t: t.category.startswith("Fuel IPW - Base") and t.ttype == "3D",
     "title": "燃料噴射パルス幅 ベース Fuel IPW Base",
     "what": "インジェクタの基本噴射時間。空気量に対する燃料量の基礎で、空燃比に直結。",
     "adjust": "インジェクタ交換時はここと『オフセット/スケーリング』で容量・デッドタイムを合わせる。"
               "値↑=リッチ/値↓=リーン。",
     "caution": "インジェクタ特性を無視した変更は低開度で大きくズレる。交換時は必ず対応データで。"},
    {"kind": "scalars", "title": "回転リミッタ(レブリミット) Rev Limit",
     "what": "回転数の上限保護。条件別に『燃料カット』と『スロットルカット』がある。",
     "adjust": "値を上げると許容回転が上がる。上げる場合はバルブ・駆動系の許容回転を必ず確認。",
     "caution": "機械的限界を超える設定はエンジン破損に直結。むやみに上げない。",
     "items": [
         (0xC487C, "燃料カット: 温間・MT(実質のレブ)"),
         (0xC4878, "燃料カット: AT(73C0タイマ作動中)"),
         (0xC4870, "燃料カット: 冷間/一次しきい値以下・故障時"),
         (0xC4874, "燃料カット: 冷間/二次・始動時"),
         (0xC53BC, "スロットルカット: クラッチ踏込(ニュートラル空吹かし保護)"),
         (0xC53C0, "スロットルカット: クラッチ非踏込(走行中/実質無効)"),
     ]},
    {"kind": "scalars", "title": "速度リミッタ / アイドル Speed & Idle",
     "what": "車速リミッタの作動条件と、目標アイドル回転の代表値。",
     "adjust": "速度リミッタ解除は自己責任・公道では法令順守。アイドルは高め=安定/低め=静粛(低すぎでストール)。",
     "caution": "車速リミッタの変更は用途・法令を確認。アイドルは冷間時の安定も要確認。",
     "items": [
         (0xC47EC, "車速リミッタ: 作動車速しきい値"),
         (0xC47E4, "車速リミッタ: 作動RPMしきい値"),
     ]},
]


def _fmt(v):
    if _isnan(v):
        return "—"
    if isinstance(v, float):
        return f"{v:.3f}".rstrip("0").rstrip(".") if abs(v) < 1000 else f"{v:.0f}"
    return str(v)


def _table_line(t, rom):
    try:
        grid = rom.read_table(t)
        r, c = rom.dims(t)
    except Exception:  # noqa: BLE001
        return f"{t.name}  @0x{t.address:X}"
    flat = [v for row in grid for v in row if isinstance(v, (int, float)) and not _isnan(v)]
    nm = i18n.translate_table_name(t.name)
    if r * c == 1:
        v = grid[0][0] if grid and grid[0] else float("nan")
        return f"{nm} = {_fmt(v)}   [@0x{t.address:X}]"
    xa, ya = t.x_axis, t.y_axis
    ax = []
    if xa:
        ax.append("X=" + i18n.axis_label(xa.name))
    if ya:
        ax.append("Y=" + i18n.axis_label(ya.name))
    axs = ("  " + " ".join(ax)) if ax else ""
    rng = f"{min(flat):g}〜{max(flat):g}" if flat else "—"
    return f"{nm}  [{r}×{c}]{axs}  範囲 {rng}   [@0x{t.address:X}]"


def section_full_reference(d, rd, rom):
    d._start_page()
    d.h1("4. 全マップ リファレンス(カテゴリ別・全テーブル)")
    d.para("この章は定義に含まれる全テーブル(" + str(len(rd.tables)) +
           "件)の一覧です。各カテゴリに解説と『値を変えると』を付け、"
           "テーブルごとに [次元] 軸 範囲 と現在値(1×1は値)・アドレスを示します。"
           "個別の深掘り解説と調整指針は第3章(主要マップ)を参照してください。", color=d.sub)
    cats = {}
    for t in rd.tables:
        cats.setdefault(t.category, []).append(t)
    for cat in sorted(cats):
        d.h2(i18n.translate_category(cat))
        desc = i18n.describe_category(cat)
        if desc and "未登録" not in desc:
            d.para("解説: " + desc, size=9, color=d.sub, gap=2)
        eff = i18n.effect_of(cat)
        if eff and "意味が分からない" not in eff:
            d.para("値を変えると: " + eff, size=9, color=d.sub, gap=3)
        for t in sorted(cats[cat], key=lambda x: (x.name, x.address)):
            d.para(_table_line(t, rom), size=8.5, color=d.ink, gap=1, lead=1.3, indent=8)
        d.spacer(3)


def section_relationships(d, rd, rom):
    d._start_page()
    d.h1("5. マップ間の連動・関係性")
    d.para("マップは独立ではなく、軸の共有や制御の加減算・クランプで互いに影響します。"
           "1つを変えると関連するマップの効き方も変わるため、関係を理解して調整してください。",
           color=d.ink)

    d.h2("5.1 軸を共有するマップ(同じ軸を変えると全てに影響)")
    d.para("同じ軸(ブレークポイント)を複数のマップが共有しています。その軸の目盛りを変えると、"
           "共有する全マップの格子位置が同時に動きます。主な共有軸:", color=d.sub)
    axis_use = {}
    for t in rd.tables:
        for a in (t.x_axis, t.y_axis):
            if a:
                axis_use.setdefault(a.name, []).append(t)
    for name, ts in sorted(axis_use.items(), key=lambda kv: -len(kv[1]))[:10]:
        cats = sorted({i18n.translate_category(x.category).split(" - ")[0] for x in ts})
        lbl = i18n.axis_label(name)
        d.bullet(f"{lbl}({name}): {len(ts)}マップが共有 — 例: " + "、".join(cats[:5]), size=9)

    d.h2("5.2 点火系の連動")
    d.para("最終点火時期 = 『点火ベース(基本進角)』+ 各種補正、ただし『点火上限』でクランプ:", color=d.ink)
    for b in ["『点火ベース(Spark Base)』= 回転数×負荷の基本進角(出発点)。",
              "『点火ベース補正(ECT/IAT)』『点火補正(ノックリタード/冷間進角/急開/高回転高水温ほか)』"
              "がベースに加減算される。",
              "『点火上限(Spark Limits / 点火ベース上限)』が最終値を進角/遅角側で制限。",
              "→ ベースを上げても上限で頭打ち、補正で実際の点火はずれる。3つをセットで見ること。"]:
        d.bullet(b, size=9)

    d.h2("5.3 燃料系の連動")
    for b in ["空気量(『エンジンセンサ MAF/MAP』特性 →『エンジン負荷 Load スケーリング』)が"
              "負荷(Load)を決め、これが点火・燃料・VVT の“縦軸”になる。",
              "噴射量 = 『目標空燃比(Fuel Target OL/CL)』と『燃料噴射パルス幅(Fuel IPW ベース + "
              "オフセット/スケーリング)』で決定。",
              "さらに『燃料補正(LTFT/STFT・暖機増量・加速増量・減速カット)』で加減。",
              "→ センサ特性やLoadスケーリングを変えると、Loadを軸に持つ“全マップ”の参照位置がずれる"
              "(最も影響範囲が広い)。インジェクタ交換時はIPWベース+オフセットを必ずセットで。"]:
        d.bullet(b, size=9)

    d.h2("5.4 吸気・VVT の連動")
    for b in ["『可変吸気(IMRC/IMTV)』はRPMしきい値で切替わり、充填効率(VE)が変化 → 同じ負荷でも"
              "必要な燃料/点火が変わる。",
              "『可変バルブタイミング(VVT)』もVE・内部EGRを変える → 燃料/点火の最適点に影響。"]:
        d.bullet(b, size=9)

    d.h2("5.5 アイドル系の連動")
    d.para("『目標アイドル回転数』↔『点火アイドル(Spark Idle)』↔『アイドル負荷(空気量)』↔"
           "『アイドル補正』が相互に効き合ってアイドルを維持。どれか単独で詰めると不安定になりやすい。",
           size=9, color=d.ink)

    d.h2("5.6 リミッタ/整合性")
    for b in ["『回転リミッタ(燃料カット)』と『スロットルカット(クラッチ踏込時)』は条件別の対で、"
              "ニュートラル空吹かし時はスロットルカットが先に効く。",
              "どのマップを編集しても『チェックサム表(0xFF650〜)』の再計算が必要(保存時に自動補正)。",
              "『フラッシュカウンタ(0xFFB00)』はECUが書込毎に更新する領域で、読み戻し照合では除外する。"]:
        d.bullet(b, size=9)


def section_notes(d):
    import json
    if not NOTES_PATH.exists():
        return
    try:
        notes = json.loads(NOTES_PATH.read_text(encoding="utf-8")).get("notes", [])
    except Exception:  # noqa: BLE001
        return
    if not notes:
        return
    d._start_page()
    d.h1("6. 補足解説(質問から蓄積した項目)")
    d.para("エディタ使用中に出た疑問への回答を蓄積したものです。"
           "項目が増えたら docs/map_notes.json に追記し、本スクリプトを再実行すると"
           "ここへ一括反映されます。", color=d.sub)
    for n in notes:
        d.h2(n.get("title", n.get("id", "?")))
        meta = []
        if n.get("category_match"):
            meta.append(f"関連カテゴリ: {n['category_match']}")
        if n.get("date"):
            meta.append(f"記録日: {n['date']}")
        if meta:
            d.para("  ".join(meta), size=9, color=d.sub, gap=3)
        for para in n.get("body", []):
            if para.startswith("・"):
                d.bullet(para[1:].strip(), size=10)
            elif para.startswith("重要") or para.startswith("原則") or para.startswith("注意"):
                d.para(para, size=10, color=d.warn)
            else:
                d.para(para, size=10)
        d.spacer(4)


def build():
    rd = ltdef.parse(MAIN_JSON, CALID_JSON)
    data = ROM_PATH.read_bytes()
    rom = Rom(data, rd)
    gen = flashmod.detect_generation(data)
    cal = flashmod.get_cal_id(data)
    TMP.mkdir(parents=True, exist_ok=True)

    d = Doc()
    # ---- 表紙 ----
    d.y = 150
    d.para("NCEC ROM マップエディタ", size=26, color=d.accent, gap=6)
    d.para("詳細取扱説明書", size=18, color=d.ink, gap=20)
    d.para(f"対象ECU: Denso NC / Renesas SH7058   CALID {cal}   世代 {gen}", size=11, color=d.sub)
    d.para(f"ROM: {ROM_PATH.name}   生成日: {datetime.date.today().isoformat()}", size=11, color=d.sub, gap=20)
    d.para("本書は実ROMの値を読み取って自動生成しています。ROM・ツールに変更があれば "
           "tools/gen_manual.py を再実行すると最新版に更新されます。", size=10, color=d.sub)
    d.spacer(14)
    d.para("⚠ 安全上の注意", size=12, color=d.warn, gap=4)
    for b in ["作業は予備(ベンチ)ECUで行う前提。車両搭載ECUへの書き込みは行わないこと。",
              "点火時期・空燃比・リミッタの変更はエンジン破損の危険があります。意味が分からない項目は変更しない。",
              "編集後の保存ではチェックサムを自動補正します。実機書き込みは別途SBLが必要です(後述)。"]:
        d.bullet(b, size=10)

    # ---- §1 概要 ----
    d._start_page()
    d.h1("1. 概要")
    d.para("本ソフトは、2005年式 NCEC ロードスター(LF-VE / SH7058 ECU)の ROM を読み込み、"
           "各種マップ(テーブル)を表示・編集し、チェックサムを補正して保存するための、"
           "自作のオープンな GUI ツールです。LinkECU / Haltech のような純正書き換え型の"
           "チューニング環境を目標にしています。")
    d.h2("できること")
    for b in ["ROM(.bin)の読み込みと、カテゴリ別ツリーからのマップ選択(日本語表示)。",
              "2D/3D マップのヒートマップ表示・セル編集、軸ラベル表示、マップ別の解説。",
              "保存時のチェックサム自動補正(nc-flash と byte 単位で一致を検証済み)。",
              "実機ライブ表示(OBD-II):回転数・負荷・水温・電圧・DTC 等と、現在運転点のセル追従。",
              "ECU 吸い出し(Mode 23 読み出し)、ECU↔ROM 照合、ROM↔ROM 照合。"]:
        d.bullet(b)
    d.h2("現在の制約")
    for b in ["実機への『書き込み(フラッシュ)』には SBL(セカンダリブートローダ)が必要で、"
              "入手待ち。認証・手順・チェックサム等の他要素は実装・検証済みで、SBL を入れれば書込可能。",
              "ベンチ(エンジン停止)ではライブの運転点が静止するため、セル追従は左下に固定されます"
              "(実走・信号注入時に動きます)。"]:
        d.bullet(b)

    # ---- §2 使用方法 ----
    d._start_page()
    d.h1("2. ソフトウェアの使用方法")
    d.h2("画面構成")
    for b in ["左: カテゴリ別ツリー(日本語)。検索欄で名称/カテゴリを絞り込み。",
              "右上: 選択マップの情報(アドレス・次元・単位・型)と解説パネル。",
              "右中: ライブ数値パネル(Live 時)。",
              "右下: ヒートマップ・グリッド(セルをクリック→数値入力→Enterで確定)。"]:
        d.bullet(b)
    d.h2("ツールバーの各ボタン")
    for name, desc in [
        ("ROMを開く", "既定定義(LibreTuner)でROMを読み込み。"),
        ("保存 / 名前を付けて保存", "チェックサムを自動補正して書き出し。"),
        ("ヘルプ", "簡易ヘルプ(docs/editor_help_ja.md)。"),
        ("Live ▶/■", "実機OBDに接続しライブ表示開始/停止。現在運転点のセルを赤枠表示。"),
        ("ECU吸出し", "実機から全1MBを読み出して.bin保存(読み取り専用)。"),
        ("ECUと照合", "実機を読み出し、開いているROMと差分比較。"),
        ("ROM照合", "2つの.binファイルの差分比較。"),
    ]:
        d.bullet(f"{name} … {desc}")
    d.h2("基本ワークフロー")
    d.para("①ROMを開く → ②ツリーからマップ選択 → ③セルを編集(Enter確定)→ "
           "④保存(チェックサム自動補正)。編集値は色(ヒートマップ)で相対位置が分かります。")
    d.h2("セルの色と記号")
    for b in ["ヒートマップ: 低=青 → 高=赤。相対的な値の分布を表します。",
              "「—」(灰): 未使用セル(0xFF等でNaN)。",
              "赤枠: ライブ中の『現在の運転点に当たるセル』。"]:
        d.bullet(b)
    d.h2("ライブ表示と照合の注意")
    for b in ["吸い出し/照合/Live はCANアダプタ(gs_usb)を占有します(同時使用不可)。",
              "吸い出し・照合は認証(プログラミングセッション+セキュリティ解除)を行います"
              "(読み取り専用・消去/書込なし)。終了後は通常セッションへ自動復帰。",
              "実車のOBD2から行う場合は CAN-H(6)/CAN-L(14)に加え GND(4/5)の接続が必須。"]:
        d.bullet(b)
    d.h2("書き込み(フラッシュ)の現状")
    d.para("認証→RoutineControl→RequestDownload(0x8000/0xFF800)→SBL+本体転送(0x400ブロック)"
           "→TransferExit→リセット、という手順まで実装・実機で手前段階まで検証済みです。"
           "唯一 SBL(NC1用・0x1800バイト)の入手が未了のため、実書き込みは保留中です。", color=d.ink)

    # ---- §3 各マップ詳細 ----
    d._start_page()
    d.h1("3. 各マップの詳細と調整方法")
    d.para("ここでは代表的・重要なマップを、実ROMの現在値つきで説明します。"
           "(全テーブルはエディタのツリーから参照できます。)", color=d.sub)

    for spec in KEY_MAPS:
        if spec["kind"] == "find":
            t = next((t for t in rd.tables if spec["match"](t)), None)
            if not t:
                continue
            d.h2(spec["title"])
            d.para(f"対象テーブル: {t.name}  @0x{t.address:X}  "
                   f"(カテゴリ: {i18n.translate_category(t.category)})", size=9, color=d.sub, gap=3)
            d.para("● 概要: " + spec["what"])
            # ヒートマップ
            grid = rom.read_table(t)
            r, c = rom.dims(t)
            xa, ya = t.x_axis, t.y_axis
            xv = rom.read_axis(xa)[:c] if xa else None
            yv = rom.read_axis(ya)[:r] if ya else None
            xl = i18n.axis_label(xa.name) if xa else ""
            yl = i18n.axis_label(ya.name) if ya else ""
            png = TMP / (f"{t.address:X}.png")
            vfmt = "%.2f" if (abs(max(v for row in grid for v in row if not _isnan(v))) < 10) else "%.0f"
            w, h = render_heatmap(grid, xv, yv, xl, yl, spec["title"], png, vfmt)
            d.image(png, w, h, maxw=d.W - d.ml - d.mr)
            d.para("● 値を変えると: " + spec["adjust"])
            d.para("⚠ 注意: " + spec["caution"], color=d.warn)
            d.spacer(4)
        else:  # scalars
            d.h2(spec["title"])
            d.para("● 概要: " + spec["what"])
            for addr, label in spec["items"]:
                val = f32(data, addr)
                d.para(f"    ・{label}: {val:,.0f}  (@0x{addr:X})", size=10, color=d.ink, gap=2)
            d.spacer(2)
            d.para("● 値を変えると: " + spec["adjust"])
            d.para("⚠ 注意: " + spec["caution"], color=d.warn)
            d.spacer(4)

    # ---- §4 全マップ リファレンス / §5 連動 / §6 補足解説(蓄積)----
    section_full_reference(d, rd, rom)
    section_relationships(d, rd, rom)
    section_notes(d)

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    d.save(OUT_PDF)
    pages = d.doc.page_count
    # 中間ヒートマップ画像は PDF に埋め込み済みなので削除
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)
    print("saved:", OUT_PDF, f"({OUT_PDF.stat().st_size} bytes, {pages} pages)")


if __name__ == "__main__":
    build()
