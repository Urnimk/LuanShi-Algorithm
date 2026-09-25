"""每屆調整一次的政策價格指數；不改交易價格或既有金幣帳務。"""

POLICY_INDEX_SMOOTHING = 0.25
POLICY_INDEX_SEASON_LIMIT = 0.08
POLICY_INDEX_MIN = 0.50
POLICY_INDEX_MAX = 4.00


def policy_cost(base, source=None):
    index = float((source or {}).get('policy_price_index', 1.0) or 1.0)
    return max(1, int(round(int(base) * index)))


def real_basket(countries):
    return max(1.0, sum(
        max(0, int(c.get('pop_total', 0) or 0)) * 5.0
        + max(0, float(c.get('food', 0) or 0))
        + max(0, float(c.get('wood', 0) or 0)) * 1.8
        + max(0, float(c.get('metal', 0) or 0)) * 3.2
        for c in countries.values() if c.get('is_alive', True)
    ))


def initialize(bank, countries):
    """舊存檔從當前世界作基準，不追溯歷史發行。"""
    if float(bank.get('policy_base_circulation', 0) or 0) <= 0:
        bank['policy_base_circulation'] = max(1, sum(
            max(0, int(c.get('gold', 0) or 0)) for c in countries.values()
        ))
        bank['policy_base_real_basket'] = real_basket(countries)
        bank['policy_price_index'] = 1.0
    return float(bank.get('policy_price_index', 1.0) or 1.0)


def settle_season(bank, countries, market, resources, round_number):
    """發行／實物比和成交價共同引導指數，單屆最大漲跌 8%。"""
    index = initialize(bank, countries)
    if int(bank.get('policy_last_round', 0) or 0) >= int(round_number):
        return index
    circulation = max(1, sum(max(0, int(c.get('gold', 0) or 0)) for c in countries.values()))
    basket = real_basket(countries)
    monetary = (circulation / max(1, bank['policy_base_circulation'])) / (
        basket / max(1.0, bank['policy_base_real_basket'])
    )
    price = sum(
        max(.01, float(market.get('stats', {}).get(res, {}).get('vwap_10', meta['seed_price'])
                        or meta['seed_price'])) / meta['seed_price']
        for res, meta in resources.items()
    ) / max(1, len(resources))
    target = max(POLICY_INDEX_MIN, min(POLICY_INDEX_MAX, monetary * .70 + price * .30))
    smooth = index + POLICY_INDEX_SMOOTHING * (target - index)
    result = round(max(POLICY_INDEX_MIN, min(POLICY_INDEX_MAX,
                       max(index * (1 - POLICY_INDEX_SEASON_LIMIT),
                           min(index * (1 + POLICY_INDEX_SEASON_LIMIT), smooth)))), 6)
    bank['policy_price_index'] = result
    bank['policy_index_target'] = round(target, 6)
    bank['policy_last_round'] = int(round_number)
    return result
