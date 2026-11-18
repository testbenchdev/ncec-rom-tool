#!/usr/bin/env python3
"""統合マニュアル(目次付きHTML)のビルド。

    python tools/build_docs.py          # docs/map_analysis_JA.html と docs/map_analysis.html を作り直す

- 各章の原稿は docs/ の Markdown。章の並びは下の JA / EN に書いてある。
- 「全マップ解析」パート(フローチャート＋カテゴリ別ノート)だけは Markdown から作らず、
  既存の HTML の該当部分をそのまま引き継ぐ(<!-- MAP-ANALYSIS:BEGIN/END --> の間)。
  ここを直すときは HTML を直接編集するか、tools/gen_manual.py が使う docs/map_notes.json と合わせて直す。
- 依存ライブラリなし(Markdown変換は下の小さな自前実装。原稿で使っている記法だけ対応)。
"""
from __future__ import annotations

import datetime
import html
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"

BEGIN, END = "<!-- MAP-ANALYSIS:BEGIN -->", "<!-- MAP-ANALYSIS:END -->"
MAP = "@map"          # パート定義で「全マップ解析(既存HTMLから引き継ぎ)」を表す印

# ---------------------------------------------------------------- 章立て
JA = {
    "lang": "ja",
    "out": "map_analysis_JA.html",
    "title": "NCEC ROM Tool 統合マニュアル",
    "subtitle": "Mazda MX-5 NC（NCEC / LF-VE）純正ECU ・ Renesas SH7058 ・ CAL ID LFG7EG",
    "lead": (
        "導入・使い方・チューニング機能・書き込み・解析メモ・全マップ解析を1本にまとめた文書です。"
        "左の目次（狭い画面では下の目次）から各章へ移動できます。ページ内検索（Ctrl+F）も使えます。"),
    "warn": (
        "⚠ 無保証・自己責任です。点火・燃料・リミッタ・電子スロットルを理解せずに変更すると、エンジンの破損や"
        "走行不能につながります。吸い出した原本は必ず <code>rom_data/</code> に残し、書き込み中は電源を切らないでください。"
        "排ガス関連の監視の無効化やDTCの抑制は、このプロジェクトの対象外です。"),
    "toc_title": "目次",
    "top_title": "先頭へ",
    "sections_label": "この章の内容",
    "parts": [
        ("導入", [("SETUP_ja.md", {"title": "導入手順（Windows）"}),
                 ("setup_wsl_ja.md", {"title": "WSL2 導入（書き込みを高速化）"})]),
        ("使い方", [("editor_help_ja.md", {"plain": True, "title": "エディタの使い方（アプリ内ヘルプ）"}),
                   ("dashboard_chart_ja.md", {"title": "ダッシュボードとログ分析チャート"}),
                   ("live_ramread_ja.md", {"title": "ライブRAM読み出し（Mode23）とノック表示"})]),
        ("チューニング", [("tuning_basics_ja.md", {"title": "チューニングの基本"}),
                         ("tuning_flatshift_ja.md", {"title": "フラットシフト"}),
                         ("tuning_overrun_pops_ja.md", {"title": "アンチラグ（減速時のポップ音）"}),
                         ("revdrop_ja.md", {"title": "回転落ち高速化（レブハング低減）"}),
                         ("tuning_throttle_ja.md", {"title": "スロットル1:1化（電スロ）"})]),
        ("書き込み", [("flash_ja.md", {"title": "ECU書き込み（手順と高速化）"})]),
        ("解析・資料", [("knock_re_ja.md", {"title": "ノック制御の解析"}),
                       ("table_audit_ja.md", {"title": "テーブル監査（定義と実ROMの照合）"}),
                       ("diag_findings.md", {"title": "診断プロトコルの調査記録"}),
                       ("SH7058_hardware_notes.md", {"title": "SH7058 ハードウェア要点"}),
                       ("unit_fixes_i18n.md", {"title": "単位ラベルの修正一覧（日英）"})]),
        ("全マップ解析", MAP),
    ],
    "map_intro": (
        "カテゴリ別に、全テーブル（127カテゴリ / 922テーブル）の役割・値・単位・注意点をまとめたノートです。"
        "数値はベンチECU（<code>rom_data/ecu_readout_yahooauction.bin</code>）の実測で、実車ECUとの差は「P. 実車比較」と、"
        "テーブルごとの差分一覧 <code>docs/ecu_diff_report.html</code>（ROM の値を含むのでローカル保管用。公開リポジトリには無い）にあります。"
        "<span class=\"badge fix\">i18n修正</span> の付いたカテゴリは、単位・軸ラベル・訳を <code>ncecu/i18n.py</code> で直したものです。"),
    # 統合・削除で無くなった原稿名 → いまの章(リンクの付け替え用)
    "aliases": {
        "setup_wsl_newpc_ja.md": "setup_wsl_ja.md", "wsl2_socketcan_ja.md": "setup_wsl_ja.md",
        "can_flash_ready_ja.md": "flash_ja.md", "flash_speed_ja.md": "flash_ja.md",
        "flatshift_oncar_test_ja.md": "tuning_flatshift_ja.md", "revdrop_bench_ja.md": "revdrop_ja.md",
        "map_analysis_JA.md": MAP, "map_analysis_JA.html": MAP,
    },
}

