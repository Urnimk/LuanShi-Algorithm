"""經驗面板只讀所選國家的目前狀態與 Q 值。"""
import json
from experience_view import render_current_q


def test_current_state_only_and_full_saved_q_table():
    current = json.dumps([1, 2], separators=(',', ':'))
    old = json.dumps([0, 0], separators=(',', ':'))
    saved = {'policies': {'strategic': {'q_table': {current: [2.5, -1], old: [99, 99]},
                                         'visit_counts': {current: 7, old: 40}}}}
    report = render_current_q('甲', (1, 2), saved, {0: '貿易', 1: '建設'})
    assert '目前狀態：1｜2' in report and '此狀態造訪：7 次' in report
    assert '貿易：+2.5000' in report and '建設：-1.0000' in report
    assert '99.0000' not in report


def test_new_state_has_zero_q_without_mutating_agent():
    saved = {'policies': {'strategic': {'q_table': {}}}}
    report = render_current_q('乙', (2,), saved, {0: '貿易'})
    assert '尚無已存檔的 Q 值' in report and '貿易：+0.0000' in report
    assert saved['policies']['strategic']['q_table'] == {}
