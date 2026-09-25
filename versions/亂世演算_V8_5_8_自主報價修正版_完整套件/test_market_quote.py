"""報價依庫存調整，Q 僅因實際成交價格品質獲得額外獎勵。"""
import importlib

m = importlib.import_module('亂世演算_V8_5_8_自主報價修正版')


def test_stock_urgency_affects_buy_and_sell_quotes():
    market = m._default_world_market()
    poor = m._market_reservation_price('BUY', 'wood', .10, 2., 1, market)
    full = m._market_reservation_price('BUY', 'wood', 1.50, 2., 1, market)
    assert poor > 2. > full
    assert m._market_reservation_price('SELL', 'wood', .25, 2., 1, market) > 2.
    assert m._market_reservation_price('SELL', 'wood', 3., 2., 1, market) < 2.
    assert m._market_price_floor('wood', market) <= poor <= m._market_price_ceiling('wood', market)


def test_price_actions_still_control_aggression():
    market = m._default_world_market()
    for side in ('BUY', 'SELL'):
        bids = [m._market_reservation_price(side, 'food', .6, 1., action, market)
                for action in range(3)]
        assert bids == sorted(bids) if side == 'BUY' else bids == sorted(bids, reverse=True)


def test_trade_price_quality_and_zero_net_sale():
    buy = {'side': 'BUY', 'reference_price': 2.0}
    sell = {'side': 'SELL', 'reference_price': 2.0}
    low = [{'qty': 10, 'price': 1.8, 'gross_gold': 18, 'fee_gold': 1}]
    high = [{'qty': 10, 'price': 2.2, 'gross_gold': 22, 'fee_gold': 1}]
    assert m._market_quote_quality(buy, low) > m._market_quote_quality(buy, high)
    assert m._market_quote_quality(sell, high) > m._market_quote_quality(sell, low)
    assert m._market_quote_quality(sell, [{'qty': 1, 'price': 1., 'gross_gold': 1, 'fee_gold': 1}]) < 0
    assert m._market_quote_quality(buy, []) == 0


def test_currency_change_scales_order_reference_as_well_as_price():
    bank = m._default_world_bank()
    bank.update(issued_total=100, treasury=100)
    market = m._default_world_market()
    market['orders'] = [{'price': 1.5, 'reference_price': 1.2, 'side': 'BUY',
                         'resource': 'food', 'country': '甲', 'qty': 5}]
    m._redenominate_currency(bank, {}, market, factor=10)
    assert market['orders'][0]['price'] == 15
    assert market['orders'][0]['reference_price'] == 12
    assert m._currency_audit({}, bank, raise_on_error=True)['gap'] == 0