EN = {
    "lang": "en",
    "out": "map_analysis.html",
    "title": "NCEC ROM Tool — Manual",
    "subtitle": "Mazda MX-5 NC (NCEC / LF-VE) factory ECU · Renesas SH7058 · CAL ID LFG7EG",
    "lead": (
        "Setup, usage, tuning features, flashing, analysis notes and the full map analysis in one document. "
        "Use the table of contents on the left (below on narrow screens) or the browser search (Ctrl+F)."),
    "warn": (
        "⚠ No warranty; use at your own risk. Keep the original read-out of every ECU in <code>rom_data/</code> "
        "and do not cut power while flashing. Defeating emissions monitoring or suppressing emissions DTCs is "
        "out of scope for this project."),
    "toc_title": "Contents",
    "top_title": "Back to top",
    "sections_label": "In this chapter",
    "parts": [
        ("Manual", [("manual_EN.md", {"split": True})]),
        ("Appendix", [("unit_fixes_i18n.md", {"title": "Unit-label fixes (bilingual list)"})]),
        ("Full map analysis", MAP),
    ],
    "map_intro": (
        "Notes for every table (127 categories / 922 tables), grouped by subsystem: role, values, units and "
        "cautions. Numbers are the as-read calibration of the bench ECU "
        "(<code>rom_data/ecu_readout_yahooauction.bin</code>); differences to the car's ECU are in "
        "\"P. Real-car comparison\" and in the per-table diff report "
        "<code>docs/ecu_diff_report.html</code> (Japanese; local only, not in the public repository because it contains ROM values). Categories marked <span class=\"badge fix\">i18n fix</span> had a unit, "
        "axis-label or translation correction in <code>ncecu/i18n.py</code>."),
    "aliases": {"map_analysis_EN.md": MAP, "map_analysis.html": MAP, "map_analysis_JA.html": MAP},
}

# ---------------------------------------------------------------- Markdown → HTML (原稿で使う記法のみ)
_FENCE = re.compile(r"^\s*```")
_HEAD = re.compile(r"^(#{1,6})\s+(.*?)\s*#*\s*$")
_HR = re.compile(r"^\s*([-*_])(\s*\1){2,}\s*$")
_LIST = re.compile(r"^(\s*)([-*+]|\d+[.)])\s+(.*)$")
_TSEP = re.compile(r"^\s*\|?\s*:?-{2,}:?\s*(\|\s*:?-{2,}:?\s*)*\|?\s*$")
_CJK = re.compile(r"[　-ヿ㐀-鿿＀-￯]")


