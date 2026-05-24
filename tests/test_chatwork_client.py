from __future__ import annotations

import os
import tempfile
from unittest.mock import MagicMock, patch

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

    def test_send_order_notification_text_only(self):
        client = ChatworkClient(api_token="token", default_room_id="123")
        client.post_message = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = client.send_order_notification("123", "hello", "", "A1")

        assert result is True
        client.post_message.assert_called_once_with("123", "hello")

    def test_send_order_notification_with_local_file(self):
        client = ChatworkClient(api_token="token", default_room_id="123")
        client.upload_file_with_message = MagicMock(return_value=True)  # type: ignore[method-assign]

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake image")
            tmp_path = f.name

        try:
            result = client.send_order_notification("123", "msg", tmp_path, "A1")
            assert result is True
            client.upload_file_with_message.assert_called_once_with("123", tmp_path, "msg")
        finally:
            os.unlink(tmp_path)

    @patch("infrastructure.chatwork_client.ChatworkClient._download_to_temp")
    def test_send_order_notification_with_http_url(self, mock_download: MagicMock):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake image")
            tmp_path = f.name

        mock_download.return_value = tmp_path
        client = ChatworkClient(api_token="token", default_room_id="123")
        client.upload_file_with_message = MagicMock(return_value=True)  # type: ignore[method-assign]

        result = client.send_order_notification("123", "msg", "http://example.com/img.png", "A1")

        assert result is True
        mock_download.assert_called_once_with("http://example.com/img.png")
        client.upload_file_with_message.assert_called_once_with("123", tmp_path, "msg")
        assert not os.path.exists(tmp_path)

    def test_send_order_notification_empty_returns_false(self):
        client = ChatworkClient(api_token="token", default_room_id="123")
        assert client.send_order_notification("123", "", "", "") is False

    def test_extract_drive_file_id_from_file_url(self):
        url = "https://drive.google.com/file/d/1aBcDeFgHiJkLmN/view?usp=sharing"
        assert ChatworkClient._extract_drive_file_id(url) == "1aBcDeFgHiJkLmN"

    def test_extract_drive_file_id_from_open_url(self):
        url = "https://drive.google.com/open?id=1aBcDeFgHiJkLmN&usp=drive_fs"
        assert ChatworkClient._extract_drive_file_id(url) == "1aBcDeFgHiJkLmN"

    def test_extract_drive_file_id_non_drive_url(self):
        url = "https://example.com/image.png"
        assert ChatworkClient._extract_drive_file_id(url) is None

    @patch("infrastructure.chatwork_client.ChatworkClient._download_from_google_drive")
    def test_download_to_temp_uses_drive_api_for_drive_urls(self, mock_drive: MagicMock):
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"fake")
            tmp_path = f.name
        mock_drive.return_value = tmp_path

        client = ChatworkClient(api_token="t", google_credentials_file="creds.json")
        result = client._download_to_temp("https://drive.google.com/open?id=ABC123")

        mock_drive.assert_called_once_with("ABC123")
        assert result == tmp_path
        os.unlink(tmp_path)


