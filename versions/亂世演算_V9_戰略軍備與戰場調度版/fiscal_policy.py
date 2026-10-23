"""有邊界的國家財政決策與銀行既有貨幣回流。"""
import json

FISCAL_ACTIONS = {0: '維持預算', 1: '鼓勵生育', 2: '增產補貼', 3: '基建投資'}


def fiscal_q_report(agents):
    """每國列出最常造訪的財政狀態與原始 Q 數值；完整資料仍在 JSON。"""
    lines = ['財政 Q 值觀察表｜狀態順序：可用預算／物資安全／政策機會／貨幣流通']
    for name, agent in sorted(agents.items()):
        policy = agent.fiscal_policy
        lines.append(f'國家：{name}｜已學狀態 {len(policy.q_table)}/81')
        for key in sorted(policy.q_table, key=lambda k: (-policy.visit_counts.get(k, 0), k))[:5]:
            try:
                state = '｜'.join(map(str, json.loads(key)))
            except (ValueError, TypeError):
                state = str(key)
            lines.append(f'  {state}｜造訪 {policy.visit_counts.get(key, 0)} 次')
            for index, value in enumerate(policy.q_table[key]):
                lines.append(f'    {FISCAL_ACTIONS[index]}：{float(value):+.4f}')
    return '\n'.join(lines)


