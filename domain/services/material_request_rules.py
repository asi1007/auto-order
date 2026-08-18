from __future__ import annotations

from typing import Callable

# ここの語彙は運用しながら育てる。判定を変えたいときはこのファイルだけ触る。

SHORTAGE_KEYWORDS: tuple[str, ...] = (
    "在庫不足",
    "在庫なく",
    "在庫がなく",
    "足りな",
    "足らな",
    "不足",
)

REQUEST_KEYWORDS: tuple[str, ...] = (
    "再注文",
    "再発注",
    "注文して",
    "発注して",
    "購入して",
)

CATEGORY_MESSAGE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "OPP": ("opp",),
    "プチプチ": ("プチプチ", "ぷちぷち", "気泡", "エアキャップ"),
    "ダンボール": ("ケース", "ダンボール", "段ボール", "箱", "ボックス"),
    "袋": ("袋", "ぶくろ"),
}

CATEGORY_MATERIAL_PREDICATES: dict[str, Callable[[str], bool]] = {
    "OPP": lambda name: "OPP" in name,
    "プチプチ": lambda name: "プチプチ" in name,
    "ダンボール": lambda name: "ダンボール" in name or "段ボール" in name,
    "袋": lambda name: "袋" in name or "OPP" in name or "プチプチ" in name,
}
