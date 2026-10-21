"""每屆固定通膨倍率 = 累計發行量／最初發行量。"""

def policy_cost(base, source=None):
    index = float((source or {}).get('policy_price_index', 1.0) or 1.0)
    denomination = max(1, int((source or {}).get('currency_denomination', 1) or 1))
    return max(1, int(round(int(base) * index * denomination)))


def _circulation(countries):
    return max(1, sum(max(0, int(c.get('gold', 0) or 0)) for c in countries.values()))


def initialize(bank, countries):
    """首次建世界時記錄初始發行量；舊存檔無歷史則從現有發行量建基準。"""
    if int(bank.get('policy_index_schema', 0) or 0) < 4:
        initial = (int(bank.get('initial_issued_total', 0) or 0)
                   or int(bank.get('policy_base_issued_total', 0) or 0)
                   or int(bank.get('issued_total', 0) or 0)
                   or _circulation(countries))
        bank['initial_issued_total'] = max(1, initial)
        # 名稱更換仍是 1:1，與通膨計算及 issued_total 無關。
        bank['policy_price_index'] = max(0.0, int(bank.get('issued_total', 0) or 0)) / bank['initial_issued_total']
        bank['policy_index_target'] = bank['policy_price_index']
        if int(bank.get('policy_index_schema', 0) or 0) < 2:
            bank['currency_issue_baseline'] = int(bank.get('market_issued_total', 0) or 0)
            bank['currency_deflation_streak'] = 0
            bank['currency_recovery_streak'] = 0
            bank['currency_episode_active'] = False
        bank['policy_index_schema'] = 4
    return float(bank['policy_price_index'])


def market_evidence(market, resources, last_observed_turn, current_turn):
    """只取當屆國家間真實成交；銀行介入和沒有新成交的舊 VWAP 不計。"""
    per_resource = {}
    for trade in market.get('recent_trades', []) or []:
        turn = int(trade.get('turn', 0) or 0)
        res = trade.get('resource')
        if (res not in resources or turn <= last_observed_turn or turn > current_turn
                or trade.get('buyer') == '世界銀行' or trade.get('seller') == '世界銀行'):
            continue
        qty = max(0, int(trade.get('qty', 0) or 0))
        if qty:
            sums = per_resource.setdefault(res, [0.0, 0])
            sums[0] += qty * max(0.01, float(trade.get('price', 0) or 0))
            sums[1] += qty
    ratios = {
        res: amount / qty / resources[res]['seed_price']
        for res, (amount, qty) in per_resource.items() if qty >= 10
    }
    return ratios


def settle_season(bank, countries, market, resources, round_number, current_turn):
    """屆末結算下屆倍率；不平滑、不限制每屆幅度。"""
    index = initialize(bank, countries)
    if int(bank.get('policy_last_round', 0) or 0) >= int(round_number):
        return index
    result = int(bank.get('issued_total', 0) or 0) / max(1, int(bank['initial_issued_total']))
    bank['policy_price_index'] = result
    bank['policy_index_target'] = result
    bank['policy_last_round'] = int(round_number)
    return result


def settle_currency_name(bank, market, resources, options, round_number, current_turn):
    """本屆某一商品最後一筆國家間成交低至預設價 10% 才換幣。"""
    if int(bank.get('currency_last_checked_round', 0) or 0) >= int(round_number):
        return None
    observed = int(bank.get('currency_last_observed_turn', -1) or -1)
    latest = {}
    for trade in market.get('recent_trades', []) or []:
        turn = int(trade.get('turn', 0) or 0)
        resource = trade.get('resource')
        if (resource not in resources or turn <= observed or turn > int(current_turn)
                or trade.get('buyer') == '世界銀行' or trade.get('seller') == '世界銀行'
                or int(trade.get('qty', 0) or 0) <= 0):
            continue
        if turn >= latest.get(resource, (-1, None))[0]:
            latest[resource] = (turn, trade)
    bank['currency_last_observed_turn'] = int(current_turn)
    bank['currency_last_checked_round'] = int(round_number)
    threshold = float(bank.get('currency_rename_trigger_rate', .10) or .10)
    denomination = max(1, int(bank.get('currency_denomination', 1) or 1))
    candidates = [
        (float(trade['price']) / (float(resources[res]['seed_price']) * denomination), res)
        for res, (_, trade) in latest.items()
        if float(resources[res]['seed_price']) > 0
        and float(trade.get('price', 0) or 0) <= float(resources[res]['seed_price']) * denomination * threshold
    ]
    if not candidates or not options:
        return None
    _, resource = min(candidates)
    bank['currency_name_index'] = (int(bank.get('currency_name_index', 0) or 0) + 1) % len(options)
    bank['currency'] = options[bank['currency_name_index']]
    bank['currency_rename_last_round'] = int(round_number)
    return resource