class Md:
    """1章ぶんの Markdown を HTML にする。見出しは shift 段だけ下げ、id を振って self.heads に記録。"""

    def __init__(self, chap_id: str, shift: int, resolve):
        self.chap_id = chap_id
        self.shift = shift
        self.resolve = resolve          # ファイル名 → ページ内アンカー('#…') or None
        self.heads: list[tuple[int, str, str]] = []   # (出力レベル, id, テキスト)
        self._n = 0

    # ---- インライン
    def inline(self, s: str) -> str:
        codes: list[str] = []

        def keep_code(m):
            body = m.group(2)
            target = self.resolve(body.strip()) if self.resolve else None
            h = "<code>" + html.escape(body, quote=False) + "</code>"
            if target:
                h = f'<a href="{target}">{h}</a>'
            codes.append(h)
            return f"\x00{len(codes) - 1}\x00"

        s = re.sub(r"(`+)(.+?)\1", keep_code, s)
        s = s.replace("\\|", "|")
        s = html.escape(s, quote=False)
        s = re.sub(r"&lt;br\s*/?&gt;", "<br>", s)

        def image(m):
            return f'<img src="{html.escape(m.group(2))}" alt="{html.escape(m.group(1))}">'

        def link(m):
            text, url = m.group(1), m.group(2).strip()
            if not re.match(r"^(https?:|mailto:|#)", url):
                target = self.resolve(url) if self.resolve else None
                if not target:
                    return text                      # 無くなった文書へのリンク=文字だけ残す
                url = target
            ext = ' target="_blank" rel="noopener"' if url.startswith("http") else ""
            return f'<a href="{html.escape(url)}"{ext}>{text}</a>'

        s = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", image, s)
        s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", link, s)
        s = re.sub(r'(?<![">=/\w])(https?://[^\s<>()（）、。]+)',
                   r'<a href="\1" target="_blank" rel="noopener">\1</a>', s)
        s = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", s)
        s = re.sub(r"(?<![*\w])\*(?!\s)([^*\n]+?)(?<!\s)\*(?![*\w])", r"<i>\1</i>", s)
        return re.sub(r"\x00(\d+)\x00", lambda m: codes[int(m.group(1))], s)

    @staticmethod
    def _join(lines: list[str]) -> str:
        """折り返した行をつなぐ。日本語どうしは空白を入れない。行末2空白は改行。"""
        out = ""
        for ln in lines:
            hard = ln.endswith("  ") or ln.endswith("\\")
            ln = ln.rstrip("\\").strip()
            if out and not out.endswith("<br>"):
                if not (_CJK.match(out[-1]) or _CJK.match(ln[:1] or " ")):
                    out += " "
            out += ln
            if hard:
                out += "<br>"
        return out.removesuffix("<br>")

    # ---- ブロック
    def convert(self, text: str) -> str:
        return self._blocks(text.replace("\r\n", "\n").split("\n"))

    def _blocks(self, lines: list[str]) -> str:
        out: list[str] = []
        i, n = 0, len(lines)
        while i < n:
            ln = lines[i]
            if not ln.strip():
                i += 1
                continue
            if _FENCE.match(ln):
                j = i + 1
                while j < n and not _FENCE.match(lines[j]):
                    j += 1
                ind = len(ln) - len(ln.lstrip())
                body = "\n".join(l[ind:] if l[:ind].strip() == "" else l for l in lines[i + 1:j])
                out.append("<pre><code>" + html.escape(body, quote=False) + "</code></pre>")
                i = j + 1
                continue
            m = _HEAD.match(ln)
            if m:
                out.append(self._heading(len(m.group(1)), m.group(2)))
                i += 1
                continue
            if _HR.match(ln):
                out.append("<hr>")
                i += 1
                continue
            if ln.lstrip().startswith(">"):
                j = i
                buf = []
                while j < n and lines[j].lstrip().startswith(">"):
                    buf.append(re.sub(r"^\s*>\s?", "", lines[j]))
                    j += 1
                out.append('<blockquote>' + self._blocks(buf) + "</blockquote>")
                i = j
                continue
            if "|" in ln and i + 1 < n and _TSEP.match(lines[i + 1]) and "-" in lines[i + 1]:
                j = i + 2
                while j < n and "|" in lines[j] and lines[j].strip():
                    j += 1
                out.append(self._table(lines[i:j]))
                i = j
                continue
            if _LIST.match(ln):
                html_, i = self._list(lines, i)
                out.append(html_)
                continue
            j = i
            buf = []
            while j < n and lines[j].strip() and not (
                    _FENCE.match(lines[j]) or _HEAD.match(lines[j]) or _HR.match(lines[j])
                    or lines[j].lstrip().startswith(">") or _LIST.match(lines[j])
                    or ("|" in lines[j] and j + 1 < n and _TSEP.match(lines[j + 1]) and "-" in lines[j + 1])):
                buf.append(lines[j])
                j += 1
            out.append("<p>" + self.inline(self._join(buf)) + "</p>")
            i = j
        return "\n".join(out)

    def _heading(self, level: int, text: str) -> str:
        lv = min(6, level + self.shift)
        self._n += 1
        hid = f"{self.chap_id}-{self._n}"
        plain = re.sub(r"<[^>]+>", "", self.inline(text))
        self.heads.append((lv, hid, html.unescape(plain)))
        return f'<h{lv} id="{hid}">{self.inline(text)}</h{lv}>'

    @staticmethod
    def _cells(row: str) -> list[str]:
        row = row.strip()
        row = row[1:] if row.startswith("|") else row
        row = row[:-1] if row.endswith("|") and not row.endswith("\\|") else row
        cells, cur, in_code, k = [], "", False, 0
        while k < len(row):
            ch = row[k]
            if ch == "`":
                in_code = not in_code
            if ch == "\\" and k + 1 < len(row) and row[k + 1] == "|":
                cur += "\\|"
                k += 2
                continue
            if ch == "|" and not in_code:
                cells.append(cur.strip())
                cur = ""
            else:
                cur += ch
            k += 1
        cells.append(cur.strip())
        return cells

    def _table(self, rows: list[str]) -> str:
        head = self._cells(rows[0])
        out = ['<div class="tw"><table><thead><tr>']
        out += [f"<th>{self.inline(c)}</th>" for c in head]
        out.append("</tr></thead><tbody>")
        for r in rows[2:]:
            cells = self._cells(r)
            cells += [""] * (len(head) - len(cells))
            out.append("<tr>" + "".join(f"<td>{self.inline(c)}</td>" for c in cells[:max(len(head), len(cells))]) + "</tr>")
        out.append("</tbody></table></div>")
        return "".join(out)

    def _list(self, lines: list[str], i: int) -> tuple[str, int]:
        """リスト1個(同じインデント・同じ種類)を変換。入れ子と、項目に続く行/コード/表も扱う。"""
        m = _LIST.match(lines[i])
        base = len(m.group(1))
        ordered = m.group(2)[0].isdigit()
        items: list[list[str]] = []
        n = len(lines)
        while i < n:
            m = _LIST.match(lines[i])
            if not m or len(m.group(1)) != base or m.group(2)[0].isdigit() != ordered:
                break
            content_indent = base + len(m.group(2)) + 1
            body = [m.group(3)]
            i += 1
            while i < n:
                ln = lines[i]
                if not ln.strip():
                    # 空行の次が「この項目より深い行」なら項目の続き
                    k = i + 1
                    while k < n and not lines[k].strip():
                        k += 1
                    if k < n and (len(lines[k]) - len(lines[k].lstrip())) > base:
                        body.append("")
                        i += 1
                        continue
                    break
                ind = len(ln) - len(ln.lstrip())
                m2 = _LIST.match(ln)
                if m2 and ind <= base:
                    break                           # 次の項目 or 外側のリスト
                if ind <= base and (_HEAD.match(ln) or _HR.match(ln) or _FENCE.match(ln)
                                    or ln.lstrip().startswith(">")):
                    break
                body.append(ln[min(ind, content_indent):] if ind > base else ln.strip())
                i += 1
            items.append(body)
        tag = "ol" if ordered else "ul"
        parts = [f"<{tag}>"]
        for body in items:
            inner = self._blocks(body)
            # 1段落だけの項目は <p> を外す(行間を詰める)
            if inner.count("<p>") == 1 and inner.startswith("<p>"):
                inner = inner.replace("<p>", "", 1).replace("</p>", "", 1)
            parts.append(f"<li>{inner}</li>")
        parts.append(f"</{tag}>")
        return "".join(parts), i