def treasury_circulation(bank, countries, turn, interval=10, share=.01,
                         target_treasury_share=.35, reserve_share=.25, money_ratio=1,
                         max_share=.025):
    """國庫過度集中且多數存活國家缺現金時回流，永不增加發行量。"""
    if turn <= 0 or turn % interval or bank.get('fiscal_recycle_last_turn') == turn:
        return []
    issued = max(0, int(bank.get('issued_total', 0) or 0))
    treasury = max(0, int(bank.get('treasury', 0) or 0))
    alive = sorted((k, v) for k, v in countries.items() if v.get('is_alive', True))
    if not alive or issued <= 0 or treasury <= issued * target_treasury_share:
        return []
    # 政策價已包含目前幣別及通膨倍率。以每人 3 單位界定買方現金壓力。
    from policy_index import policy_cost
    cost_per_person = policy_cost(3 * money_ratio, bank)
    shortage = []
    for key, country in alive:
        pop = max(1, int(country.get('pop_total', 1) or 1))
        gold = max(0, int(country.get('gold', 0) or 0))
        gap = max(0, pop * cost_per_person - gold)
        if gap:
            shortage.append((key, country, gap))
    if len(shortage) < max(2, (len(alive) + 1) // 2):
        return []
    # 金庫越集中且缺現金國家越多，回流越快；每十回合仍受發行量 2.5% 與準備金限制。
    stressed_fraction = len(shortage) / len(alive)
    excess_fraction = max(0., treasury / issued - target_treasury_share)
    effective_share = min(max_share, share + .04 * excess_fraction * stressed_fraction)
    budget = min(max(0, treasury - int(issued * reserve_share)),
                 max(1, int(issued * effective_share)))
    if budget <= 0:
        return []
    # 按缺口比例分配，且任何國家不能拿到超過實際缺口；按國名排序保持 Seed 可重現。
    pending = list(shortage)
    awards = {key: 0 for key, _country, _gap in shortage}
    while budget and pending:
        total_gap = sum(gap for _key, _country, gap in pending)
        if not total_gap:
            break
        distributed = 0
        remaining = []
        for key, country, gap in pending:
            amount = min(gap, max(1, int(budget * gap / total_gap)))
            amount = min(amount, budget - distributed)
            if amount <= 0:
                remaining.append((key, country, gap))
                continue
            awards[key] += amount
            distributed += amount
            if gap > amount:
                remaining.append((key, country, gap - amount))
            if distributed >= budget:
                break
        if not distributed:
            break
        budget -= distributed
        pending = remaining
    total = sum(awards.values())
    if not total:
        return []
    for key, country, _gap in shortage:
        country['gold'] = max(0, int(country.get('gold', 0) or 0)) + awards[key]
    bank['treasury'] = treasury - total
    bank['liquidity_redistributed'] = max(0, int(bank.get('liquidity_redistributed', 0) or 0)) + total
    bank['liquidity_operations'] = max(0, int(bank.get('liquidity_operations', 0) or 0)) + 1
    bank['fiscal_recycle_total'] = max(0, int(bank.get('fiscal_recycle_total', 0) or 0)) + total
    bank['fiscal_recycle_last_turn'] = turn
    bank['last_action'] = f'既有金庫回流 {total}，支援 {sum(v > 0 for v in awards.values())} 國'
    return [(key, amount) for key, amount in awards.items() if amount]


def fiscal_state(country, bank, free_cash, food_target, wood_target, metal_target,
                 birth_cost, production_cost):
    """四個各最多三級的訊號，共最多 81 種組合。"""
    cash = max(0, int(free_cash))
    cheapest = max(1, min(birth_cost, production_cost))
    budget = 'NO_CASH' if cash < cheapest else 'LIMITED' if cash < cheapest * 3 else 'FUNDED'
    food = float(country.get('food', 0) or 0) / max(1., food_target)
    wood = float(country.get('wood', 0) or 0) / max(1., wood_target)
    metal = float(country.get('metal', 0) or 0) / max(1., metal_target)
    lowest = min(food, wood, metal)
    supply = 'CRITICAL' if lowest < .65 else 'LOW' if lowest < 1.1 else 'SAFE'
    housing_room = max(0, int(country.get('houses', 0) or 0) * 10
                       - int(country.get('pop_total', 0) or 0))
    opportunity = ('PRODUCTION' if lowest < .9 else
                   'BIRTH' if food >= 1.0 and housing_room >= 10 else 'MAINTAIN')
    issued = max(1, int(bank.get('issued_total', 0) or 0))
    bank_share = float(bank.get('treasury', 0) or 0) / issued
    circulation = 'TIGHT' if bank_share >= .70 else 'NORMAL' if bank_share >= .35 else 'LOOSE'
    return budget, supply, opportunity, circulation


def fiscal_valid_actions(country, engine_valid, free_cash, birth_cost, production_cost,
                         infrastructure_cost):
    valid = [0]
    if 12 in engine_valid and free_cash >= birth_cost and int(country.get('birth_policy_turns', 0) or 0) <= 1:
        valid.append(1)
    if 13 in engine_valid and free_cash >= production_cost and int(country.get('production_policy_turns', 0) or 0) <= 1:
        valid.append(2)
    gold_cost, wood_cost, metal_cost = infrastructure_cost
    if (3 in engine_valid and free_cash >= gold_cost
            and int(country.get('wood', 0) or 0) >= wood_cost
            and int(country.get('metal', 0) or 0) >= metal_cost):
        valid.append(3)
    return valid


def delayed_fiscal_reward(action, baseline, current, cost, denomination=1):
    """政策期滿後給財政 Q 的結果回饋；不可把一般國力變化全歸給政策。"""
    if action not in (1, 2, 3):
        return 0.0
    if not current.get('is_alive', True):
        return -1.0
    pop0 = max(1, int(baseline.get('pop_total', 1) or 1))
    food_now = float(current.get('food', 0) or 0)
    food_runway = food_now / max(1., float(current.get('farmers', 0) or 0)
                                  + float(current.get('soldiers', 0) or 0) * 2)
    cost_scale = max(1., float(cost) / max(1, denomination))
    if action == 1:
        increase = max(0, int(current.get('pop_total', 0) or 0) - pop0)
        score = min(1., increase / max(2., pop0 * .06))
        return max(-1., min(1., score * .85 - (.8 if food_runway < 2 else 0.) - min(.25, cost_scale / max(1., pop0) * .05)))
    if action == 2:
        # 存量按人口折算；只比較政策結束時的缺口，避免立即領到資源就獲滿分。
        before = min(float(baseline.get(r, 0) or 0) / pop0 for r in ('food', 'wood', 'metal'))
        now_pop = max(1, int(current.get('pop_total', 1) or 1))
        after = min(float(current.get(r, 0) or 0) / now_pop for r in ('food', 'wood', 'metal'))
        score = max(-.5, min(1., (after - before) / max(1., before)))
        return max(-1., min(1., score * .8 - (.4 if food_runway < 2 else 0.) - min(.25, cost_scale / max(1., pop0) * .05)))
    increase = max(0, int(current.get('infrastructure', 0) or 0)
                   - int(baseline.get('infrastructure', 0) or 0))
    return max(-1., min(1., .15 * increase - min(.25, cost_scale / max(1., pop0) * .05)))
