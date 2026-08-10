import logging
import sys

from infrastructure import (
    AppConfig,
    get_order_data,
    group_orders_by_url,
    NoOrderDataException,
    OrderAutomation,
)
from usecases import estimate_required_amount

logger = logging.getLogger(__name__)

SAFETY_MARGIN_RATE = 1.2


def check_balance() -> int:
    config = AppConfig.from_dotenv()
    assert config.validate(), "設定が不正です（.env/環境変数と認証情報ファイルを確認してください）"

    try:
        order_list = get_order_data(config.credentials_file, config.sales_url, config.purchase_url)
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)
    except NoOrderDataException:
        order_groups = []

    required = estimate_required_amount(order_groups)
    recommended = required * SAFETY_MARGIN_RATE

    automation = OrderAutomation.from_env(headless=True)
    try:
        automation.start_browser()
        if not automation.login():
            logger.error("ログインに失敗しました")
            return 1
        balance = automation.fetch_balance()
    finally:
        automation.close_browser()

    logger.info("💰 現在残高: CNY %s 元 / JPY %s 円", f"{balance.cny:,.2f}", f"{balance.jpy:,.0f}")

    for group in order_groups:
        for order in group:
            amount = order.order_quantity * (order.unit_price or 0)
            logger.info(
                "  %s  数量 %s  単価 %s  = %s 元",
                order.asin,
                f"{order.order_quantity:,}",
                order.unit_price,
                f"{amount:,.2f}",
            )

    logger.info("商品代金の合計: %s 元", f"{required:,.2f}")
    logger.info("推奨残高（送料・手数料込みの目安 %.0f%%）: %s 元", SAFETY_MARGIN_RATE * 100, f"{recommended:,.2f}")

    if not order_groups:
        logger.info("✓ 発注対象がありません")
        return 0

    if balance.covers(recommended):
        logger.info("✓ 残高は推奨額を満たしています。発注可能です")
        return 0

    if balance.covers(required):
        logger.warning(
            "△ 商品代金は足りますが推奨額に %s 元 不足しています。送料・手数料で失敗する可能性があります",
            f"{recommended - balance.cny:,.2f}",
        )
        return 0

    logger.error("✗ 残高不足です。あと %s 元 必要です", f"{balance.shortfall(required):,.2f}")
    return 1


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    sys.exit(check_balance())