# ---------------------------------------------------------------- 原稿の読み込み
def _title_and_body(text: str) -> tuple[str, str]:
    lines = text.replace("\r\n", "\n").split("\n")
    for k, ln in enumerate(lines):
        if ln.strip():
            m = _HEAD.match(ln)
            if m and len(m.group(1)) == 1:
                return m.group(2), "\n".join(lines[k + 1:])
            break
    return "", text


def _plain_to_md(text: str) -> str:
    """アプリ内ヘルプ(■ 見出しのテキスト)を Markdown に直す。本文は桁をそろえたまま出す。"""
    lines = text.replace("\r\n", "\n").split("\n")
    out, buf = [], []

    def flush():
        while buf and not buf[-1].strip():
            buf.pop()
        if buf:
            out.extend(["```", *buf, "```", ""])
        buf.clear()

    for k, ln in enumerate(lines):
        if k == 0:
            out.append("# " + ln.strip())
            continue
        if ln.strip() and set(ln.strip()) <= set("=＝"):
            continue
        if ln.startswith("■"):
            flush()
            out.extend(["## " + ln.lstrip("■ ").strip(), ""])
        else:
            if buf or ln.strip():
                buf.append(ln)
    flush()
    return "\n".join(out)


def _slug(name: str) -> str:
    return "ch-" + re.sub(r"[^a-z0-9]+", "-", pathlib.Path(name).stem.lower()).strip("-")


