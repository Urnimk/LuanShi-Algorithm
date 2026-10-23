"""V9 戰線調度。所有變更沿用引擎人口、戰爭索引與盟約資料；不改排名。"""
MAX_COMBAT_YEARS = 30
OCCUPATION_YEARS = 3
CAPTURE_SOLDIER_RATIO = .25
CAPTURE_FORT = 25
EMPTY_CITY_MAX_YEARS = 10
REVIEW_INTERVAL = 5
REINFORCEMENT_TRAVEL = 2


def protected(c, year):
    return max(int(c.get('newbie_protection_until_turn', 0) or 0),
               int(c.get('rebuild_protection_until_turn', 0) or 0)) > year


def record(c, year, kind, reason):
    c['last_strategy_reason'] = reason
    events = c.setdefault('strategy_events', [])
    events.append(dict(year=year, generation=c.get('country_generation'), kind=kind, reason=reason))
    del events[:-100]


def safe_aid_amount(c, resource, rate):
    pop = max(1, int(c.get('pop_total', 1)))
    soldiers = max(0, int(c.get('soldiers', 0)))
    reserve = {'food': (pop + soldiers) * 6, 'metal': max(60, soldiers * 6.25),
               'wood': max(60, pop * .5), 'gold': 180}.get(resource, 0)
    stock = max(0, int(c.get(resource, 0)))
    return max(0, min(int(stock * rate), int(stock - reserve)))


def front_weights(key, wars):
    weights = {}
    for wid, w in wars.items():
        if key in w.get('defender_members', []):
            weights[str(wid)] = 3.0 if w.get('defender_anchor') == key else 2.0
        elif key in w.get('attacker_members', []):
            weights[str(wid)] = 1.0
        elif any(item.get('country') == key for item in w.get('reinforcements', [])):
            # 行軍中的部隊也占用同一兵源池，但抵達前不算入目的戰場戰力。
            weights[str(wid)] = 2.0
    return weights


def front_share(key, war_id, wars):
    weights = front_weights(key, wars)
    return weights.get(str(war_id), 0.0) / max(1.0, sum(weights.values()))


def projected_front_share(key, wars, defending=False):
    # 尚未開戰的保守估算：防禦以盟友防線權重2，本土實際可獲權重3。
    new_weight = 2.0 if defending else 1.0
    return new_weight / (new_weight + sum(front_weights(key, wars).values()))


def side_force(members, wid, wars, countries):
    return sum(int(max(0, countries.get(k, {}).get('soldiers', 0)) * front_share(k, wid, wars))
               for k in members if countries.get(k, {}).get('is_alive', False))


def capital_status(war, countries, year, attacker_force, defender_force):
    """僅目標國本身的守軍／城防及持續佔領決定陷落，拒和不呼叫本函式。"""
    key = war.get('defender_anchor')
    c = countries.get(key, {})
    if not c.get('is_alive', False) or protected(c, year):
        return False, '目標已失效或受保護'
    initial = max(1, int(war.setdefault('target_initial_soldiers', max(1, c.get('soldiers', 0)))))
    own = max(0, int(c.get('soldiers', 0)))
    fort = float(c.get('fortification', 0))
    if attacker_force <= 0:
        war['target_occupation'] = 0
        return False, '攻方無有效兵力'
    # 有效援軍可防止空城單靠本國零兵就被自動攻陷。
    uncovered = defender_force < attacker_force
    empty = own == 0 and uncovered
    war['target_empty_years'] = int(war.get('target_empty_years', 0)) + 1 if empty else 0
    breach = own <= initial * CAPTURE_SOLDIER_RATIO and fort < CAPTURE_FORT and attacker_force > defender_force * 1.2
    war['target_occupation'] = min(OCCUPATION_YEARS, int(war.get('target_occupation', 0)) + 1) if breach else 0
    if empty and fort <= 0:
        return True, '目標國無守軍、城防歸零且援軍無法阻止佔領'
    if war['target_empty_years'] >= EMPTY_CITY_MAX_YEARS:
        return True, f'目標國連續{EMPTY_CITY_MAX_YEARS}年無守軍且援軍無法解除圍城'
    if war['target_occupation'] >= OCCUPATION_YEARS:
        return True, f'目標國低守軍、低城防，敵方連續{OCCUPATION_YEARS}年完成佔領'
    return False, '繼續抵抗'


