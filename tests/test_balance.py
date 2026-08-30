from unittest.mock import MagicMock

import pytest

from domain.entities.order import Order
from domain.value_objects.balance import Balance
from infrastructure.order_automation import OrderAutomation
from usecases.estimate_required_amount import estimate_required_amount


class TestBalance:

    def test_shortfall_returns_zero_when_balance_covers_amount(self):
        balance = Balance(cny=34086.36, jpy=0)

        assert balance.shortfall(13380.0) == 0.0

    def test_shortfall_returns_missing_amount(self):
        balance = Balance(cny=5076.83, jpy=0)

        assert balance.shortfall(13380.0) == pytest.approx(8303.17)

    def test_covers_is_false_when_short(self):
        balance = Balance(cny=5076.83, jpy=0)

        assert balance.covers(13380.0) is False

    def test_covers_is_true_when_equal(self):
        balance = Balance(cny=13380.0, jpy=0)

        assert balance.covers(13380.0) is True

    def test_jpy_is_not_counted_as_cny(self):
        balance = Balance(cny=0.0, jpy=700000)

        assert balance.covers(13380.0) is False

    def test_from_texts_parses_comma_separated_amounts(self):
        balance = Balance.from_texts("CNY 34,086.36 元", "JPY 700,000 円")

        assert balance.cny == pytest.approx(34086.36)
        assert balance.jpy == pytest.approx(700000)

    def test_from_texts_returns_zero_for_unparsable_text(self):
        balance = Balance.from_texts("", "")

        assert balance.cny == 0.0
        assert balance.jpy == 0.0

    def test_from_texts_keeps_the_minus_sign(self):
        balance = Balance.from_texts("利用可能残高： CNY -15778.77 元", "JPY 0 円")

        assert balance.cny == pytest.approx(-15778.77)

    def test_negative_balance_never_covers_an_order(self):
        balance = Balance.from_texts("CNY -15,778.77 元", "JPY 0 円")

        assert balance.covers(1.0) is False
        assert balance.shortfall(12450.0) == pytest.approx(28228.77)


class TestEstimateRequiredAmount:

    def _order(self, quantity: int, unit_price: float) -> Order:
        return Order(
            asin="B0TEST00001",
            product_name="テスト商品",
            purchase_url="https://detail.1688.com/offer/1.html",
            order_quantity=quantity,
            unit_price=unit_price,
        )

    def test_sums_quantity_times_unit_price_across_groups(self):
        groups = [
            [self._order(25000, 0.12), self._order(40000, 0.12)],
            [self._order(2000, 0.99)],
        ]

        assert estimate_required_amount(groups) == pytest.approx(9780.0)

    def test_treats_missing_unit_price_as_zero(self):
        groups = [[self._order(100, None)]]

        assert estimate_required_amount(groups) == 0.0

    def test_returns_zero_for_no_groups(self):
        assert estimate_required_amount([]) == 0.0


class TestFetchBalance:

    @pytest.fixture
    def automation(self) -> OrderAutomation:
        automation = OrderAutomation(headless=True, email="test@example.com", password="testpass")
        automation.page = MagicMock()
        automation._goto_with_retry = MagicMock()
        return automation

    def _locator(self, text: str, count: int = 1) -> MagicMock:
        locator = MagicMock()
        locator.count.return_value = count
        locator.first.text_content.return_value = text
        return locator

    def test_fetch_balance_parses_both_currencies(self, automation, monkeypatch):
        monkeypatch.setattr("infrastructure.order_automation.time.sleep", lambda _: None)
        automation.page.locator.side_effect = [
            self._locator("CNY 34,086.36 元"),
            self._locator("JPY 700,000 円"),
        ]

        balance = automation.fetch_balance()

        assert balance == Balance(cny=34086.36, jpy=700000.0)

    def test_fetch_balance_returns_zero_when_element_missing(self, automation, monkeypatch):
        monkeypatch.setattr("infrastructure.order_automation.time.sleep", lambda _: None)
        automation.page.locator.side_effect = [
            self._locator("", count=0),
            self._locator("", count=0),
        ]

        assert automation.fetch_balance() == Balance(cny=0.0, jpy=0.0)
