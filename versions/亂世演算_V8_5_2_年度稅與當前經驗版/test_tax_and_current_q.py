"""年度稅守恆與目前狀態 Q 值。"""
import importlib
import json

from annual_tax import collect_and_redistribute
from experience_view import render_current_q

m = importlib.import_module('亂世演算_V8_5_2_年度稅與當前經驗版')


def test_tax_rates_and_same_year_full_return():
    countries = {name: {'gold': gold, 'pop_total': 100, 'is_alive': True}
                 for name, gold in [('甲', 10_000), ('乙', 5_000), ('丙', 1_000)]}
    bank = m._default_world_bank()
    bank['issued_total'] = 16_000
    before = sum(c['gold'] for c in countries.values()) + bank['treasury']
    result = collect_and_redistribute(bank, countries, 7)
    assert result['taxes']['甲']['rate'] == .40
    assert result['taxes']['丙']['rate'] == .10
    assert .10 < result['taxes']['乙']['rate'] < .40
    assert result['collected'] == result['distributed'] == sum(result['grants'].values())
    assert sum(c['gold'] for c in countries.values()) + bank['treasury'] == before
    assert m._currency_audit(countries, bank, raise_on_error=True)['gap'] == 0
    again = collect_and_redistribute(bank, countries, 7)
    assert again['collected'] == 0
    assert m._normalize_world_bank(bank)['annual_tax_last_year'] == 7


def test_tied_wealth_tax_is_equal_and_minimum():
    countries = {name: {'gold': 100, 'pop_total': 10, 'is_alive': True} for name in ('甲', '乙')}
    result = collect_and_redistribute({'treasury': 0}, countries, 1)
    assert [result['taxes'][name]['rate'] for name in ('甲', '乙')] == [.10, .10]


def test_current_state_uses_full_q_table_even_if_not_in_top_24():
    state = ('生存:充裕', '軍事:安定', '發展:強盛', '爭冠:落後')
    key = json.dumps(list(state), ensure_ascii=False, separators=(',', ':'))
    agent = {'policies': {'strategic': {'q_table': {key: [1.5, -2]},
                                        'visit_counts': {key: 3}}}}
    text = render_current_q('甲', state, agent, {0: '發展', 1: '戰爭'})
    assert '造訪：3 次' in text and '發展：+1.5000' in text and '戰爭：-2.0000' in text
    assert text.count('目前狀態：') == 1
    missing = render_current_q('甲', ('其他',), agent, {0: '發展'})
    assert '尚無已存檔' in missing


def test_current_state_matches_engine_decision_formula():
    countries = {'甲': {'is_alive': True, 'pop_total': 100, 'farmers': 70,
                        'soldiers': 30, 'food': 1000, 'wood': 200,
                        'metal': 100, 'gold': 100000, 'power': 1000,
                        'world_rank': 1, 'policy_price_index': 1,
                        'currency_denomination': 1}}
    state = m.current_strategic_state('甲', countries)
    expected = m.CountryRLAgent('甲')._get_strategic_state(countries['甲'], 1000, 1000, 1)
    assert state == expected