def prepare_year(e, countries, alliances, agents, wars, year, note_loss):
    """保護校正、戰線撤出與增援。每年一次，增援須旅行並重新確認盟約與兵源。"""
    for wid, w in wars.items():
        for side in ('attacker', 'defender'):
            members = w.get(side + '_members', [])
            removed = [k for k in members if k in countries and protected(countries[k], year)]
            if removed:
                w[side + '_members'] = [k for k in members if k not in removed]
                for k in removed:
                    record(countries[k], year, '保護期撤離', f'{wid}：保護期間僅提供安全存量以外的經濟支援')
                    e.print(f'🛡️ [保護期撤離] 第{year}年【{countries[k].get("display_name",k)}】退出 {wid} 軍事名單。')
            anchor = countries.get(w.get(side + '_anchor'), {})
            if anchor and (protected(anchor, year) or not anchor.get('is_alive', False)):
                w['v9_invalid_anchor'] = True
        target = countries.get(w.get('defender_anchor'), {})
        w.setdefault('target_initial_soldiers', max(1, int(target.get('soldiers', 0))))
    e._war_index_rebuild(wars)
    # 本土被威脅時，評估撤出次要進攻。不是強制所有盟員跟隨撤出。
    for key, c in countries.items():
        if not c.get('is_alive') or year < int(c.get('front_redeploy_after', 0)):
            continue
        home = [(wid, w) for wid, w in wars.items() if w.get('defender_anchor') == key and key in w.get('defender_members', [])]
        if not home:
            continue
        danger = max(side_force(w.get('attacker_members', []), wid, wars, countries) /
                     max(1, side_force(w.get('defender_members', []), wid, wars, countries)) for wid, w in home)
        bond = float((c.get('alliance_confidence') or {}).get('comradeship', 0))
        benefit = min(100, danger * 35) + min(25, c.get('war_exhaustion', 0) * .25)
        cost = 35 + min(20, bond * .2)
        if benefit <= cost + 10:
            continue
        for wid, w in list(wars.items()):
            if key not in w.get('attacker_members', []):
                continue
            loss = min(20, int(c.get('soldiers', 0) * .02)) if w.get('phase') != 'MUSTERING' else 0
            if loss:
                c['soldiers'] -= loss; c['pop_total'] -= loss
                note_loss(key, loss, '撤離次要戰線傷亡')
            for ally in w['attacker_members']:
                if ally != key and ally in countries:
                    e.confidence.record_event(countries[ally], year, '盟友撤軍保衛本土，戰線壓力增加', -2, -1)
            w['attacker_members'].remove(key)
            w.setdefault('withdrawn_members', {})[key] = year
            c['war_exhaustion'] = min(100, c.get('war_exhaustion', 0) + 2)
            c['front_redeploy_after'] = year + 10
            c['power'] = e.calculate_rts_power(c)
            reason = f'{wid} 撤軍轉保本土；生存收益 {benefit:.1f} > 撤退／盟約成本 {cost:.1f}；損失 {loss} 兵'
            record(c, year, '戰線調度', reason)
            e.print(f'↩️ [戰線調度] 第{year}年【{c.get("display_name",key)}】{reason}。')
            e._war_index_rebuild(wars)
    for wid, w in wars.items():
        if w.get('v9_invalid_anchor'):
            continue
        anchor = w.get('defender_anchor'); target = countries.get(anchor, {})
        ally = target.get('current_alliance', '')
        queue = w.setdefault('reinforcements', [])
        kept = []
        for item in queue:
            k = item['country']; c = countries.get(k, {})
            valid = (c.get('is_alive') and not protected(c, year) and k in alliances.get(ally, [])
                     and c.get('country_generation') == item.get('generation')
                     and k not in w.get('attacker_members', []) and k not in w.get('defender_members', []))
            if not valid:
                continue
            if item['arrival'] > year:
                kept.append(item); continue
            if e._war_country_can_join_new_war(k, wars):
                w['defender_members'].append(k)
                w['defender_initial_soldiers'] = int(w.get('defender_initial_soldiers', 0)) + int(c.get('soldiers', 0))
                record(c, year, '援軍抵達', f'{wid}：履行對 {target.get("display_name",anchor)} 的共同防禦')
                e.print(f'🛡️ [援軍抵達] 第{year}年【{c.get("display_name",k)}】加入 {wid}；兵源重新分配，不複製兵力。')
                e._war_index_rebuild(wars)
        w['reinforcements'] = kept
        if year < int(w.get('next_support_review', 0)):
            continue
        w['next_support_review'] = year + REVIEW_INTERVAL
        attack = side_force(w.get('attacker_members', []), wid, wars, countries)
        defense = side_force(w.get('defender_members', []), wid, wars, countries)
        if attack < defense * 1.15:
            continue
        pending = {x['country'] for x in kept}
        for k in alliances.get(ally, []):
            c = countries[k]
            if not c.get('is_alive') or k in pending or k in w.get('attacker_members', []) + w.get('defender_members', []):
                continue
            if protected(c, year):
                transferred = {}
                for res in ('food', 'metal', 'wood'):
                    amount = safe_aid_amount(c, res, .03)
                    if amount:
                        c[res] -= amount; target[res] = target.get(res, 0) + amount; transferred[res] = amount
                if transferred:
                    e.confidence.record_aid(c, target, transferred, year)
                    e.print(f'📦 [保護期援助] 第{year}年【{c.get("display_name",k)}】以安全餘糧與物資支援 {wid}：{transferred}。')
                continue
            # 已在敵方另一場戰爭或待命佔滿戰線時，不建立相互矛盾的援軍。
            enemies = set(w.get('attacker_members', []))
            conflicting = any(k in other.get('attacker_members', []) and anchor in other.get('defender_members', []) or
                              k in other.get('defender_members', []) and anchor in other.get('attacker_members', [])
                              for other in wars.values())
            reserved = sum(any(x['country'] == k for x in other.get('reinforcements', [])) for other in wars.values())
            if conflicting or e._war_country_war_count(k, wars) + reserved >= e.WARSTATE['MAX_ACTIVE_WARS_PER_COUNTRY']:
                continue
            support, reason = e._alliance_member_defense_support(k, anchor, w['attacker_anchor'], countries, alliances, agents, wars, year)
            if support:
                w['reinforcements'].append(dict(country=k, generation=c.get('country_generation'), arrival=year+REINFORCEMENT_TRAVEL))
                record(c, year, '增援出發', f'{wid}：{reason}；{REINFORCEMENT_TRAVEL} 年後抵達')
                e.print(f'📯 [增援出發] 第{year}年【{c.get("display_name",k)}】支援 {wid}，{reason}。')
            else:
                record(c, year, '增援評估', f'{wid}：{reason}')


