import pytest

from infrastructure.app_config import AppConfig


class TestAppConfig:
    def test_from_env_reads_values(self, monkeypatch, tmp_path):
        creds = tmp_path / "creds.json"
        creds.write_text("{}", encoding="utf-8")

        monkeypatch.setenv("GOOGLE_CREDENTIALS_FILE", str(creds))
        monkeypatch.setenv("SALES_SHEET_URL", "https://example.com/sales")
        monkeypatch.setenv("PURCHASE_SHEET_URL", "https://example.com/purchase")
        monkeypatch.setenv("PURCHASE_HISTORY_SHEET_URL", "https://example.com/history")
        monkeypatch.setenv("PURCHASE_MANAGEMENT_SHEET_URL", "https://example.com/management?gid=1#gid=1")
        monkeypatch.setenv("PURCHASE_MANAGEMENT_SHEET_NAME", "仕入管理")
        monkeypatch.setenv("PURCHASE_HISTORY_SHEET_NAME", "履歴")
        monkeypatch.setenv("HEADLESS", "true")

        config = AppConfig.from_env()

        assert config.credentials_file == str(creds)
        assert config.sales_url == "https://example.com/sales"
        assert config.purchase_url == "https://example.com/purchase"
        assert config.purchase_history_url == "https://example.com/history"
        assert config.purchase_history_sheet_name == "履歴"
        assert config.purchase_management_sheet_url == "https://example.com/management?gid=1#gid=1"
        assert config.purchase_management_sheet_name == "仕入管理"
        assert config.headless is True

    def test_from_dotenv_reads_values(self, tmp_path, monkeypatch):
        creds = tmp_path / "creds.json"
        creds.write_text("{}", encoding="utf-8")

        dotenv_path = tmp_path / ".env"
        dotenv_path.write_text(
            "\n".join(
                [
                    f"GOOGLE_CREDENTIALS_FILE={creds}",
                    "SALES_SHEET_URL=https://example.com/sales",
                    "PURCHASE_SHEET_URL=https://example.com/purchase",
                    "PURCHASE_HISTORY_SHEET_URL=https://example.com/history",
                    "PURCHASE_HISTORY_SHEET_NAME=履歴",
                    "HEADLESS=true",
                ]
            ),
            encoding="utf-8",
        )

        # 既存の環境変数があってもdotenvの値を優先して読み込めること
        monkeypatch.setenv("SALES_SHEET_URL", "https://override-me.invalid")

        config = AppConfig.from_dotenv(dotenv_path=str(dotenv_path), override=True)

        assert config.credentials_file == str(creds)
        assert config.sales_url == "https://example.com/sales"
        assert config.purchase_url == "https://example.com/purchase"
        assert config.purchase_history_url == "https://example.com/history"
        assert config.purchase_history_sheet_name == "履歴"
        assert config.headless is True

    def test_validate_returns_true_when_all_required_values_present(self, monkeypatch, tmp_path):
        creds = tmp_path / "creds.json"
        creds.write_text("{}", encoding="utf-8")

        monkeypatch.setenv("GOOGLE_CREDENTIALS_FILE", str(creds))
        monkeypatch.setenv("SALES_SHEET_URL", "https://example.com/sales")
        monkeypatch.setenv("PURCHASE_SHEET_URL", "https://example.com/purchase")
        monkeypatch.setenv("PURCHASE_HISTORY_SHEET_URL", "https://example.com/history")
        monkeypatch.setenv("PURCHASE_MANAGEMENT_SHEET_URL", "https://example.com/management?gid=1#gid=1")

        config = AppConfig.from_env()
        assert config.validate() is True

    @pytest.mark.parametrize(
        "missing_key",
        ["SALES_SHEET_URL", "PURCHASE_SHEET_URL", "PURCHASE_HISTORY_SHEET_URL", "PURCHASE_MANAGEMENT_SHEET_URL"],
    )
    def test_validate_returns_false_when_sheet_url_missing(self, monkeypatch, tmp_path, missing_key):
        creds = tmp_path / "creds.json"
        creds.write_text("{}", encoding="utf-8")

        monkeypatch.setenv("GOOGLE_CREDENTIALS_FILE", str(creds))
        monkeypatch.setenv("SALES_SHEET_URL", "https://example.com/sales")
        monkeypatch.setenv("PURCHASE_SHEET_URL", "https://example.com/purchase")
        monkeypatch.setenv("PURCHASE_HISTORY_SHEET_URL", "https://example.com/history")
        monkeypatch.setenv("PURCHASE_MANAGEMENT_SHEET_URL", "https://example.com/management?gid=1#gid=1")

        monkeypatch.setenv(missing_key, "")

        config = AppConfig.from_env()
        assert config.validate() is False


