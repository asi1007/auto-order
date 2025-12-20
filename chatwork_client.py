"""
Chatwork APIクライアント
"""

import requests
from typing import Optional
import logging
import os

logger = logging.getLogger(__name__)


class ChatworkClient:
    def __init__(self, api_token: str):
        self.api_token = api_token
        self.base_url = "https://api.chatwork.com/v2"
    
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



