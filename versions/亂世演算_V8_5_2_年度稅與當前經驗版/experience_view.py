"""只顯示目前戰略狀態的 Q 值。"""
import json


def render_current_q(country_name, state, saved_agent, action_labels):
    """只顯示目前一個狀態；完整 JSON 保有未列於可讀前 24 名的 Q 值。"""
    if state is None:
        return f'{country_name}：目前沒有可計算的國家狀態。'
    agent = saved_agent if isinstance(saved_agent, dict) else {}
    strategic = (agent.get('policies') or {}).get('strategic') or {}
    key = json.dumps(list(state), ensure_ascii=False, separators=(',', ':'))
    values = strategic.get('q_table', agent.get('q_table', {})).get(key)
    visits = (strategic.get('visit_counts') or agent.get('visit_counts') or {}).get(key, 0)
    lines = [f'國家：{country_name}', f'目前狀態：{"｜".join(map(str, state))}'
            #  ,f'此狀態造訪：{int(visits or 0)} 次', ''
             ]
    if values is None:
        lines.append('這個狀態尚無已存檔的 Q 值；未學過的動作預設為 0。')
        values = [0.0] * len(action_labels)
    else:
        lines.append('目前狀態的動作 Q 值（高到低）：')
    lines.extend(f'  {action_labels[index]}：{float(values[index] if index < len(values) else 0):+.4f}'
                 for index in sorted(action_labels,
                                     key=lambda idx: -float(values[idx] if idx < len(values) else 0)))
    return '\n'.join(lines)
