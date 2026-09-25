"""產銷平衡與年度稅取消的帳務驗證。"""
import importlib
import random

m = importlib.import_module('亂世演算_V8_5_3_供需平衡版')


def test_housing_consumes_actual_wood_without_negative_resources():
    random.seed(14)
    c = {'display_name': '農國', 'is_alive': True, 'pop_total': 100,
         'farmers': 70, 'soldiers': 30, 'houses': 15,
         'food': 5000, 'wood': 150, 'metal': 400,
         'gold': 400_000, 'military_target_ratio': .30}
    for _ in range(80):
        m.update_rts_economy_and_jobs(c)
        assert c['food'] >= 0 and c['wood'] >= 0 and c['metal'] >= 0
        assert c['farmers'] + c['soldiers'] == c['pop_total']
    assert c['wood_maintenance_spent'] > 0


def test_no_annual_tax_changes_balances():
    c = {'甲': {'gold': 2_000, 'is_alive': True},
         '乙': {'gold': 1_000, 'is_alive': True}}
    bank = m._default_world_bank()
    bank['issued_total'] = 3_000
    before = (c['甲']['gold'], c['乙']['gold'], bank['treasury'])
    for turn in range(1, 11):
        m._world_bank_recirculate_liquidity(bank, c, turn)
    assert (c['甲']['gold'], c['乙']['gold'], bank['treasury']) == before
    assert m._currency_audit(c, bank, raise_on_error=True)['gap'] == 0


def test_more_wood_surplus_reduces_new_harvest():
    basis = {'display_name': '測試國', 'is_alive': True, 'pop_total': 100,
             'farmers': 70, 'soldiers': 30, 'houses': 15,
             'food': 1500, 'metal': 400, 'gold': 400000,
             'military_target_ratio': .30}
    moderate = dict(basis, wood=350)
    glutted = dict(basis, wood=1400)
    random.seed(15)
    m.update_rts_economy_and_jobs(moderate)
    random.seed(15)
    m.update_rts_economy_and_jobs(glutted)
    # 扣掉相同房屋維修後，極度過剩國每輪新增的木材應較少。
    assert (glutted['wood'] - 1400) < (moderate['wood'] - 350)
