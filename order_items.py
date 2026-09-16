import logging
from infrastructure import (
    AppConfig,
    get_order_data,
    group_orders_by_url,
    NoOrderDataException,
    OrderAutomation,
    ChatworkClient,
    record_purchase_management,
)
from infrastructure.repositories import BaseSheetsRepository, SheetsSalesSheetRepository


logger = logging.getLogger(__name__)


def _report_spec_questions(automation: OrderAutomation) -> None:
    if not automation.pending_spec_questions:
        return
    logger.error("=" * 60)
    logger.error("規格を特定できず、発注を中断しました。どれを買うか教えてください。")
    for question in automation.pending_spec_questions:
        logger.error("  ASIN: %s", question.asin)
        logger.error("  仕入情報シートの指定: %r", question.desired)
        logger.error("  1688側の候補 %s件:", len(question.candidates))
        for candidate in question.candidates:
            logger.error("    - %s", candidate)
    logger.error("=" * 60)


def order_items():
    config = AppConfig.from_dotenv()
    automation = OrderAutomation.from_env(headless=config.headless)
    chatwork_client = ChatworkClient.from_env()
    assert config.validate(), "設定が不正です（.env/環境変数と認証情報ファイルを確認してください）"

    try:
        order_list = get_order_data(config.credentials_file, config.sales_url, config.purchase_url)
        order_groups = group_orders_by_url(order_list, max_items_per_group=5)

        # グループが成立するたびに記録し、発注数も消す。
        # 全部終わってからまとめて行うと、途中で落ちたときに成立済みの注文が
        # 仕入管理シートに一切残らず、発注数も残るので二重発注の危険がある（2026-09-16）
        def _record_one(result) -> None:
            if not result.order_number:
                return
            record_purchase_management(
                config.credentials_file,
                config.purchase_management_sheet_url,
                [result],
                config.purchase_management_sheet_name,
            )
            asins = sorted({
                str(order.asin).strip()
                for order in result.order_group
                if getattr(order, "asin", "")
            })
            if asins:
                base = BaseSheetsRepository(config.credentials_file)
                sales_repo = SheetsSalesSheetRepository(config.credentials_file, client=base.client)
                sales_repo.clear_order_quantities(config.sales_url, asins)

        results = automation.process_orders(order_groups, on_group_done=_record_one)

        chatwork_client.send_notifications_for_order_groups(order_groups)

        _report_spec_questions(automation)

    except NoOrderDataException:
        return
    except Exception as e:
        logger.exception("エラーが発生しました: %s", e)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    order_items()
