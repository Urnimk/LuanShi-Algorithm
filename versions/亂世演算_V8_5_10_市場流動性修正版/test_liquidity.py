"""回流、低價撮合及真實存檔的監測回歸。"""
import importlib
import json
from pathlib import Path

from fiscal_policy import treasury_circulation


m = importlib.import_module('亂世演算_V8_5_10_市場流動性修正版')


def test_adaptive_recycling_and_conservation():
    countries = {f'C{i:02}': {'is_alive': True, 'gold': 0, 'pop_total': 100}
                 for i in range(100)}
    bank = m._default_world_bank()
    bank.update(issued_total=40000, treasury=40000)
    paid = treasury_circulation(bank, countries, 10)
    assert 400 < sum(amount for _, amount in paid) <= 1000
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0
    assert treasury_circulation(bank, countries, 10) == []


def test_tiny_trade_preserves_seller_payment_and_bank_audit():
    assert m._market_transaction_fee(1) == 0
    assert m._market_transaction_fee(99) == 0
    assert m._market_transaction_fee(100) == 1
    bank = m._default_world_bank()
    bank.update(issued_total=10, treasury=0)
    countries = {
        'buyer': {'is_alive': True, 'gold': 10, 'food': 0},
        'seller': {'is_alive': True, 'gold': 0, 'food': 10},
    }
    market = m._default_world_market()
    market['orders'] = [
        {'id': 'M1', 'turn': 1, 'country': 'buyer', 'side': 'BUY', 'resource': 'food', 'qty': 1, 'price': .05},
        {'id': 'M2', 'turn': 1, 'country': 'seller', 'side': 'SELL', 'resource': 'food', 'qty': 1, 'price': .05},
    ]
    trades = m._market_match_orders(countries, market, bank, 1)
    assert len(trades) == 1 and trades[0]['gross_gold'] == 1
    assert trades[0]['fee_gold'] == 0 and countries['seller']['gold'] == 1
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_uploaded_snapshot_identifies_floor_cash_pressure():
    path = Path(__file__).parent.parent / 'upload' / 'war_live_countries(2).json'
    if not path.exists():
        return  # 套件發給使用者後無需附測試用的私人存檔。
    snapshot = json.loads(path.read_text(encoding='utf-8'))
    bank = snapshot['world_bank']
    assert m._currency_audit(snapshot['countries'], bank, raise_on_error=True)['gap'] == 0
    market = snapshot['world_market']
    stressed = market['price_monitor']['latest']['cash_stressed']
    pressure, resources = m._market_floor_cash_pressure(market, stressed)
    assert pressure and 'food' in resources


def test_monitor_flags_stuck_price_without_triggering_new_issuance():
    market = m._default_world_market()
    bank = m._default_world_bank()
    bank.update(issued_total=1000, treasury=1000)
    countries = {'C': {'is_alive': True, 'gold': 0, 'pop_total': 100,
                       'food': 800, 'wood': 250, 'metal': 100,
                       'farmers': 70, 'soldiers': 30}}
    for resource in m.MARKET_RESOURCES:
        market['stats'][resource]['traded_volume'] = 1000
        market['stats'][resource]['traded_value'] = 1000
    market['stats']['food'].update(last_price=.05, buy_qty=100, sell_qty=700)
    latest = m._market_health_update(market, bank, countries, 10)
    assert latest['reliable'] and latest['floor_cash_stress']
    assert latest['diagnosis'] == '價格貼底、賣盤偏重及廣泛現金不足'
    assert not latest['liquidity_stress']
    assert m._world_bank_recirculate_liquidity(bank, countries, 10, market) == []
    assert bank['issued_total'] == 1000