# ---------------------------------------------------------------- 全マップ解析パートの引き継ぎ
def _map_region(out_path: pathlib.Path) -> str:
    """既存の出力HTMLから「全マップ解析」部分を取り出す。"""
    if not out_path.exists():
        raise SystemExit(f"{out_path.name} がありません(全マップ解析パートの引き継ぎ元)。")
    s = out_path.read_text(encoding="utf-8")
    if BEGIN in s and END in s:
        region = s[s.index(BEGIN) + len(BEGIN):s.index(END)]
    else:                                   # v2.70 以前の単独HTMLからの初回移行
        a = s.index('<h2 id="flow">')
        b = s.rindex("<hr><p class=\"sub\">")
        tail = s[b + 4:s.index("</p>", b) + 4]          # 定義名typoなどの注記は残す
        tail = re.sub(r"^<p class=\"sub\">.*?(?=定義名のtypo|Definition-name typos)", '<p class="sub">', tail, flags=re.S)
        region = s[a:b] + "<hr>" + tail
    region = region.replace("ncec_rom_dump.bin", "ecu_readout_yahooauction.bin").strip()

    # カテゴリのカード(<h3>)に id を振る(目次から飛べるように)。note ID があればそれを使う。
    def add_id(m):
        return f'<div class="cat">\n<h3 id="n-{m.group(2)}">{m.group(1)}</h3>\n<div class="meta">{m.group(3)}note: {m.group(2)}'
    region = re.sub(r'<div class="cat">\s*<h3>(.*?)</h3>\s*<div class="meta">(?=[^<]*?note: ([a-z0-9\-]+))([^<]*?)note: \2',
                    add_id, region, flags=re.S)
    return region


def _region_heads(region: str):
    """[(h2 id, タイトル, [(h3 id, タイトル), …]), …]"""
    out = []
    for m in re.finditer(r'<h2 id="([^"]+)">(.*?)</h2>|<h3 id="([^"]+)">(.*?)</h3>', region, flags=re.S):
        if m.group(1):
            out.append((m.group(1), _strip(m.group(2)), []))
        elif out:
            out[-1][2].append((m.group(3), _strip(m.group(4))))
    return out


def _strip(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h))).strip()


