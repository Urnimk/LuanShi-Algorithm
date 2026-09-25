"""金庫守恆、預留額度與財政決策延後結算。"""
import importlib
from fiscal_policy import (treasury_circulation, fiscal_state, fiscal_valid_actions,
                           delayed_fiscal_reward, fiscal_q_report)

m = importlib.import_module('亂世演算_V8_5_10_市場流動性修正版')


def test_recycling_keeps_money_supply_and_does_not_pay_twice():
    bank = m._default_world_bank()
    bank.update(issued_total=10000, treasury=8500)
    countries = {f'C{i:02}': dict(is_alive=True, gold=15, pop_total=100)
                 for i in range(100)}
    before = m._currency_audit(countries, bank, raise_on_error=True)
    amounts = treasury_circulation(bank, countries, 10)
    assert sum(v for _, v in amounts) == 250  # 金庫集中觸發上限 2.5%
    assert len(amounts) > 0 and bank['issued_total'] == before['issued']
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0
    assert treasury_circulation(bank, countries, 10) == []
    assert treasury_circulation(bank, countries, 11) == []


def test_masks_reserved_gold_and_unfunded_policies():
    c = dict(gold=150, food=900, wood=60, metal=30, houses=20,
             pop_total=100, farmers=70, soldiers=30, infrastructure=2)
    market = m._default_world_market()
    market['orders'].append(dict(id='M1', country='C', side='BUY', resource='food', qty=90, price=1))
    reserved, _ = m._market_order_reservations(market, 'C')
    assert reserved == 90
    valid = fiscal_valid_actions(c, [3, 12, 13], c['gold']-reserved,
                                 120, 150, (60, 50, 20))
    assert valid == [0, 3]
    assert len(fiscal_state(c, dict(issued_total=10000, treasury=8500),
                            60, 800, 250, 100, 120, 150)) == 4
    assert fiscal_valid_actions(c, [3, 12, 13], 0, 120, 150, (60, 50, 20)) == [0]


def test_choose_fiscal_policy_instead_of_fixed_birth_rule():
    agent = m.CountryRLAgent('C')
    agent._get_strategic_state = lambda *_: ('a', 'b', 'c', 'd')
    agent.strategic_policy.choose = lambda _state, _valid: 7
    agent.fiscal_policy.choose = lambda _state, valid: max(valid)
    c = dict(gold=200, food=900, wood=100, metal=50, houses=20,
             pop_total=100, farmers=70, soldiers=30, infrastructure=0,
             currency_denomination=1)
    bank = m._default_world_bank()
    bank.update(issued_total=10000, treasury=8500)
    action = agent.choose_action(c, 1, 1, 1, [3, 7, 12, 13],
                                 bank, m._default_world_market())
    assert action == 3 and agent._last_fiscal_action == 3


def test_delayed_reward_requires_actual_outcome():
    baseline = dict(pop_total=100, food=1000, wood=100, metal=100,
                    infrastructure=0)
    stagnant = dict(baseline, is_alive=True, farmers=70, soldiers=30)
    improved = dict(stagnant, pop_total=111, infrastructure=4,
                    food=1200, wood=170, metal=150)
    assert delayed_fiscal_reward(1, baseline, improved, 120) > delayed_fiscal_reward(1, baseline, stagnant, 120)
    assert delayed_fiscal_reward(2, baseline, improved, 150) > delayed_fiscal_reward(2, baseline, stagnant, 150)
    assert delayed_fiscal_reward(3, baseline, improved, 60) > delayed_fiscal_reward(3, baseline, stagnant, 60)


def test_delayed_fiscal_q_credit_is_saved_and_settled_once():
    agent = m.CountryRLAgent('C')
    agent._last_state_str = agent.strategic_policy.state_key(('a', 'b', 'c', 'd'))
    agent._last_strategic_action = 7
    agent._last_fiscal_state = ('FUNDED', 'LOW', 'PRODUCTION', 'TIGHT')
    agent._last_fiscal_action = 2
    agent._last_fiscal_cost = 150
    before = dict(is_alive=True, pop_total=100, power=100, gold=500,
                  food=500, wood=50, metal=50, currency_denomination=1)
    agent.schedule_delayed_evaluation(before, 13, 10, True)
    restored = m.CountryRLAgent('C', policy_data=agent.policy_payload(),
                                pending_decisions=agent.pending_decisions)
    current = dict(before, pop_total=110, power=110, food=600, wood=160,
                   metal=120, farmers=80, soldiers=30)
    assert restored.settle_delayed_evaluations(current, 19) == []
    assert len(restored.settle_delayed_evaluations(current, 20)) == 1
    key = restored.fiscal_policy.state_key(agent._last_fiscal_state)
    first = restored.fiscal_policy.q_table[key][2]
    assert first > 0 and restored.pending_decisions == []
    assert restored.settle_delayed_evaluations(current, 21) == []
    assert restored.fiscal_policy.q_table[key][2] == first


def test_fiscal_report_is_readable():
    agent = m.CountryRLAgent('C')
    state = ('FUNDED', 'LOW', 'PRODUCTION', 'TIGHT')
    agent.fiscal_policy.q_table[agent.fiscal_policy.state_key(state)] = [0., .1, .25, -.2]
    report = fiscal_q_report({'C': agent})
    assert '國家：C' in report and 'FUNDED｜LOW｜PRODUCTION｜TIGHT' in report
    assert '增產補貼：+0.2500' in report
