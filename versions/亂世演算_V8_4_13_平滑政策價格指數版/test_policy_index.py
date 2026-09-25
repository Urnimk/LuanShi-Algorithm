import importlib


m = importlib.import_module('亂世演算_V8_4_13_平滑政策價格指數版')
index_module = importlib.import_module('policy_index')


def case():
    countries = {
        '甲': {'is_alive': True, 'pop_total': 100, 'farmers': 80, 'soldiers': 20,
              'food': 2000, 'wood': 1500, 'metal': 500, 'gold': 40_000_000,
              'houses': 30, 'infrastructure': 0},
    }
    bank = m._default_world_bank()
    bank['issued_total'] = 40_000_000
    market = m._default_world_market()
    index_module.initialize(bank, countries)
    return countries, bank, market


def test_one_season_limit_and_gradual_convergence():
    countries, bank, market = case()
    countries['甲']['gold'] = 60_000_000
    bank['issued_total'] = 60_000_000
    assert index_module.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1) == 1.08
    assert index_module.policy_cost(m.BIRTH_POLICY_GOLD_COST, bank) == 129600
    assert index_module.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1) == 1.08
    assert index_module.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 2) <= 1.08 * 1.08 + 1e-6
    for season in range(3, 50):
        index_module.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, season)
    assert 1.34 < bank['policy_price_index'] < 1.351
    assert bank['issued_total'] == 60_000_000
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_real_goods_growth_can_offset_money_growth():
    countries, bank, market = case()
    countries['甲']['gold'] = 60_000_000
    countries['甲']['food'] *= 1.5
    countries['甲']['wood'] *= 1.5
    countries['甲']['metal'] *= 1.5
    index_module.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1)
    assert 1.0 <= bank['policy_price_index'] < 1.08


def test_downward_change_is_limited_and_repeated_round_does_nothing():
    countries, bank, market = case()
    countries['甲']['food'] = 500_000
    countries['甲']['wood'] = 100_000
    countries['甲']['metal'] = 50_000
    first = index_module.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1)
    assert first == 0.92
    assert index_module.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1) == first


def test_policy_cost_mask_execution_and_treasury_match():
    countries, bank, market = case()
    bank['policy_price_index'] = 1.5
    c = countries['甲']
    c['policy_price_index'] = 1.5
    assert index_module.policy_cost(m.BIRTH_POLICY_GOLD_COST, c) == 180000
    assert index_module.policy_cost(m.PRODUCTION_POLICY_GOLD_COST, c) == 225000
    c['gold'] = 179999
    assert 12 not in m.get_valid_rl_actions('甲', countries, {}, {}, ['甲'])
    assert not m._apply_birth_policy(c, bank)[0]
    c['gold'] = 180000
    assert 12 in m.get_valid_rl_actions('甲', countries, {}, {}, ['甲'])
    bank['issued_total'] = 180000
    assert m._apply_birth_policy(c, bank) == (True, 180000)
    assert c['gold'] == 0 and bank['treasury'] == 180000
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_legacy_bank_starts_at_current_price_and_can_reload():
    countries, bank, market = case()
    old_bank = {'issued_total': 40_000_000, 'currency': '銀幣', 'treasury': 0}
    normalized = m._normalize_world_bank(old_bank)
    index_module.initialize(normalized, countries)
    assert normalized['currency'] == '銀幣'
    assert normalized['policy_price_index'] == 1.0
    assert normalized['policy_base_circulation'] == 40_000_000
    normalized['policy_price_index'] = 1.08
    reloaded = m._normalize_world_bank(normalized)
    assert reloaded['policy_price_index'] == 1.08
    assert reloaded['policy_base_circulation'] == 40_000_000
