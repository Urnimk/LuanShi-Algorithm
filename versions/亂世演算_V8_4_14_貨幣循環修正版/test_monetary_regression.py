"""復現亂換幣、政策費越變越低、銀行印鈔失控等情境。"""

import importlib


m = importlib.import_module('亂世演算_V8_4_14_貨幣循環修正版')
policy = importlib.import_module('policy_index')


def example():
    countries = {'甲': {'is_alive': True, 'display_name': '甲', 'pop_total': 1000,
                        'farmers': 700, 'soldiers': 300,
                        'gold': 40_000_000, 'food': 10000, 'wood': 1000, 'metal': 500}}
    bank = m._default_world_bank()
    bank['issued_total'] = 40_000_000
    bank['current_season_round'] = 1
    market = m._default_world_market()
    policy.initialize(bank, countries)
    return countries, bank, market


def add_order(market, resource, qty, price, turn=1, side='SELL', owner='甲'):
    order = {'id': 'M' + str(market.get('order_sequence', 0) + 1), 'turn': turn,
             'country': owner, 'resource': resource, 'side': side,
             'qty': qty, 'price': price}
    market['order_sequence'] += 1
    market['orders'].append(order)
    return order


def test_normal_prices_and_old_one_item_low_never_rename():
    countries, bank, market = example()
    bank['market_issued_total'] = 100000
    for season in range(1, 12):
        market['stats']['food']['last_price'] = 200
        m._market_match_orders(countries, market, bank, season)
        assert not policy.settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                               m.WORLD_CURRENCY_NAME_OPTIONS, season, season)
    assert bank['currency'] == '大洋'


def test_inventory_boom_with_stable_market_does_not_lower_policy():
    countries, bank, market = example()
    countries['甲']['wood'] = 200_000_000
    countries['甲']['metal'] = 50_000_000
    for season in range(1, 18):
        policy.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, season, season)
    assert bank['policy_price_index'] == 1.0
    assert policy.policy_cost(m.BIRTH_POLICY_GOLD_COST, bank) == 120000


def test_more_circulating_money_raises_fees_gradually():
    countries, bank, market = example()
    countries['甲']['gold'] = 60_000_000
    bank['issued_total'] = 60_000_000
    policy.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1, 1)
    assert bank['policy_price_index'] == 1.08
    assert policy.policy_cost(m.BIRTH_POLICY_GOLD_COST, bank) == 129600
    assert policy.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1, 1) == 1.08
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_new_issuance_uses_budget_without_unit_cap_or_accounting_gap():
    countries, bank, market = example()
    countries['甲']['wood'] = 10000
    market['stats']['wood']['last_price'] = 900
    first = add_order(market, 'wood', 5000, 800)
    trades = m._market_match_orders(countries, market, bank, 1)
    assert sum(t['qty'] for t in trades) > 120
    assert 0 < bank['market_issued_this_season'] <= 2_000_000
    assert bank['market_issue_season_budget'] == 2_000_000
    assert first['qty'] > 0  # 有效賣單超過貨幣發行預算，保留剩餘單
    for turn in range(2, 10):
        market['stats']['wood']['last_price'] = 900
        m._market_match_orders(countries, market, bank, turn)
    assert bank['market_issued_this_season'] <= bank['market_issue_season_budget']
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_bank_first_spends_treasury_and_resells_real_inventory():
    countries, bank, market = example()
    bank['treasury'] = 500000
    bank['issued_total'] += 500000
    market['stats']['wood']['last_price'] = 900
    add_order(market, 'wood', 100, 800)
    m._market_match_orders(countries, market, bank, 1)
    assert bank['market_issued_this_season'] == 0
    assert bank['market_reserves']['wood'] == 100
    countries['甲']['gold'] += 1_000_000
    bank['issued_total'] += 1_000_000
    add_order(market, 'wood', 90, 1800, turn=2, side='BUY')
    m._market_match_orders(countries, market, bank, 2)
    assert bank['market_reserves']['wood'] == 10
    assert bank['treasury'] == 90 * 1800 + 500000 - 100 * 1800
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_rename_is_one_to_one_only_after_confirmed_multi_item_deflation():
    countries, bank, market = example()
    # 有當屆新發貨幣；市場兩種資源連續兩屆確實以低價交易。
    bank['market_issued_total'] += 1
    for season in (1, 2):
        for res in ('food', 'wood'):
            market['recent_trades'].append({'turn': season, 'resource': res,
                'qty': 20, 'price': m.MARKET_RESOURCE_META[res]['seed_price'] * .5,
                'buyer': '甲', 'seller': '乙'})
        changed = policy.settle_currency_name(bank, market, m.MARKET_RESOURCE_META,
                                                m.WORLD_CURRENCY_NAME_OPTIONS, season, season)
    assert changed and bank['currency'] == '銀幣'
    assert countries['甲']['gold'] == 40_000_000
    assert bank['issued_total'] == 40_000_000
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_previous_discounted_save_is_rebased_once():
    countries, bank, market = example()
    bank['policy_index_schema'] = 1
    bank['policy_price_index'] = .57
    bank['market_issued_total'] = 1234
    normalized = m._normalize_world_bank(bank)
    assert policy.initialize(normalized, countries) == 1.0
    assert normalized['currency_issue_baseline'] == 1234
    assert policy.initialize(normalized, countries) == 1.0
    assert m._normalize_world_bank(normalized)['policy_index_schema'] == 2
