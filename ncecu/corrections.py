"""要注意テーブルの次元補正 {data_address: (rows, cols)}。

汎用定義 lfg7eg.xml が実ROMに合わないテーブルについて、ECU内部の
テーブル・ディスクリプタ([Y_ptr, X_ptr, data_ptr, 0, (rows,cols)] 形式)から
真の次元を取得し、値が目安範囲に収まること(in-range>=0.85)で検証したもののみ採用。
検証を通らなかったテーブルは補正せず、エディタ側で⚠表示のまま(信頼性低)。

このモジュールは tools/gen_corrections.py で自動生成・更新できる。
"""

# {data_address(int): (rows, cols)} — 検証済みのみ
CORRECTIONS: dict[int, tuple[int, int]] = {}

try:
    from ._corrections_data import CORRECTIONS as _C  # 自動生成データ
    CORRECTIONS = _C
except Exception:
    CORRECTIONS = {}


def corrected_dims(address: int):
    """補正があれば (rows, cols) を返す。無ければ None。"""
    return CORRECTIONS.get(address)
