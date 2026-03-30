"""
Chatwork APIクライアント
"""

import tempfile
import requests
from typing import Optional
from typing import TYPE_CHECKING
from urllib.parse import urlparse
import logging
import os

logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from domain.entities.order import Order


class ChatworkClient:
    def __init__(self, api_token: str, default_room_id: str = "397092794"):
        self.api_token = api_token
        self.base_url = "https://api.chatwork.com/v2"
        self.default_room_id = default_room_id

    @classmethod
    def from_env(cls) -> "ChatworkClient":
        api_token = os.getenv("CHATWORK_API_TOKEN", "")
        room_id = os.getenv("CHATWORK_ROOM_ID", "397092794")
        return cls(api_token=api_token, default_room_id=room_id)

    def post_message(self, room_id: str, message: str) -> bool:
        if not self.api_token:
            logger.warning("Chatwork APIトークンが設定されていません")
            return False

        url = f"{self.base_url}/rooms/{room_id}/messages"
        headers = {"X-ChatWorkToken": self.api_token}
        data = {"body": message}

        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            logger.info(f"✓ Chatworkにメッセージを投稿しました (room_id: {room_id})")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Chatworkへの投稿に失敗しました: {e}")
            return False

    def upload_file_with_message(self, room_id: str, file_path: str, message: str = "") -> bool:
        if not self.api_token:
            logger.warning("Chatwork APIトークンが設定されていません")
            return False

        url = f"{self.base_url}/rooms/{room_id}/files"
        headers = {"X-ChatWorkToken": self.api_token}

        try:
            with open(file_path, 'rb') as f:
                files = {'file': (os.path.basename(file_path), f)}
                data = {"message": message} if message else {}
                response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
                response.raise_for_status()
                file_id = response.json().get('file_id')
                logger.info(f"✓ Chatworkにファイルをアップロードしました (file_id: {file_id})")
                return True
        except Exception as e:
            logger.error(f"Chatworkへのファイルアップロードに失敗しました: {e}")
            return False

    @staticmethod
    def _to_direct_download_url(url: str) -> str:
        import re
        match = re.search(r"drive\.google\.com/file/d/([^/]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        match = re.search(r"drive\.google\.com/open\?id=([^&]+)", url)
        if match:
            file_id = match.group(1)
            return f"https://drive.google.com/uc?export=download&id={file_id}"
        return url

    def _download_to_temp(self, url: str) -> Optional[str]:
        try:
            download_url = self._to_direct_download_url(url)
            response = requests.get(download_url, timeout=30)
            response.raise_for_status()
            content_type = response.headers.get("Content-Type", "")
            if "text/html" in content_type:
                logger.error(f"画像ではなくHTMLが返されました（共有設定を確認してください）: {url}")
                return None
            ext_map = {"image/png": ".png", "image/jpeg": ".jpg", "image/webp": ".webp"}
            ext = ext_map.get(content_type.split(";")[0], "")
            if not ext:
                parsed = urlparse(url)
                ext = os.path.splitext(parsed.path)[1] or ".png"
            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=ext)
            tmp.write(response.content)
            tmp.close()
            logger.info(f"✓ 画像をダウンロードしました: {url}")
            return tmp.name
        except Exception as e:
            logger.error(f"画像のダウンロードに失敗しました: {url} - {e}")
            return None

    def send_order_notification(self, room_id: str, chatwork_message: str, chatwork_attachment: str, asin: str = "") -> bool:
        if not chatwork_message and not chatwork_attachment:
            return False

        message = chatwork_message if chatwork_message else "[info]発注情報[/info]"

        file_path: Optional[str] = None
        temp_file: Optional[str] = None
        if chatwork_attachment:
            if os.path.exists(chatwork_attachment):
                file_path = chatwork_attachment
            elif chatwork_attachment.startswith('http'):
                temp_file = self._download_to_temp(chatwork_attachment)
                file_path = temp_file

        try:
            if file_path:
                success = self.upload_file_with_message(room_id, file_path, message)
            else:
                success = self.post_message(room_id, message)
            if success and asin:
                logger.info(f"✓ Chatworkに通知を送信しました (ASIN: {asin})")
            return success
        finally:
            if temp_file and os.path.exists(temp_file):
                os.unlink(temp_file)

    def send_notifications_for_order_groups(self, order_groups: list[list["Order"]]) -> None:
        for group in order_groups:
            for order in group:
                chatwork_message = str(order.chatwork_message).strip()
                chatwork_attachment = str(order.chatwork_attachment).strip()
                asin = str(order.asin).strip()

                # chatwork文章とchatwork添付がある場合のみ通知
                if not chatwork_message and not chatwork_attachment:
                    continue

                self.send_order_notification(
                    self.default_room_id,
                    chatwork_message,
                    chatwork_attachment,
                    asin,
                )



