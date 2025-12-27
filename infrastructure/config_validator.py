"""
設定検証モジュール
"""

import os
import logging
from typing import List, Optional


logger = logging.getLogger(__name__)


def validate_config(credentials_file: str, 
                    yiwupassport_email: str, 
                    yiwupassport_password: str,
                    sheet_urls: Optional[List[str]] = None,
                    sheet_url_names: Optional[List[str]] = None) -> bool:
    if not os.path.exists(credentials_file):
        logger.error("エラー: 認証情報ファイル '%s' が見つかりません", credentials_file)
        logger.error("Google Sheets APIの認証情報を設定してください")
        logger.error("詳細はREADME.mdを参照してください")
        return False
    
    if sheet_urls:
        if sheet_url_names and len(sheet_url_names) == len(sheet_urls):
            missing_urls = []
            for url, name in zip(sheet_urls, sheet_url_names):
                if not url:
                    missing_urls.append(name)
            if missing_urls:
                logger.error("エラー: 環境変数が正しく設定されていません")
                logger.error(".envファイルに%sを設定してください", "と".join(missing_urls))
                logger.error("詳細はREADME.mdを参照してください")
                return False
        else:
            missing_urls = [url for url in sheet_urls if not url]
            if missing_urls:
                logger.error("エラー: 環境変数が正しく設定されていません")
                logger.error(".envファイルにシートURLを設定してください")
                logger.error("詳細はREADME.mdを参照してください")
                return False
    
    if not yiwupassport_email or not yiwupassport_password:
        logger.error("エラー: イーウーパスポートのログイン情報が設定されていません")
        logger.error(".envファイルにYIWUPASSPORT_EMAILとYIWUPASSPORT_PASSWORDを設定してください")
        logger.error("詳細はREADME.mdを参照してください")
        return False
    
    return True

