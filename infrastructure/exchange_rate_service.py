from __future__ import annotations

import logging
from functools import lru_cache
from typing import Final

import requests


logger = logging.getLogger(__name__)

EXCHANGE_RATE_API_URL: Final[str] = "https://api.exchangerate-api.com/v4/latest/CNY"
DEFAULT_CNY_TO_JPY_RATE: Final[float] = 21.0


@lru_cache(maxsize=1)
def _fetch_cny_to_jpy_rate() -> float:
    try:
        response = requests.get(EXCHANGE_RATE_API_URL, timeout=10)
        response.raise_for_status()
        data = response.json()
        rate = data.get("rates", {}).get("JPY")
        if rate is None:
            logger.warning("APIレスポンスにJPYレートが含まれていません。デフォルト値を使用します。")
            return DEFAULT_CNY_TO_JPY_RATE
        logger.info("為替レート取得成功: 1 CNY = %.2f JPY", rate)
        return float(rate)
    except requests.RequestException as e:
        logger.warning("為替レート取得に失敗しました: %s。デフォルト値を使用します。", e)
        return DEFAULT_CNY_TO_JPY_RATE


def get_cny_to_jpy_rate() -> float:
    return _fetch_cny_to_jpy_rate()


def convert_cny_to_jpy(cny_amount: float) -> float:
    rate = get_cny_to_jpy_rate()
    return cny_amount * rate


def clear_rate_cache() -> None:
    _fetch_cny_to_jpy_rate.cache_clear()
