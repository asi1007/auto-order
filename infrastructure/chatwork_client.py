"""
Chatwork APIクライアント
"""

import requests
from typing import Optional
from typing import TYPE_CHECKING
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
    
    def post_message(self, room_id: str, message: str, file_id: Optional[int] = None) -> bool:
        if not self.api_token:
            logger.warning("Chatwork APIトークンが設定されていません")
            return False
        
        url = f"{self.base_url}/rooms/{room_id}/messages"
        headers = {
            "X-ChatWorkToken": self.api_token
        }
        data = {
            "body": message
        }
        if file_id:
            data["file"] = file_id
        
        try:
            response = requests.post(url, headers=headers, data=data, timeout=10)
            response.raise_for_status()
            logger.info(f"✓ Chatworkにメッセージを投稿しました (room_id: {room_id})")
            return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Chatworkへの投稿に失敗しました: {e}")
            return False
    
    def upload_file(self, room_id: str, file_path: str) -> Optional[int]:
        if not self.api_token:
            logger.warning("Chatwork APIトークンが設定されていません")
            return None
        
        url = f"{self.base_url}/rooms/{room_id}/files"
        headers = {
            "X-ChatWorkToken": self.api_token
        }
        
        try:
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f)
                }
                response = requests.post(url, headers=headers, files=files, timeout=30)
                response.raise_for_status()
                file_id = response.json().get('file_id')
                logger.info(f"✓ Chatworkにファイルをアップロードしました (file_id: {file_id})")
                return file_id
        except Exception as e:
            logger.error(f"Chatworkへのファイルアップロードに失敗しました: {e}")
            return None
    
    def send_order_notification(self, room_id: str, chatwork_message: str, chatwork_attachment: str, asin: str = "") -> bool:
        if not chatwork_message and not chatwork_attachment:
            return False
        
        message = chatwork_message if chatwork_message else "[info]発注情報[/info]"
        
        file_id = None
        if chatwork_attachment:
            if os.path.exists(chatwork_attachment):
                file_id = self.upload_file(room_id, chatwork_attachment)
            elif chatwork_attachment.startswith('http'):
                message += f"\n\n添付: {chatwork_attachment}"
        
        if message:
            success = self.post_message(room_id, message, file_id)
            if success and asin:
                logger.info(f"✓ Chatworkに通知を送信しました (ASIN: {asin})")
            return success
        
        return False

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