def describe(e, countries, wars, year):
    for key, c in countries.items():
        fronts = []
        for wid in e._war_country_active_war_ids(key, wars):
            w = wars[wid]
            side = 'defender' if key in w.get('defender_members', []) else 'attacker'
            enemy_side = 'attacker' if side == 'defender' else 'defender'
            own = side_force(w.get(side+'_members', []), wid, wars, countries)
            enemy = side_force(w.get(enemy_side+'_members', []), wid, wars, countries)
            committed = int(c.get('soldiers', 0) * front_share(key, wid, wars))
            supply = min(c.get('food',0)/max(1,c.get('pop_total',0)+c.get('soldiers',0)+committed*.5),
                         c.get('metal',0)/max(1,committed*1.25))
            fronts.append(dict(war=wid, side=side, committed=committed, friendly=own, enemy=enemy,
                               runway=round(supply,1), fort=c.get('fortification',0),
                               starts_in=max(0,int(w.get('combat_starts_turn',year))-year)))
        c['battle_readiness'] = fronts
        c['battle_readiness_text'] = '；'.join(f"{f['war']} 投入{f['committed']}兵／友{f['friendly']}:敵{f['enemy']}／庫存續航{f['runway']}年／城防{f['fort']}" for f in fronts) or '和平：無正式戰線'
        c['battle_threat_ratio'] = max((f['enemy']/max(1,f['friendly']) for f in fronts),default=0)
        c['battle_starts_in'] = min((f['starts_in'] for f in fronts),default=999)
