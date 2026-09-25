"""政策成本依貨幣／人口及實際市場成交平滑變化；避開囤貨假性通縮。"""

POLICY_INDEX_SMOOTHING = 0.25
POLICY_INDEX_SEASON_LIMIT = 0.08
POLICY_INDEX_MIN = 0.50
POLICY_INDEX_MAX = 4.00


def policy_cost(base, source=None):
    index = float((source or {}).get('policy_price_index', 1.0) or 1.0)
    return max(1, int(round(int(base) * index)))


def _circulation(countries):
    return max(1, sum(max(0, int(c.get('gold', 0) or 0)) for c in countries.values()))


def _population(countries):
    return max(1, sum(max(0, int(c.get('pop_total', 0) or 0))
                      for c in countries.values() if c.get('is_alive', True)))


def initialize(bank, countries):
    """舊模型曾用庫存壓低成本；升級時以當前世界重設基準和最低原價。"""
    if int(bank.get('policy_index_schema', 0) or 0) < 2:
        bank['policy_price_index'] = max(1.0, float(bank.get('policy_price_index', 1.0) or 1.0))
        bank['policy_base_circulation'] = _circulation(countries)
        bank['policy_base_population'] = _population(countries)
        bank['policy_index_target'] = bank['policy_price_index']
        bank['policy_deflation_streak'] = 0
        bank['currency_issue_baseline'] = int(bank.get('market_issued_total', 0) or 0)
        bank['currency_deflation_streak'] = 0
        bank['currency_recovery_streak'] = 0
        bank['currency_episode_active'] = False
        bank['policy_index_schema'] = 2
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
    """單屆最多 ±8%；正常物價時不因庫存膨脹而把政策越算越便宜。"""
    index = initialize(bank, countries)
    if int(bank.get('policy_last_round', 0) or 0) >= int(round_number):
        return index
    monetary = (_circulation(countries) / max(1, bank['policy_base_circulation'])) / (
        _population(countries) / max(1, bank['policy_base_population'])
    )
    last_turn = int(bank.get('policy_last_observed_turn', -1) or -1)
    ratios = market_evidence(market, resources, last_turn, int(current_turn))
    bank['policy_last_observed_turn'] = int(current_turn)
    # 至少兩種商品當屆有新成交，才以當屆成交價形成市場訊號。
    broad_price = sum(ratios.values()) / len(ratios) if len(ratios) >= 2 else 1.0
    real_deflation = len(ratios) >= 2 and broad_price < .90 and monetary < .90
    streak = int(bank.get('policy_deflation_streak', 0) or 0) + 1 if real_deflation else 0
    bank['policy_deflation_streak'] = streak
    target = max(POLICY_INDEX_MIN, min(POLICY_INDEX_MAX,
                                      monetary * .70 + broad_price * .30))
    # 只有連續兩屆同時出現廣泛跌價與人均流通貨幣下降，才降低費用。
    if streak < 2:
        target = max(index, target)
    smooth = index + POLICY_INDEX_SMOOTHING * (target - index)
    result = round(max(POLICY_INDEX_MIN, min(POLICY_INDEX_MAX,
                       max(index * (1 - POLICY_INDEX_SEASON_LIMIT),
                           min(index * (1 + POLICY_INDEX_SEASON_LIMIT), smooth)))), 6)
    bank['policy_price_index'] = result
    bank['policy_index_target'] = round(target, 6)
    bank['policy_last_round'] = int(round_number)
    return result


def settle_currency_name(bank, market, resources, options, round_number, current_turn):
    """跨兩屆、至少兩種商品真實成交低於觸發線，且市場確實復原後才可再改名。"""
    if int(bank.get('currency_last_checked_round', 0) or 0) >= int(round_number):
        return False
    ratios = market_evidence(market, resources,
                             int(bank.get('currency_last_observed_turn', -1) or -1),
                             int(current_turn))
    bank['currency_last_observed_turn'] = int(current_turn)
    bank['currency_last_checked_round'] = int(round_number)
    threshold = float(bank.get('currency_rename_trigger_rate', .60) or .60)
    depressed = len(ratios) >= 2 and sum(v <= threshold for v in ratios.values()) >= 2
    recovered = len(ratios) >= 2 and all(v >= max(.75, threshold + .15) for v in ratios.values())
    if recovered:
        bank['currency_recovery_streak'] = int(bank.get('currency_recovery_streak', 0) or 0) + 1
        if bank['currency_recovery_streak'] >= 2:
            bank['currency_episode_active'] = False
    else:
        bank['currency_recovery_streak'] = 0
    bank['currency_deflation_streak'] = (int(bank.get('currency_deflation_streak', 0) or 0) + 1
                                         if depressed else 0)
    if (bank['currency_deflation_streak'] < 2 or bank.get('currency_episode_active', False)
            or int(bank.get('market_issued_total', 0) or 0) <= int(bank.get('currency_issue_baseline', 0) or 0)
            or int(round_number) - int(bank.get('currency_rename_last_round', -999) or -999) < 3):
        return False
    bank['currency_episode_active'] = True
    bank['currency_name_index'] = (int(bank.get('currency_name_index', 0) or 0) + 1) % len(options)
    bank['currency'] = options[bank['currency_name_index']]
    bank['currency_rename_last_round'] = int(round_number)
    bank['currency_issue_baseline'] = int(bank.get('market_issued_total', 0) or 0)
    return True
