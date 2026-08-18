import argparse
import logging
import os
from datetime import datetime

from dotenv import load_dotenv

from domain.value_objects.ingest_plan import IngestPlan
from infrastructure.chatwork_client import ChatworkClient
from infrastructure.processed_message_store import ProcessedMessageStore
from infrastructure.repositories.packing_materials_sheet_repository import (
    SheetsPackingMaterialsSheetRepository,
)
from infrastructure.repositories.purchase_history_sheet_repository import (
    SheetsPurchaseHistoryRepository,
)
from usecases.ingest_material_requests import IngestMaterialRequests

logger = logging.getLogger(__name__)

_STATE_FILE = ".material_request_state.json"


def build_usecase(order_quantity_overrides: dict[str, int]) -> IngestMaterialRequests:
    load_dotenv()
    credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "service_account.json")
    packing_sheet_url = os.getenv("PACKING_MATERIALS_SHEET_URL", "")
    packing_sheet_name = os.getenv("PACKING_MATERIALS_SHEET_NAME") or "使用資材"
    history_sheet_url = os.getenv("PURCHASE_HISTORY_SHEET_URL", packing_sheet_url)
    history_sheet_name = os.getenv("PURCHASE_HISTORY_SHEET_NAME") or packing_sheet_name
    room_id = os.getenv("CHATWORK_ROOM_ID", "397092794")

    return IngestMaterialRequests(
        chatwork_client=ChatworkClient.from_env(),
        packing_repository=SheetsPackingMaterialsSheetRepository(credentials_file),
        history_repository=SheetsPurchaseHistoryRepository(
            credentials_file, history_sheet_url, history_sheet_name
        ),
        store=ProcessedMessageStore(_STATE_FILE),
        room_id=room_id,
        packing_sheet_url=packing_sheet_url,
        packing_sheet_name=packing_sheet_name,
        order_quantity_overrides=order_quantity_overrides,
    )


def print_plan(plan: IngestPlan) -> None:
    if not plan.orders and not plan.pendings:
        print("取り込む発注依頼はありません")
        return

    if plan.orders:
        print(f"\n[発注数を書き込む資材] {len(plan.orders)}件")
        print(f"  {'資材名称':<20}{'発注数':>8}{'個数':>10}  {'行':>4}  依頼")
        for order in plan.orders:
            print(
                f"  {order.material.name:<20}{order.quantity:>8}{order.piece_count:>10}  "
                f"{order.material.row_number:>4}  {order.size_token.text}"
            )

    if plan.pendings:
        print(f"\n[保留・要確認] {len(plan.pendings)}件")
        for pending in plan.pendings:
            size = pending.size_token.text if pending.size_token else "—"
            candidates = "/".join(row.name for row in pending.candidates) or "—"
            print(f"  {pending.reason:<10} サイズ={size:<14} 候補={candidates}")
            print(f"    依頼: {' '.join(pending.request.body.split())[:100]}")


def _parse_overrides(assignments: list[str]) -> dict[str, int]:
    overrides: dict[str, int] = {}
    for assignment in assignments:
        name, _, quantity = assignment.partition("=")
        if not name.strip() or not quantity.strip().isdigit():
            raise SystemExit(f"--set の書式が正しくありません: {assignment}")
        overrides[name.strip()] = int(quantity)
    return overrides


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--apply", action="store_true", help="シートの発注数へ実際に書き込む")
    parser.add_argument(
        "--seed",
        action="store_true",
        help="書き込まずに検出済みの依頼を全て処理済みにする（導入時に過去分を消化するため）",
    )
    parser.add_argument(
        "--seed-before",
        metavar="YYYY-MM-DD",
        help="その日より前に届いた依頼だけを処理済みにする（対応済みの分だけ消化したいとき）",
    )
    parser.add_argument(
        "--set",
        action="append",
        default=[],
        metavar="資材名称=発注数",
        help="発注実績が無い資材の発注数（ロット数）を指定する。複数指定可",
    )
    args = parser.parse_args()

    usecase = build_usecase(_parse_overrides(args.set))
    plan = usecase.build_plan()
    print_plan(plan)

    if args.seed_before:
        cutoff = int(datetime.strptime(args.seed_before, "%Y-%m-%d").timestamp())
        seeded = usecase.mark_as_processed_before(plan, cutoff_epoch=cutoff)
        print(f"\n{args.seed_before} より前の依頼を処理済みにしました: {seeded}件（書き込みはしていません）")
        return

    if args.seed:
        seeded = usecase.mark_all_as_processed(plan)
        print(f"\n過去分として処理済みにしました: {seeded}件（書き込みはしていません）")
        return

    if not args.apply:
        print("\n(--dry-run 相当。書き込むには --apply を付けて実行する)")
        return

    written = usecase.apply(plan)
    print(f"\n発注数を書き込みました: {written}件")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    main()
