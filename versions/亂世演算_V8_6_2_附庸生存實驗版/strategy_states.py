"""戰略層 4×4×4×4 = 256 種狀態，使用可讀的中文標籤。"""

import json


LABELS = (
    ("安全:保護準備", "安全:安全", "安全:受威脅", "安全:危急"),
    ("軍事:安定", "軍事:戒備", "軍事:受威脅", "軍事:交戰"),
    ("發展:受限", "發展:起步", "發展:成長", "發展:強盛"),
    ("爭冠:落後", "爭冠:追趕", "爭冠:有望", "爭冠:領先"),
)


def _tier(value):
    return min(3, max(0, int(value)))


def strategic_state_256(state, country):
    """壓縮既有 13 欄；只動戰略 Q 的 key，不改動 Reward 或其他子策略。"""
    power, food, materials, liquidity, war, resilience, diplomacy, risk, need, world, phase, cash, rank = state
    food_level = {"FAMINE": 0, "LOW": 1, "SAFE": 2, "SURPLUS": 3}.get(food, 1)
    material_level = {"SHORT": 0, "OK": 2, "SURPLUS": 3}.get(materials, 1)
    liquidity_level = {"CRISIS": 0, "OK": 2, "AMPLE": 3}.get(liquidity, 1)
    resilience_level = {"FRAGILE": 0, "NORMAL": 2, "STABLE": 3}.get(resilience, 1)
    cash_level = {"NO_POLICY_BUDGET": 0, "FUNDED": 2, "CAPITAL_RICH": 3}.get(cash, 1)
    # 第一維不再用資源加權後的「生存吃緊」。舊公式在無貨幣模式及小國期
    # 幾乎永遠落在同一格，無法提供策略差異。新版改為真正的安全態勢：
    # 保護準備／安全／受威脅／危急，仍維持 4×4×4×4 = 256 狀態。
    current_turn = max(0, int(country.get("current_turn", 0) or 0))
    protection_until = max(
        int(country.get("newbie_protection_until_turn", 0) or 0),
        int(country.get("rebuild_protection_until_turn", 0) or 0),
    )
    protected = bool(country.get("is_alive", True) and protection_until > current_turn)
    security_score = float(
        country.get("security_risk_score", country.get("prewar_risk_score", 0)) or 0
    )
    if protected:
        security = 0
    elif war in ("WAR", "MULTI_FRONT") or security_score >= 70:
        security = 3
    elif war == "THREATENED" or security_score >= 35:
        security = 2
    else:
        security = 1

    war_level = {"PEACE": 0, "THREATENED": 1, "WAR": 3, "MULTI_FRONT": 3}.get(war, 0)
    risk_level = {"CALM": 0, "ALERT": 1, "HIGH": 2, "CRITICAL": 3}.get(risk, 0)
    need_level = {"LOW": 0, "MEDIUM": 1, "HIGH": 2}.get(need, 0)
    military = max(war_level, risk_level, need_level)
    if diplomacy == "STRONG_ALLIANCE" and military == 1 and war_level == 0:
        military = 0

    power_level = {"WEAK": 0, "PEER": 1, "STRONG": 2, "DOMINANT": 3}.get(power, 1)
    development = _tier(round(power_level * .60 + material_level * .18
                              + cash_level * .12 + resilience_level * .10))
    if materials == "SHORT" and liquidity == "CRISIS":
        development = min(development, 1)

    try:
        world_rank = int(country.get("world_rank", 999) or 999)
    except (ValueError, TypeError):
        world_rank = 999
    contest = 3 if world_rank == 1 else 2 if world_rank <= 3 else 1 if world_rank <= 10 else 0
    if rank == "TOP3":
        contest = max(contest, 2)
    elif rank == "TOP10":
        contest = max(contest, 1)
    # 本屆後段的前十名進入爭冠圈；世界已有霸主時，排名十名外仍維持落後。
    if phase == "LATE" and contest == 1 and world != "EMPIRE":
        contest = 2
    return (LABELS[0][security], LABELS[1][military], LABELS[2][development], LABELS[3][contest])


def readable_q_text(agents, action_labels):
    """每國輸出最多 24 個常見狀態；完整 256 狀態保留在原始 JSON。"""
    lines = ["戰略 Q 值觀察表｜狀態最多 256 種／國；數值越大代表當前估計越有利",
             "注意：Q 值是學習中的相對估計；未試過的動作會顯示為零。", ""]
    for name, agent in sorted(agents.items()):
        policy = agent.strategic_policy
        lines.append(f"國家：{name}｜已造訪狀態 {len(policy.q_table)}/256｜戰略決策 {policy.decision_count} 次")
        entries = sorted(policy.q_table.items(),
                         key=lambda item: (-int(policy.visit_counts.get(item[0], 0) or 0), item[0]))
        for key, values in entries[:24]:
            try:
                state = json.loads(key)
            except (ValueError, TypeError):
                state = [str(key)]
            visits = int(policy.visit_counts.get(key, 0) or 0)
            lines.append(f"  {'｜'.join(map(str, state))}｜造訪 {visits} 次")
            for idx, score in sorted(enumerate(values[:len(action_labels)]),
                                     key=lambda pair: (-float(pair[1]), pair[0])):
                lines.append(f"    {action_labels[idx]}：{float(score):+.4f}")
        if len(entries) > 24:
            lines.append(f"  其餘 {len(entries) - 24} 種狀態可查閱 rl_agents_q_tables.json")
        lines.append("")
    return "\n".join(lines)
