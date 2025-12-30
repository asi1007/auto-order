from __future__ import annotations

from unittest.mock import MagicMock

from domain.entities.order import Order
from infrastructure.chatwork_client import ChatworkClient


class TestChatworkClient:
    def test_send_notifications_for_order_groups_filters_and_calls_send_order_notification(self):
        client = ChatworkClient(api_token="token", default_room_id="123")
        client.send_order_notification = MagicMock(return_value=True)  # type: ignore[method-assign]

        order_groups = [
            [
                Order(asin="A1", product_name="p1", purchase_url="u", order_quantity=1, chatwork_message="  hello  ", chatwork_attachment=""),
                Order(asin="A2", product_name="p2", purchase_url="u", order_quantity=1, chatwork_message="", chatwork_attachment="   "),  # skip
                Order(asin="A3", product_name="p3", purchase_url="u", order_quantity=1, chatwork_message="", chatwork_attachment="http://example.com/a.png"),
            ]
        ]

        client.send_notifications_for_order_groups(order_groups)

        assert client.send_order_notification.call_count == 2
        client.send_order_notification.assert_any_call("123", "hello", "", "A1")
        client.send_order_notification.assert_any_call("123", "", "http://example.com/a.png", "A3")