# ---------------------------------------------------------------- 組み立て
def build(cfg: dict, version: str, today: str) -> tuple[pathlib.Path, dict]:
    out_path = DOCS / cfg["out"]
    region = _map_region(out_path)

    # 1) 章の一覧を先に作る(相互リンクの解決に使う)
    chapters = []                 # dict(part, id, title, md_text, shift, src)
    file_anchor: dict[str, str] = {}
    for pi, (part, items) in enumerate(cfg["parts"], 1):
        if items == MAP:
            file_anchor[MAP] = f"#part-{pi}"
            continue
        for name, opt in items:
            text = (DOCS / name).read_text(encoding="utf-8")
            if opt.get("plain"):
                text = _plain_to_md(text)
            title, body = _title_and_body(text)
            if opt.get("split"):
                chunks = re.split(r"(?m)^(?=## )", body)
                lead = chunks[0].strip()
                for ci, ch in enumerate(chunks[1:], 1):
                    t, b = ch.split("\n", 1)
                    chapters.append({"part": pi, "id": f"{_slug(name)}-{ci}", "title": t[3:].strip(),
                                     "md": b, "shift": 0, "src": name, "lead": lead if ci == 1 else ""})
                file_anchor[name] = f"#{_slug(name)}-1"
            else:
                chapters.append({"part": pi, "id": _slug(name), "title": opt.get("title") or title or name,
                                 "md": body, "shift": 1, "src": name, "lead": "",
                                 "orig": title if opt.get("title") and title != opt.get("title") else ""})
                file_anchor[name] = f"#{_slug(name)}"
    for old, new in cfg["aliases"].items():
        if new in file_anchor:
            file_anchor.setdefault(old, file_anchor[new])

    def resolve(ref: str):
        ref = ref.split("#")[0].strip()
        base = ref.replace("\\", "/").split("/")[-1]
        if not base.endswith((".md", ".html")):
            return None
        if ref not in (base, "docs/" + base, "./" + base):
            return None
        return file_anchor.get(base)

    # 2) 各章を変換
    for ch in chapters:
        md = Md(ch["id"], ch["shift"], resolve)
        if ch["lead"]:
            ch["lead_html"] = Md(ch["id"] + "-lead", 1, resolve).convert(ch["lead"])
        ch["html"] = md.convert(ch["md"])
        ch["heads"] = [(lv, hid, t) for lv, hid, t in md.heads if lv == 3]

    # 3) 目次(サイドバー＋本文先頭)
    region_heads = _region_heads(region)
    side, top = [], []
    for pi, (part, items) in enumerate(cfg["parts"], 1):
        side.append(f'<div class="pt"><a href="#part-{pi}">{html.escape(part)}</a></div><ul>')
        top.append(f'<li><a href="#part-{pi}"><b>{html.escape(part)}</b></a><ul>')
        if items == MAP:
            entries = [(hid, t, subs) for hid, t, subs in region_heads]
        else:
            entries = [(c["id"], c["title"], [(hid, t) for _lv, hid, t in c["heads"]])
                       for c in chapters if c["part"] == pi]
        for hid, title, subs in entries:
            t = html.escape(title)
            top.append(f'<li><a href="#{hid}">{t}</a></li>')
            if subs:
                sub = "".join(f'<li><a href="#{sid}">{html.escape(st)}</a></li>' for sid, st in subs)
                side.append(f'<li><details><summary><a href="#{hid}">{t}</a></summary><ul>{sub}</ul></details></li>')
            else:
                side.append(f'<li class="leaf"><a href="#{hid}">{t}</a></li>')
        side.append("</ul>")
        top.append("</ul></li>")

    # 4) 本文
    body = []
    for pi, (part, items) in enumerate(cfg["parts"], 1):
        body.append(f'<h1 class="part" id="part-{pi}"><span>{pi}</span>{html.escape(part)}</h1>')
        if items == MAP:
            body.append(f'<p class="sub">{cfg["map_intro"]}</p>')
            body.append(BEGIN + "\n" + region + "\n" + END)
            continue
        for c in [c for c in chapters if c["part"] == pi]:
            if c.get("lead_html"):
                body.append(f'<div class="lead">{c["lead_html"]}</div>')
            body.append(f'<section class="chap"><h2 id="{c["id"]}">{html.escape(c["title"])}</h2>')
            if c.get("orig"):
                body.append(f'<p class="sub">{html.escape(c["orig"])} <span class="src">（原稿 docs/{html.escape(c["src"])}）</span></p>')
            if len(c["heads"]) >= 3:
                links = " ・ ".join(f'<a href="#{hid}">{html.escape(t)}</a>' for _lv, hid, t in c["heads"])
                body.append(f'<p class="mini"><b>{cfg["sections_label"]}</b>：{links}</p>')
            body.append(c["html"])
            body.append("</section>")

    page = PAGE.format(
        lang=cfg["lang"], title=html.escape(cfg["title"]), subtitle=html.escape(cfg["subtitle"]),
        lead=cfg["lead"], warn=cfg["warn"], version=html.escape(version), today=today,
        toc_title=cfg["toc_title"], top_title=cfg["top_title"],
        side="\n".join(side), top="\n".join(top), body="\n".join(body), css=CSS, js=JS)
    out_path.write_text(page, encoding="utf-8", newline="\n")
    stats = {"chapters": len(chapters), "map_groups": len(region_heads),
             "map_notes": sum(len(s) for _h, _t, s in region_heads), "bytes": len(page.encode("utf-8"))}
    return out_path, stats


