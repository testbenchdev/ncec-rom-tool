"""GitHub 公開ガイド PDF を生成する。

出力: docs/github_publish_guide.pdf
内容: 公開手順 / そのまま使える文面(説明文・コミットコマンド) / 著作権チェック / ライセンス。
依存: PyMuPDF のみ。 使い方: python tools/gen_publish_guide.py
"""
from __future__ import annotations

import datetime
import pathlib

import pymupdf as fitz

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "github_publish_guide.pdf"
CONSOLA = r"C:\Windows\Fonts\consola.ttf"


class Doc:
    def __init__(self):
        self.doc = fitz.open()
        self.font = fitz.Font("cjk")
        try:
            self.mono = fitz.Font(fontfile=CONSOLA)
        except Exception:  # noqa: BLE001
            self.mono = self.font
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
        self._tw(self.sub).append((self.W - self.mr - 26, self.H - 28),
                                  f"- {self.doc.page_count} -", font=self.font, fontsize=9)

    def _flush(self):
        for color, tw in self._writers.items():
            tw.write_text(self.page, color=color)
        self._writers = {}

    def _tw(self, color):
        if color not in self._writers:
            self._writers[color] = fitz.TextWriter(self.page.rect)
        return self._writers[color]

    def _wrap(self, text, size, width, font=None):
        font = font or self.font
        out = []
        for raw in text.split("\n"):
            if raw == "":
                out.append("")
                continue
            cur = ""
            for ch in raw:
                if font.text_length(cur + ch, size) > width and cur:
                    out.append(cur)
                    cur = ch
                else:
                    cur += ch
            out.append(cur)
        return out

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

    def bullet(self, text, size=10, gap=2, indent=12, color=None):
        color = color or self.ink
        width = self.W - self.ml - self.mr - indent - 12
        lh = size * 1.4
        for k, ln in enumerate(self._wrap(text, size, width)):
            self._need(lh)
            if k == 0:
                self._tw(self.accent).append((self.ml + indent, self.y + size), "•",
                                             font=self.font, fontsize=size)
            self._tw(color).append((self.ml + indent + 12, self.y + size), ln,
                                   font=self.font, fontsize=size)
            self.y += lh
        self.y += gap

    def h1(self, text):
        self._need(42)
        self.y += 6
        self._tw(self.accent).append((self.ml, self.y + 16), text, font=self.font, fontsize=16)
        self.y += 22
        self.page.draw_line((self.ml, self.y), (self.W - self.mr, self.y),
                            color=self.accent, width=1.1)
        self.y += 10

    def h2(self, text):
        self._need(26)
        self.y += 3
        self._tw(self.accent).append((self.ml, self.y + 12), text, font=self.font, fontsize=12.5)
        self.y += 19

    def code(self, text):
        """ASCII のコード/コマンドブロック(等幅・薄背景)。"""
        size, lead, pad = 9, 1.35, 6
        lines = []
        for raw in text.split("\n"):
            lines += self._wrap(raw, size, self.W - self.ml - self.mr - pad * 2, font=self.mono) or [""]
        lh = size * lead
        h = pad * 2 + lh * len(lines)
        self._need(h + 4)
        x0, y0 = self.ml, self.y
        self.page.draw_rect(fitz.Rect(x0, y0, self.W - self.mr, y0 + h),
                            fill=(0.94, 0.95, 0.97), color=(0.78, 0.80, 0.84), width=0.6)
        yy = y0 + pad
        for ln in lines:
            self._tw((0.10, 0.12, 0.16)).append((x0 + pad, yy + size), ln,
                                                font=self.mono, fontsize=size)
            yy += lh
        self.y = y0 + h + 6

    def spacer(self, h=6):
        self.y += h

    def save(self, path):
        self._flush()
        self.doc.save(str(path), deflate=True, garbage=4)


