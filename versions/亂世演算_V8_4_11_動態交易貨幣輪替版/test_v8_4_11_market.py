import importlib


m = importlib.import_module('亂世演算_V8_4_11_動態交易貨幣輪替版')


def market_case(qty=500):
    countries = {'甲': {'is_alive': True, 'display_name': '甲', 'gold': 0,
                        'food': qty, 'wood': 0, 'metal': 0}}
    bank = m._default_world_bank()
    market = m._default_world_market()
    market['stats']['food']['last_price'] = 500
    market['orders'] = [{'id': 'M1', 'turn': 3, 'country': '甲', 'side': 'SELL',
                         'resource': 'food', 'qty': qty, 'price': 450}]
    return countries, bank, market


def test_bank_takes_real_order_without_120_cap():
    countries, bank, market = market_case()
    trades = m._market_match_orders(countries, market, bank, 4)
    assert sum(t['qty'] for t in trades) == 500
    assert bank['issued_total'] == 500000
    assert bank['market_reserves']['food'] == 500
    assert market['stats']['food']['last_price'] == 1000
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_independent_deflation_episode_rotates_currency_once():
    countries, bank, market = market_case()
    m._market_match_orders(countries, market, bank, 4)
    assert bank['currency'] == '大洋'
    m._market_match_orders(countries, market, bank, 5)  # 回到原價，通縮事件結束
    assert not bank['deflation_episode_active']
    market['stats']['food']['last_price'] = 500
    market['orders'] = [{'id': 'M2', 'turn': 6, 'country': '甲', 'side': 'SELL',
                         'resource': 'food', 'qty': 200, 'price': 450}]
    countries['甲']['food'] = 200
    m._market_match_orders(countries, market, bank, 6)
    assert bank['currency'] == '銀幣'
    assert bank['issued_total'] == countries['甲']['gold'] == 700000
    assert m._normalize_world_bank(bank)['currency'] == '銀幣'
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_ai_size_policy_scales_with_surplus_and_gold():
    data = {'pop_total': 1000, 'farmers': 700, 'soldiers': 300,
            'food': 1500, 'wood': 250000, 'metal': 0, 'gold': 10000000,
            'infrastructure': 50}
    countries = {'甲': data}
    market = m._default_world_market()
    small = m._market_place_layered_order('甲', countries, market, 1, 5, 1, 0)
    large = m._market_place_layered_order('甲', countries, market, 2, 5, 1, 2)
    assert large['qty'] > small['qty'] > 120
    assert large['qty'] <= data['wood']
    data['wood'] = 500000
    richer = m._market_place_layered_order('甲', countries, market, 3, 5, 1, 2)
    assert richer['qty'] > large['qty']


def test_twenty_backup_names_and_no_order_no_mint():
    assert len(m.WORLD_CURRENCY_NAME_OPTIONS) == 21
    assert len(set(m.WORLD_CURRENCY_NAME_OPTIONS)) == 21
    countries, bank, market = market_case()
    market['orders'].clear()
    m._market_match_orders(countries, market, bank, 4)
    assert bank['issued_total'] == 0
    assert market['stats']['food']['last_price'] == 500
