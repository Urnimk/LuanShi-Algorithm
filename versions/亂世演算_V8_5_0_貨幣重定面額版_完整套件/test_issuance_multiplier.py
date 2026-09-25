"""固定發行倍率：政策、給付、換名與帳本的關鍵回歸測試。"""

import importlib


m = importlib.import_module('亂世演算_V8_5_貨幣重定面額版')
pricing = importlib.import_module('policy_index')


def world():
    country = dict(is_alive=True, display_name='甲', pop_total=100, farmers=80,
                   soldiers=20, gold=40_000_000, food=800, wood=500, metal=200,
                   houses=20, infrastructure=0)
    countries = {'甲': country}
    bank = m._default_world_bank()
    bank['issued_total'] = 40_000_000
    pricing.initialize(bank, countries)
    return countries, bank, m._default_world_market()


def test_base_issued_total_remains_fixed_and_ratio_is_exact_next_season():
    countries, bank, market = world()
    assert bank['initial_issued_total'] == 40_000_000
    assert bank['policy_price_index'] == 1.0
    countries['甲']['gold'] += 20_000_000
    bank['issued_total'] += 20_000_000
    assert bank['policy_price_index'] == 1.0  # 本屆凍結
    assert pricing.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1, 5) == 1.5
    assert bank['initial_issued_total'] == 40_000_000
    assert pricing.policy_cost(m.BIRTH_POLICY_GOLD_COST, bank) == 180_000
    assert pricing.policy_cost(m.PRODUCTION_POLICY_GOLD_COST, bank) == 225_000
    assert pricing.policy_cost(m.WORLD_BANK_RESPAWN_GRANT, bank) == 180_000
    assert pricing.policy_cost(m.SEASON_CHAMPION_GOLD_REWARD, bank) == 225_000
    assert pricing.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1, 5) == 1.5
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0


def test_more_goods_more_people_or_low_market_price_cannot_lower_ratio():
    countries, bank, market = world()
    countries['甲']['gold'] += 20_000_000
    bank['issued_total'] += 20_000_000
    countries['甲']['pop_total'] = 50_000
    countries['甲']['wood'] = 5_000_000
    countries['甲']['metal'] = 2_000_000
    for stat in market['stats'].values():
        stat['last_price'] *= 0.15
        stat['vwap_10'] *= 0.15
    for season in range(1, 10):
        assert pricing.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, season, season) == 1.5


def test_birth_infrastructure_and_rewards_use_same_multiplier():
    countries, bank, market = world()
    countries['甲']['gold'] += 20_000_000
    bank['issued_total'] += 20_000_000
    pricing.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1, 1)
    c = countries['甲']
    c['policy_price_index'] = bank['policy_price_index']
    assert m._infrastructure_investment_cost(c)[0] == 90_000
    assert 12 in m.get_valid_rl_actions('甲', countries, {}, {}, ['甲'])
    assert m._apply_birth_policy(c, bank) == (True, 180_000)
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0
    respawn = {'gold': 0}
    paid = m._world_bank_grant(bank, respawn, pricing.policy_cost(m.WORLD_BANK_RESPAWN_GRANT, bank), '重建援助')
    assert paid == respawn['gold'] == 180_000
    assert bank['issued_total'] == 60_000_000  # 有足夠銀行金庫，獎助沒有再增發
    assert m._currency_audit({'甲': c, '重建國': respawn}, bank, raise_on_error=True)['gap'] == 0


def test_old_save_without_initial_baseline_uses_current_issued_once():
    countries, bank, market = world()
    older = m._normalize_world_bank({
        'issued_total': 60_000_000, 'policy_index_schema': 2,
        'policy_price_index': .55, 'currency': '銀幣',
    })
    countries['甲']['gold'] = 60_000_000
    assert pricing.initialize(older, countries) == 1.0
    assert older['initial_issued_total'] == 60_000_000
    assert older['currency'] == '銀幣'
    assert m._normalize_world_bank(older)['initial_issued_total'] == 60_000_000
    assert m._currency_audit(countries, older, raise_on_error=True)['gap'] == 0


def test_award_mint_does_not_raise_cost_again_within_same_season():
    countries, bank, market = world()
    result = m._award_season_champion_rewards('甲', countries, {}, bank, 1)
    assert result['champion'] == 150000
    assert bank['issued_total'] == 40_150_000
    assert bank['policy_price_index'] == 1.0
    pricing.settle_season(bank, countries, market, m.MARKET_RESOURCE_META, 1, 1)
    assert bank['policy_price_index'] == 40_150_000 / 40_000_000
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0