def build():
    d = Doc()
    # 表紙
    d.y = 120
    d.para("NCEC ROM Map Editor", size=24, color=d.accent, gap=4)
    d.para("GitHub 公開ガイド(手順・文面・著作権チェック)", size=15, color=d.ink, gap=16)
    d.para(f"生成日: {datetime.date.today().isoformat()}   対象: 自作の NC(NCEC/SH7058)ROMツール",
           size=10, color=d.sub, gap=10)
    d.para("本書は『何を公開し・何を公開してはいけないか』『GitHubへの投稿手順』"
           "『そのまま使える説明文』をまとめたものです。付属ファイル README.md / .gitignore / "
           "requirements.txt は作成済みで、そのままコミットできます。", color=d.ink)
    d.spacer(8)
    d.para("⚠ 最重要: マツダのROM(ncec_rom_dump.bin)やルネサスのマニュアルPDF等の"
           "第三者著作物は絶対に公開しないこと(.gitignore で除外済み)。", color=d.warn)

    # 1. 公開前チェック
    d._start_page()
    d.h1("1. 公開前チェック(著作権で“含めない”もの)")
    d.para("オープンソース公開で最も重要なのは、他者の著作物を混ぜないことです。以下は"
           "リポジトリに含めないでください(付属 .gitignore で自動除外されます)。")
    d.bullet("ECU ファームウェア/ROMイメージ(*.bin、ncec_rom_dump.bin)= マツダの著作物。",
             color=d.ink)
    d.bullet("SBL / 非公開IP(入手できても公開しない)。", color=d.ink)
    d.bullet("Renesas SH7058 マニュアル(docs/sh7058_plain_manual.pdf、REN_*.pdf)= ルネサスの著作物。")
    d.bullet("他ツールの配布物(nc-flash-*.zip、mx5studio 等)。")
    d.bullet("ログ/キャプチャ(logs/、*.raw)、個人設定(dashboard_layout.json)。")
    d.spacer(4)
    d.para("コミット前に必ず確認:", color=d.ink)
    d.code("cd C:\\Users\\satoru\\Downloads\\NECEECU\n"
           "git status            # 一覧に .bin / 各種PDF(Renesas) が無いことを確認\n"
           "git check-ignore ncec_rom_dump.bin   # 除外されていれば行が返る")
    d.para("※ マップ定義(defs/libretuner/*.json)は LibreTuner/speepsio 氏の著作物(GPL)。"
           "同梱する場合はクレジットとGPL表記が必要です。迷う場合は同梱せず、README の手順で"
           "利用者にダウンロードしてもらう方式が安全です(付属 README はこの方式)。", color=d.sub)

    # 2. リポジトリ構成
    d.h1("2. 公開する中身(推奨構成)")
    d.para("公開するのは“自分が書いたコードと文書”です:")
    d.code("ncec_editor.py  ncec_dashboard.py      # GUI\n"
           "ncecu/*.py                              # ライブラリ(flash, rom, i18n, livelog, ...)\n"
           "tools/*.py                              # 吸い出し/比較/取説生成 等\n"
           "docs/*.md                               # ドキュメント(自作)\n"
           "README.md  LICENSE  .gitignore  requirements.txt")
    d.para("defs/libretuner/ は上記の著作権方針に従って判断。生成PDF(取説)は任意で同梱可"
           "(自分のROM値を含むので、気になる場合は外す)。", color=d.sub)

    # 3. ライセンス
    d.h1("3. ライセンスとクレジット")
    d.para("参照した LibreTuner / nc-flash が GPL 系のため、本プロジェクトも "
           "GNU GPL v3.0 を推奨します(互換・オープン維持)。")
    d.bullet("GitHub でリポジトリ作成時、または Add file → Create new file → ファイル名 "
             "'LICENSE' で GitHub のテンプレート(GNU GPLv3)を選ぶと正式な全文が入ります。")
    d.bullet("README の『クレジット』に LibreTuner(speepsio 氏の定義)、RomDrop、nc-flash、"
             "Renesas マニュアルを明記(付属 README に記載済み)。")
    d.bullet("『公開情報を参考にゼロから再実装。非公開IF(SBL等)は含まない』と明記しておくと誠実。")

    # 4. 手順(Web + git)
    d._start_page()
    d.h1("4. 公開手順")
    d.h2("A. GitHub でリポジトリを作成(ブラウザ)")
    d.bullet("github.com にログイン → 右上 [+] → New repository。")
    d.bullet("Repository name 例: ncec-rom-tool  /  Description は第5章の文面を貼る。")
    d.bullet("Public を選択。README/.gitignore/License は“追加しない”(手元に用意済みのため)。"
             "※ License だけ GitHub で付けたい場合は GPLv3 を選択。")
    d.bullet("Create repository → 表示される URL(https://github.com/<id>/ncec-rom-tool.git)を控える。")
    d.h2("B. ローカルから初回コミット&プッシュ(PowerShell)")
    d.para("git 未導入なら https://git-scm.com/download/win からインストール。初回のみ名前設定:")
    d.code("git config --global user.name  \"Your Name\"\n"
           "git config --global user.email \"you@example.com\"")
    d.para("プロジェクトフォルダで:")
    d.code("cd C:\\Users\\satoru\\Downloads\\NECEECU\n"
           "git init\n"
           "git add .\n"
           "git status                 # ← ここで .bin やRenesas PDF が無いか最終確認\n"
           "git commit -m \"Initial public release: NCEC ROM Map Editor\"\n"
           "git branch -M main\n"
           "git remote add origin https://github.com/<id>/ncec-rom-tool.git\n"
           "git push -u origin main")
    d.para("以後の更新は:", color=d.sub)
    d.code("git add -A\n"
           "git commit -m \"変更内容の説明\"\n"
           "git push")
    d.h2("C. 代替手段")
    d.bullet("GitHub Desktop(GUI): フォルダを Add → Publish repository。コマンド不要。")
    d.bullet("GitHub CLI: gh auth login → gh repo create ncec-rom-tool --public --source . --push")

    # 5. 文面テンプレ
    d._start_page()
    d.h1("5. そのまま使える文面")
    d.h2("リポジトリ説明(About / Description)")
    d.para("短い英語(推奨):", color=d.sub)
    d.code("Open-source ROM read/edit/compare/live tool for the Mazda MX-5 NC\n"
           "(NC1, LF-VE, Denso SH7058) factory ECU. Bench/spare ECU only. No warranty.")
    d.para("日本語:", color=d.sub)
    d.code("マツダ・ロードスターNC(NCEC/LF-VE/SH7058)純正ECUの\n"
           "オープンソースROM編集・比較・ライブ監視ツール。予備ECU用・無保証。")
    d.h2("Topics(タグ。リポジトリ右上の歯車 → Topics)")
    d.code("mazda  mx5  miata  nc  ecu  tuning  reverse-engineering  sh7058  obd2  can-bus")
    d.h2("最初のコミットメッセージ")
    d.code("Initial public release: NCEC ROM Map Editor\n"
           "- read/edit/compare/live-monitor, JP/EN UI, PDF manual generator\n"
           "- flashing pending an SBL (not included)")
    d.h2("README")
    d.para("全文は付属の README.md を使用してください(免責・現状・導入・使い方・ライセンス・"
           "クレジット・SBL募集を記載済み)。GitHub ではトップに自動表示されます。", color=d.ink)

    # 6. 公開後
    d.h1("6. 公開後の運用")
    d.bullet("Issues / Discussions を有効化(Settings → Features)。質問・バグ・情報提供の窓口に。")
    d.bullet("README か Discussions に『NC1 のフラッシュ candump 提供募集(SBL抽出用)』を掲示。")
    d.bullet("リリース: Releases → Draft a new release でバージョンタグ(例 v0.1.0)を付けると親切。")
    d.bullet("安全上の免責は README 冒頭に明記済み。改変は自己責任・予備ECU推奨を一貫して。")

    # 7. チェックリスト
    d.h1("7. 公開前 最終チェックリスト")
    for s in ["□ .gitignore がある(ROM/Renesas PDF/ログ/zip を除外)",
              "□ git status に *.bin・Renesas マニュアル・nc-flash zip が出ていない",
              "□ README.md / LICENSE(GPLv3)/ requirements.txt がある",
              "□ defs の著作権方針を決めた(同梱+クレジット or 非同梱+手順)",
              "□ クレジット(LibreTuner/RomDrop/nc-flash/Renesas)を記載",
              "□ 免責・安全注意を記載",
              "□ 個人情報(メール等)やキャプチャログを含めていない"]:
        d.para(s, size=10.5, color=d.ink, gap=3)

    OUT.parent.mkdir(parents=True, exist_ok=True)
    d.save(OUT)
    print("saved:", OUT, f"({OUT.stat().st_size} bytes, {d.doc.page_count} pages)")


if __name__ == "__main__":
    build()
