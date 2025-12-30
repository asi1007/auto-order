from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv

from infrastructure.config_validator import validate_config


@dataclass(frozen=True)
class AppConfig:
    credentials_file: str
    sales_url: str
    purchase_url: str
    purchase_history_url: str
    purchase_history_sheet_name: str | None
    purchase_management_sheet_url: str
    purchase_management_sheet_name: str
    headless: bool

    @classmethod
    def from_env(cls) -> "AppConfig":
        credentials_file = os.getenv("GOOGLE_CREDENTIALS_FILE", "credentials.json")
        sales_url = os.getenv("SALES_SHEET_URL", "")
        purchase_url = os.getenv("PURCHASE_SHEET_URL", "")
        purchase_history_url = os.getenv("PURCHASE_HISTORY_SHEET_URL", "")
        purchase_history_sheet_name = os.getenv("PURCHASE_HISTORY_SHEET_NAME") or None
        purchase_management_sheet_url = os.getenv(
            "PURCHASE_MANAGEMENT_SHEET_URL",
            "https://docs.google.com/spreadsheets/d/1Dvz3cS9DRGx4woEY0NNypgLPKxLZ55a4j8778YlCFls/edit?gid=1452652687#gid=1452652687",
        )
        purchase_management_sheet_name = os.getenv("PURCHASE_MANAGEMENT_SHEET_NAME", "仕入管理")
        headless = os.getenv("HEADLESS", "False").lower() == "true"

        return cls(
            credentials_file=credentials_file,
            sales_url=sales_url,
            purchase_url=purchase_url,
            purchase_history_url=purchase_history_url,
            purchase_history_sheet_name=purchase_history_sheet_name,
            purchase_management_sheet_url=purchase_management_sheet_url,
            purchase_management_sheet_name=purchase_management_sheet_name,
            headless=headless,
        )

    @classmethod
    def from_dotenv(
        cls,
        *,
        dotenv_path: str | None = None,
        override: bool = False,
    ) -> "AppConfig":
        load_dotenv(dotenv_path=dotenv_path, override=override)
        return cls.from_env()

    def validate(self) -> bool:
        return validate_config(
            self.credentials_file,
            sheet_urls=[self.sales_url, self.purchase_url, self.purchase_history_url, self.purchase_management_sheet_url],
            sheet_url_names=["SALES_SHEET_URL", "PURCHASE_SHEET_URL", "PURCHASE_HISTORY_SHEET_URL", "PURCHASE_MANAGEMENT_SHEET_URL"],
        )