CSS = r""":root{--bg:#ffffff;--fg:#1a1e24;--muted:#5b6672;--card:#f6f8fa;--line:#d7dde3;--accent:#2b6cb0;
--s:#eef4fb;--h:#fff4e6;--f:#eaf7ef;--k:#f3eefb;--a:#fdeeef;--i:#eefbfa;--m:#fbf0e8;--l:#f0f1f3;--o:#eef0f2;--box:#ffffff;--arh:#8a97a4;}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#0f1317;--fg:#e6e9ec;--muted:#9aa6b2;--card:#161b21;--line:#2a323b;--accent:#6fb0e8;
--s:#15202b;--h:#2a2318;--f:#14241b;--k:#201a2b;--a:#2b1a1d;--i:#132423;--m:#241b12;--l:#1a1e22;--o:#171b1f;--box:#1b2128;--arh:#7d8b98;}}
:root[data-theme="dark"]{--bg:#0f1317;--fg:#e6e9ec;--muted:#9aa6b2;--card:#161b21;--line:#2a323b;--accent:#6fb0e8;
--s:#15202b;--h:#2a2318;--f:#14241b;--k:#201a2b;--a:#2b1a1d;--i:#132423;--m:#241b12;--l:#1a1e22;--o:#171b1f;--box:#1b2128;--arh:#7d8b98;}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{background:var(--bg);color:var(--fg);margin:0;font:15px/1.7 -apple-system,BlinkMacSystemFont,"Segoe UI","Hiragino Sans","Hiragino Kaku Gothic ProN","Yu Gothic","Meiryo",sans-serif;}
.wrap{max-width:1000px;margin:0 auto;padding:28px 16px 80px;}
h1{font-size:25px;margin:.2em 0 .1em;line-height:1.3}
h2{font-size:20px;margin:2.2em 0 .4em;padding-top:.3em;border-top:2px solid var(--line)}
h3{font-size:16px;margin:1.4em 0 .3em}
.sub{color:var(--muted);font-size:13.5px;margin:.2em 0 1.2em}
.warn{background:var(--a);border:1px solid var(--line);border-radius:8px;padding:10px 14px;margin:14px 0;font-size:13px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.toc{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px 18px;margin:18px 0}
.toc ol{margin:.3em 0;padding-left:1.4em}
.toc li{margin:.15em 0}
.cat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;margin:12px 0;}
.cat .meta{color:var(--muted);font-size:12px;font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;margin:.1em 0 .5em}
.cat ul{margin:.3em 0;padding-left:1.2em}
.cat li{margin:.3em 0}
.badge{display:inline-block;font-size:11px;font-weight:600;border-radius:5px;padding:1px 7px;margin-left:8px;vertical-align:middle}
.fix{background:var(--h);color:#9a6a00;border:1px solid #e3c389}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]) .fix{color:#e8b765;border-color:#5a4826}}
.ct{color:var(--muted);font-weight:400;font-size:13px}
.flowwrap{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px;margin:12px 0}
.flowwrap figcaption{color:var(--muted);font-size:12.5px;margin:2px 4px 8px}
svg.flow{width:100%;height:auto;display:block}
svg.flow .n{stroke:var(--line);stroke-width:1.2;fill:var(--box)}
svg.flow .s{fill:var(--s)}svg.flow .h{fill:var(--h)}svg.flow .f{fill:var(--f)}svg.flow .k{fill:var(--k)}
svg.flow .a{fill:var(--a)}svg.flow .i{fill:var(--i)}svg.flow .m{fill:var(--m)}svg.flow .l{fill:var(--l)}svg.flow .o{fill:var(--o)}
svg.flow .t{fill:var(--fg);font-size:11.5px;text-anchor:middle;font-family:inherit}
svg.flow .lbl{fill:var(--muted);font-size:11px;text-anchor:middle}
svg.flow .e{stroke:var(--arh);stroke-width:1.4;fill:none}
svg.flow .arh{fill:var(--arh)}
.legend{font-size:12px;color:var(--muted);margin:6px 2px}
.top{position:fixed;right:14px;bottom:14px;background:var(--accent);color:#fff;border-radius:50%;width:42px;height:42px;display:flex;align-items:center;justify-content:center;font-size:20px;box-shadow:0 2px 8px rgba(0,0,0,.25)}
.top:hover{text-decoration:none}
hr{border:0;border-top:1px solid var(--line);margin:1.6em 0}
@media print{.top,.toc{display:none}body{font-size:11px}.cat,.flowwrap{break-inside:avoid;border-color:#bbb}svg.flow .n{stroke:#999}}
/* ---- 統合マニュアル用の追加 ---- */
html[lang="en"] body{font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif}
.layout{display:flex;align-items:flex-start;max-width:1320px;margin:0 auto}
.side{position:sticky;top:0;flex:0 0 290px;height:100vh;overflow:auto;padding:18px 10px 40px 16px;border-right:1px solid var(--line);font-size:13px;line-height:1.45}
.side .ttl{font-weight:700;font-size:14px;margin:0 0 .6em}
.side .pt{font-weight:700;margin:1em 0 .25em;color:var(--muted);font-size:12px;letter-spacing:.04em}
.side .pt a{color:inherit}
.side ul{list-style:none;margin:0;padding:0}
.side li{margin:.12em 0}
.side li.leaf{padding-left:15px}
.side details>summary{cursor:pointer;list-style-position:outside;margin-left:15px}
.side details ul{margin:.15em 0 .4em 15px;padding-left:9px;border-left:1px solid var(--line);font-size:12.5px}
.side a.on{font-weight:700;text-decoration:underline}
.wrap{flex:1 1 auto;min-width:0;max-width:1000px;margin:0}
h1.part{font-size:23px;margin:2.6em 0 .2em;padding:.5em .7em;background:var(--card);border:1px solid var(--line);border-left:6px solid var(--accent);border-radius:8px}
h1.part span{display:inline-block;min-width:1.5em;color:var(--accent)}
.chap>h2{margin-top:2.4em}
.chap h3{font-size:17px;margin:1.7em 0 .35em;padding-bottom:.15em;border-bottom:1px solid var(--line)}
.chap h4{font-size:15px;margin:1.3em 0 .3em}
.chap h5{font-size:14px;margin:1.1em 0 .25em;color:var(--muted)}
.mini{font-size:12.5px;color:var(--muted);background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 12px;margin:.6em 0 1em}
.lead{margin:.6em 0}
.toc.cols>ol{columns:2;column-gap:28px;list-style:none;padding-left:0}
.toc.cols>ol>li{break-inside:avoid;margin:0 0 .7em}
.toc.cols ul{margin:.2em 0;padding-left:1.2em;list-style:disc}
.tw{overflow-x:auto;margin:.8em 0}
table{border-collapse:collapse;font-size:13.5px;width:100%}
th,td{border:1px solid var(--line);padding:5px 9px;text-align:left;vertical-align:top}
th{background:var(--card);white-space:nowrap}
code{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:.92em;background:var(--card);border:1px solid var(--line);border-radius:4px;padding:0 4px}
pre{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 12px;overflow-x:auto;line-height:1.5;font-size:13px}
pre code{background:none;border:0;padding:0;white-space:pre-wrap;word-break:break-word}
blockquote{margin:.9em 0;padding:.5em 1em;background:var(--card);border-left:4px solid var(--accent);border-radius:0 8px 8px 0}
blockquote p{margin:.35em 0}
img{max-width:100%}
.ver{color:var(--muted);font-size:12.5px}
.src{font-size:11.5px;opacity:.8}
@media (max-width:980px){.layout{display:block}.side{display:none}.wrap{margin:0 auto}}
@media print{.side{display:none}.layout{display:block}pre,table{break-inside:avoid}}
"""

