"""年度富國累進現金稅，當年度全額回流缺錢國家。"""

MIN_ANNUAL_TAX_RATE = .10
MAX_ANNUAL_TAX_RATE = .40


def collect_and_redistribute(bank, countries, year):
    year = int(year)
    if year <= int(bank.get('annual_tax_last_year', 0) or 0):
        return {'collected': 0, 'distributed': 0, 'taxes': {}, 'grants': {}}
    active = [(key, data) for key, data in countries.items() if data.get('is_alive', True)]
    if len(active) < 2:
        bank['annual_tax_last_year'] = year
        return {'collected': 0, 'distributed': 0, 'taxes': {}, 'grants': {}}
    # 並列財富同稅率；同額金幣時全部適用最低 10%。
    amounts = {key: max(0, int(data.get('gold', 0) or 0)) for key, data in active}
    low, high = min(amounts.values()), max(amounts.values())
    taxes = {}
    for key, data in active:
        rate = MIN_ANNUAL_TAX_RATE + (
            (MAX_ANNUAL_TAX_RATE - MIN_ANNUAL_TAX_RATE)
            * (amounts[key] - low) / (high - low) if high > low else 0
        )
        tax = min(amounts[key], int(amounts[key] * rate))
        data['gold'] = amounts[key] - tax
        data['annual_tax_rate'] = round(rate, 4)
        data['last_annual_tax_paid'] = tax
        data['last_annual_tax_grant'] = 0
        taxes[key] = {'rate': round(rate, 4), 'amount': tax}
    collected = sum(entry['amount'] for entry in taxes.values())
    bank['treasury'] = int(bank.get('treasury', 0) or 0) + collected
    bank['annual_tax_collected'] = int(bank.get('annual_tax_collected', 0) or 0) + collected
    # 現金／人口最少的一半獲得全額回流，避免稅款滯留銀行加速通縮。
    poorest = sorted(active, key=lambda item: (int(item[1].get('gold', 0) or 0)
                      / max(1, int(item[1].get('pop_total', 1) or 1)), item[0]))
    recipients = poorest[:max(1, (len(poorest) + 1) // 2)]
    weights = [1 / (1 + max(0, int(data.get('gold', 0) or 0))
               / max(1, int(data.get('pop_total', 1) or 1))) for _, data in recipients]
    total_weight = sum(weights)
    grants = {}
    remaining = collected
    for index, ((key, data), weight) in enumerate(zip(recipients, weights)):
        share = remaining if index == len(recipients) - 1 else int(collected * weight / total_weight)
        share = min(remaining, share)
        data['gold'] = int(data.get('gold', 0) or 0) + share
        data['last_annual_tax_grant'] = share
        bank['treasury'] -= share
        remaining -= share
        grants[key] = share
    bank['annual_tax_redistributed'] = int(bank.get('annual_tax_redistributed', 0) or 0) + collected
    bank['annual_tax_last_year'] = year
    return {'collected': collected, 'distributed': collected, 'taxes': taxes, 'grants': grants}
