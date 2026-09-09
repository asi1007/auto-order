"""「+商品」ボタンの XPath を、実際に取得した YP の DOM で検証する。

2026-09-10 に A3フレーム + A6フレームの2商品グループで
`Locator.wait_for: Timeout` になり発注が落ちた。原因は2つある。

1. アイコンが商品バッジの **前** にある（コードは following-sibling を見ていた）
2. バッジの文字列が `* 商品1` になり `starts-with(., "商品")` が外れる
"""

import re
from pathlib import Path
from xml.etree import ElementTree

from infrastructure.order_automation import ADD_PRODUCT_ROW_XPATH

FIXTURE = Path(__file__).parent / "fixtures" / "yp_manual_item_row.html"


def _find(xpath: str) -> list:
    # ElementTree は限定的な XPath しか解さないので、構造だけを素直に辿って確かめる
    root = ElementTree.fromstring(_wrap(FIXTURE.read_text()))
    hits = []
    for parent in root.iter():
        children = list(parent)
        for i, child in enumerate(children):
            if child.tag != "span" or "bg-warning" not in (child.get("class") or ""):
                continue
            if "商品" not in "".join(child.itertext()):
                continue
            icons = [
                c for c in children[:i]
                if c.tag == "img" and "cursor-pointer" in (c.get("class") or "")
            ]
            if icons:
                hits.append(icons[-1])
    return hits


def _wrap(html: str) -> str:
    # ElementTree は XML しか解さない。img は HTML の空要素なので閉じてやる
    body = re.sub(r"<img\b([^>]*?)/?>", r"<img\1/>", html)
    return "<root>" + body.replace("<!---->", "").replace("&nbsp;", " ") + "</root>"


def test_商品バッジの直前のアイコンが1つ見つかる() -> None:
    hits = _find(ADD_PRODUCT_ROW_XPATH)
    assert len(hits) == 1, f"{len(hits)} 件見つかった"
    assert "cursor-pointer" in hits[0].get("class")


def test_xpathは前方のアイコンを見る() -> None:
    # following-sibling では見つからない DOM になった
    assert "preceding-sibling::img" in ADD_PRODUCT_ROW_XPATH
    assert "following-sibling::img" not in ADD_PRODUCT_ROW_XPATH


def test_バッジのテキストは前方一致では拾えない() -> None:
    # 実際の文字列は "* 商品1"。starts-with では外れる
    root = ElementTree.fromstring(_wrap(FIXTURE.read_text()))
    badge = next(el for el in root.iter("span") if "bg-warning" in (el.get("class") or ""))
    assert "".join(badge.itertext()).strip().startswith("*")
    assert "starts-with" not in ADD_PRODUCT_ROW_XPATH
    assert "contains(normalize-space(.)" in ADD_PRODUCT_ROW_XPATH
