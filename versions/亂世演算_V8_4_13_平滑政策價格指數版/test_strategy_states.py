import importlib
import itertools
import json
from pathlib import Path


m = importlib.import_module('亂世演算_V8_4_13_平滑政策價格指數版')
compressed = importlib.import_module('strategy_states')


def country(**changes):
    base = dict(pop_total=100, farmers=70, soldiers=30, food=700, wood=300,
                metal=100, gold=600000, power=1500, prev_power=1500,
                political_stability=80, war_exhaustion=0, world_rank=7,
                season_phase='EARLY', is_alive=True)
    base.update(changes)
    return base


def test_four_readable_dimensions_at_most_256():
    agent = m.CountryRLAgent('測試國')
    for food, gold, power, rank in itertools.product((0, 20, 700, 2000),
                                                      (0, 5000, 600000, 3000000),
                                                      (100, 750, 1500, 5000),
                                                      (1, 2, 7, 30)):
        state = agent._get_strategic_state(country(food=food, gold=gold,
                                        power=power, world_rank=rank), 10000, 5000, 8)
        assert len(state) == 4
        assert all(state[i] in compressed.LABELS[i] for i in range(4))
        agent.strategic_policy.choose(state, list(range(11)))
    assert len(agent.strategic_policy.q_table) <= 256


def test_emergency_and_war_not_hidden_by_average():
    agent = m.CountryRLAgent('測試國')
    peaceful = agent._get_strategic_state(country(), 10000, 5000, 8)
    famine = agent._get_strategic_state(country(food=0), 10000, 5000, 8)
    war = agent._get_strategic_state(country(current_wars=['戰爭']), 10000, 5000, 8)
    assert famine[0] == '生存:危急' or famine[0] == '生存:吃緊'
    assert peaceful[0] != famine[0]
    assert war[1] == '軍事:交戰'


def test_expected_sarsa_learns_and_records_readable_state():
    agent = m.CountryRLAgent('測試國')
    before = country()
    state = agent._get_strategic_state(before, 10000, 5000, 8)
    policy = agent.strategic_policy
    policy.choose(state, list(range(11)))
    policy.learn(state, 2, 5.0, state, list(range(11)), success=True)
    assert policy.q_table[policy.state_key(state)][2] != 0
    assert policy.visit_counts[policy.state_key(state)] >= 1


def test_readable_q_output_and_save(tmp_path):
    agent = m.CountryRLAgent('甲')
    state = agent._get_strategic_state(country(), 10000, 5000, 8)
    key = agent.strategic_policy.state_key(state)
    agent.strategic_policy.q_table[key] = [0.0] * len(m.STRATEGIC_ACTIONS)
    agent.strategic_policy.q_table[key][2] = 1.25
    agent.strategic_policy.visit_counts[key] = 9
    readable = compressed.readable_q_text({'甲': agent}, m.STRATEGIC_ACTIONS)
    assert '軍備與動員：+1.2500' in readable
    assert '造訪 9 次' in readable
    assert '生存:' in readable
    original_path = m.save_path
    try:
        m.save_path = lambda filename: str(tmp_path / filename)
        m.save_all_agents({'甲': agent}, str(tmp_path / 'rl_agents_q_tables.json'))
    finally:
        m.save_path = original_path
    assert '甲' in (tmp_path / 'rl_strategic_q_readable.txt').read_text()
    stored = json.loads((tmp_path / 'rl_agents_q_tables.json').read_text())
    assert stored['甲']['rl_version'] == 7


def test_v6_backup_keeps_market_and_alliance_q(tmp_path):
    old_agent = m.CountryRLAgent('甲')
    market_key = json.dumps(['市場:測試'], ensure_ascii=False)
    old_agent.market_policy.q_table[market_key] = [1.0] + [0.0] * (len(m.MARKET_ACTIONS) - 1)
    old_agent.alliance_policy.q_table['["外交:測試"]'] = [0.5] + [0.0] * (len(m.ALLIANCE_ACTIONS) - 1)
    old = {'甲': {'rl_version': 6, 'action_size': m.RL_ACTION_SIZE,
                 'policies': old_agent.policy_payload()}}
    target = tmp_path / 'rl_agents_q_tables.json'
    target.write_text(json.dumps(old, ensure_ascii=False))
    loaded = m.load_all_agents(['甲'], str(target))['甲']
    assert not loaded.strategic_policy.q_table
    assert market_key in loaded.market_policy.q_table
    assert '["外交:測試"]' in loaded.alliance_policy.q_table
    assert (tmp_path / 'rl_agents_q_tables.json.pre_v7_backup').exists()
