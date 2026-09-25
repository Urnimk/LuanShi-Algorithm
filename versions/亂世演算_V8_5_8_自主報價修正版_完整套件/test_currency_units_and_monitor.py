"""換幣前後價格邊界與極大面額下的真實成交監測。"""
import importlib
from policy_index import settle_currency_name

m = importlib.import_module('亂世演算_V8_5_8_自主報價修正版')


def test_quotes_keep_the_same_relative_limits_after_rebase():
    bank = m._default_world_bank()
    bank['issued_total'] = 100000
    bank['treasury'] = 100000
    market = m._default_world_market()
    floor = m._market_price_floor('food', market)
    ceiling = m._market_price_ceiling('food', market)
    m._redenominate_currency(bank, {}, market, factor=10)
    assert market['currency_denomination'] == bank['currency_denomination'] == 10
    assert m._market_price_floor('food', market) == floor * 10
    assert m._market_price_ceiling('food', market) == ceiling * 10


def test_renaming_compares_with_current_currency_unit():
    bank = m._default_world_bank()
    bank['currency_denomination'] = 10
    market = {'recent_trades': [{'turn': 10, 'resource': 'food', 'qty': 20,
                                 'price': 0.9, 'buyer': '甲', 'seller': '乙'}]}
    assert settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                ('大洋', '銀幣'), 1, 10) == 'food'
    market['recent_trades'][0]['turn'] = 20
    market['recent_trades'][0]['price'] = 1.1
    assert settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                ('大洋', '銀幣'), 2, 20) is None


def test_monitored_index_never_rounds_small_positive_prices_to_zero():
    market = m._default_world_market()
    bank = m._default_world_bank()
    bank['currency_denomination'] = 10**23
    for r, price in [('food', .08), ('wood', 4.5), ('metal', 8.0)]:
        market['stats'][r]['traded_volume'] = 100
        market['stats'][r]['traded_value'] = int(price * 100)
    first = m._market_health_update(market, bank, {}, 10)
    assert first['index'] > 0
    assert all(v > 0 for v in first['prices'].values())
    for r in m.MARKET_RESOURCES:
        market['stats'][r]['traded_volume'] += 100
        market['stats'][r]['traded_value'] += max(1, market['stats'][r]['traded_value'] // 2)
    second = m._market_health_update(market, bank, {}, 20)
    assert second['index'] > 0 and second['index'] < first['index']
    assert bank['market_price_index'] == second['index']


def test_cross_currency_windows_are_not_a_real_price_drop():
    market = m._default_world_market()
    bank = m._default_world_bank()
    monitor = market['price_monitor']
    monitor['history'] = [dict(turn=10, index=1., coverage=3, volume=200, denomination=1),
                          dict(turn=20, index=.8, coverage=3, volume=200, denomination=1)]
    monitor['last_observed_turn'] = 20
    for r in m.MARKET_RESOURCES:
        market['stats'][r]['traded_volume'] = 100
        market['stats'][r]['traded_value'] = 100
    bank['currency_denomination'] = market['currency_denomination'] = 10
    latest = m._market_health_update(market, bank, {}, 30)
    assert latest['index'] > 0 and not latest['deflation']
