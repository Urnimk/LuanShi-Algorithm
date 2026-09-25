"""銀行停止護盤、低價換幣與一比十重定面額回歸測試。"""
import importlib

m = importlib.import_module('亂世演算_V8_5_1_國家經驗查詢版')
p = importlib.import_module('policy_index')


def fixture():
    countries = {'甲': {'gold': 40_000_000, 'is_alive': True}, '乙': {'gold': 0, 'is_alive': True}}
    bank = m._default_world_bank()
    bank['issued_total'] = 40_000_000
    p.initialize(bank, countries)
    market = m._default_world_market()
    return countries, bank, market


def test_low_price_does_not_trigger_bank_buying_or_minting():
    countries, bank, market = fixture()
    market['stats']['food']['last_price'] = 60
    market['orders'].append({'id': 'M1', 'country': '甲', 'resource': 'food',
                             'side': 'SELL', 'qty': 100, 'price': 60, 'turn': 1})
    countries['甲']['food'] = 100
    assert m._market_match_orders(countries, market, bank, 2) == []
    assert market['orders'][0]['qty'] == 100
    assert bank['issued_total'] == 40_000_000
    assert countries['甲']['food'] == 100


def test_single_resource_below_ten_percent_triggers_rebase_and_audit():
    countries, bank, market = fixture()
    market['stats']['food']['last_price'] = 60
    market['stats']['food']['vwap_10'] = 60
    market['recent_trades'] = [{'resource': 'food', 'turn': 2, 'qty': 10,
                                'price': 60, 'buyer': '乙', 'seller': '甲',
                                'gross_gold': 600, 'fee_gold': 0}]
    market['orders'] = [{'price': 60, 'qty': 10, 'side': 'SELL', 'resource': 'food'}]
    assert p.settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                  m.WORLD_CURRENCY_NAME_OPTIONS, 1, 2) == 'food'
    m._redenominate_currency(bank, countries, market)
    assert bank['issued_total'] == bank['initial_issued_total'] == 400_000_000
    assert bank['currency_denomination'] == 10
    assert market['stats']['food']['last_price'] == 600
    assert market['recent_trades'][0]['price'] == market['orders'][0]['price'] == 600
    assert p.policy_cost(m.BIRTH_POLICY_GOLD_COST, bank) == 1_200_000
    assert bank['policy_price_index'] == 1
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0
    assert p.settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                  m.WORLD_CURRENCY_NAME_OPTIONS, 2, 3) is None


def test_exact_tenth_triggers_but_stale_trade_does_not():
    countries, bank, market = fixture()
    market['recent_trades'] = [{'resource': 'food', 'turn': 2, 'qty': 10,
                                'price': 100, 'buyer': '乙', 'seller': '甲'}]
    assert p.settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                  m.WORLD_CURRENCY_NAME_OPTIONS, 1, 2) == 'food'
    assert p.settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                  m.WORLD_CURRENCY_NAME_OPTIONS, 2, 3) is None


def test_issuance_ratio_stays_the_same_after_rebase():
    countries, bank, market = fixture()
    countries['甲']['gold'] = bank['issued_total'] = 60_000_000
    p.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1, 1)
    m._redenominate_currency(bank, countries, market)
    assert bank['issued_total'] / bank['initial_issued_total'] == 1.5
    assert p.policy_cost(m.BIRTH_POLICY_GOLD_COST, bank) == 1_800_000
    assert m._normalize_world_bank(bank)['currency_denomination'] == 10
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0