JS = r"""(function(){
  var links={}, cur=null;
  document.querySelectorAll('.side a[href^="#"]').forEach(function(a){links[a.getAttribute('href').slice(1)]=a;});
  var heads=[].slice.call(document.querySelectorAll('h1.part,.wrap h2[id],.wrap h3[id]')).filter(function(h){return links[h.id];});
  function spy(){
    var y=window.scrollY+90, best=null;
    for(var i=0;i<heads.length;i++){ if(heads[i].offsetTop<=y) best=heads[i]; else break; }
    if(best && best!==cur){
      if(cur && links[cur.id]) links[cur.id].classList.remove('on');
      cur=best; var a=links[cur.id]; a.classList.add('on');
      var d=a.closest('details'); if(d && !d.open && cur.tagName==='H3') d.open=true;
      var s=document.querySelector('.side'), r=a.getBoundingClientRect();
      if(r.top<60||r.bottom>window.innerHeight-40) s.scrollTop+=r.top-window.innerHeight/2;
    }
  }
  var t=null; window.addEventListener('scroll',function(){ if(t) return; t=setTimeout(function(){t=null;spy();},120); });
  spy();
})();"""

PAGE = """<!doctype html><html lang="{lang}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title}</title>
<style>
{css}</style></head>
<body><div class="layout">
<nav class="side"><div class="ttl">{toc_title}</div>
{side}
</nav>
<div class="wrap" id="top">
<h1>{title}</h1>
<p class="sub">{subtitle}</p>
<p class="ver">v{version} ・ {today}</p>
<p>{lead}</p>
<div class="warn">{warn}</div>
<div class="toc cols"><b>{toc_title}</b><ol>
{top}
</ol></div>
{body}
<a href="#top" class="top" title="{top_title}">↑</a>
</div></div>
<script>
{js}</script>
</body></html>
"""


def main() -> int:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    today = datetime.date.today().isoformat()
    for cfg in (JA, EN):
        path, st = build(cfg, version, today)
        print(f"{path.relative_to(ROOT)}: {st['chapters']} chapters + {st['map_groups']} map groups "
              f"({st['map_notes']} notes), {st['bytes'] / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
