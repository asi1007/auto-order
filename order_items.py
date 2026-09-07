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
        results = automation.process_orders(order_groups)

        record_purchase_management(
            config.credentials_file,
            config.purchase_management_sheet_url,
            results,
            config.purchase_management_sheet_name,
        )

        completed_asins: set[str] = set()
        for result in results:
            if not result.order_number:
                continue
            for order in result.order_group:
                if getattr(order, "asin", ""):
                    completed_asins.add(str(order.asin).strip())
        if completed_asins:
            base = BaseSheetsRepository(config.credentials_file)
            sales_repo = SheetsSalesSheetRepository(config.credentials_file, client=base.client)
            sales_repo.clear_order_quantities(config.sales_url, sorted(completed_asins))

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
