"""Individual alliance confidence; deterministic observations, additive JSON fields.

Benefit, trust and comradeship are separate. Tenure alone cannot create a
life-and-death pact. Events observe real transfers and effective battle forces.
No random calls, Q-state changes or combat/resource formula changes.
"""
import math

REVIEW_YEARS = 10
LOW_CONFIDENCE = 35
LOW_REVIEWS = 3
MIN_TENURE = 40
NOTICE_YEARS = 10
COOLDOWN_YEARS = 30


def clamp(x, lo=0.0, hi=100.0):
    return max(lo, min(hi, x))


def num(c, key, default=0):
    value = c.get(key, default)
    return float(default if value is None else value)


def sync(c, year):
    """Use explicit old join dates, otherwise mark a lower-bound observation date."""
    name = c.get('current_alliance') or ''
    token = [name, c.get('alliance_join_turn')]
    s = c.get('alliance_confidence')
    if not isinstance(s, dict) or s.get('membership') != token:
        prior = s if isinstance(s, dict) else {}
        joined = c.get('alliance_join_turn')
        known = joined is not None and 0 <= int(joined) <= year
        s = c['alliance_confidence'] = dict(
            membership=token, joined=int(joined) if known else int(year),
            tenure_known=known, observed_since=int(year), confidence=60.0,
            benefit=60.0, trust=55.0, comradeship=0.0, low_reviews=0,
            combat_years=0, shared_victories=0, crises=0, aid_received=0.0,
            aid_given=0.0, breaches=0, samples=[], previous_members=[],
            cooldown_until=int(prior.get('cooldown_until', 0)),
            peaceful_exits=int(prior.get('peaceful_exits', 0)),
            pending=[], last_reason='新盟約，開始觀察',
            last_decision=prior.get('last_decision','觀察留盟利益') if not name else '觀察留盟利益')
    s['current_year'] = int(year)
    return s


JOURNAL_RETENTION_YEARS = 1000
_journal_state = {}


def prune_journal(path, year, force=False):
    """Keep exactly the current year and its previous 999 years; stream old files.

    Runtime cache avoids rescanning until the oldest retained row expires.
    Replacement is atomic; failed cleanup leaves the original intact.
    """
    if not path:
        return
    import json
    import os
    import tempfile
    path = os.path.abspath(os.fspath(path))
    year = int(year)
    cutoff = year - JOURNAL_RETENTION_YEARS + 1
    try:
        st = os.stat(path)
        stamp = (st.st_mtime_ns, st.st_size)
    except FileNotFoundError:
        _journal_state[path] = dict(year=year, due=year + JOURNAL_RETENTION_YEARS, stamp=None)
        return
    previous = _journal_state.get(path)
    if (not force and previous and previous['stamp'] == stamp
            and year >= previous['year'] and year < previous['due']):
        previous['year'] = year
        return
    temp = None
    try:
        oldest = None
        with tempfile.NamedTemporaryFile(mode='wb', dir=os.path.dirname(path),
                                         prefix='.confidence-', suffix='.tmp', delete=False) as dst:
            temp = dst.name
            with open(path, 'rb') as src:
                for line in src:
                    try:
                        row = json.loads(line)
                        row_year = row.get('year')
                        if isinstance(row_year, bool) or not isinstance(row_year, int):
                            continue
                    except (ValueError, TypeError, AttributeError, UnicodeError):
                        continue
                    if cutoff <= row_year <= year:
                        dst.write(line.rstrip(b'\r\n') + b'\n')
                        oldest = row_year if oldest is None else min(oldest, row_year)
        os.replace(temp, path)
        temp = None
        st = os.stat(path)
        _journal_state[path] = dict(year=year, due=(oldest + JOURNAL_RETENTION_YEARS if oldest is not None else year + JOURNAL_RETENTION_YEARS),
                                    stamp=(st.st_mtime_ns, st.st_size))
    finally:
        if temp is not None:
            try:
                os.unlink(temp)
            except OSError:
                pass


def journal(path, event):
    """Detailed causal archive limited to the latest 1000 simulation years."""
    if path:
        import json
        import os
        year = int(event['year'])
        prune_journal(path, year)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(event, ensure_ascii=False, separators=(',', ':')) + '\n')
        absolute = os.path.abspath(os.fspath(path))
        state = _journal_state.get(absolute)
        if state:
            st = os.stat(path)
            state['stamp'] = (st.st_mtime_ns, st.st_size)
            state['due'] = min(state['due'], year + JOURNAL_RETENTION_YEARS)


def record_event(c, year, reason, trust=0, bond=0, **facts):
    if not c.get('current_alliance'):
        return
    s = sync(c, year)
    s['trust'] = round(clamp(s['trust'] + trust), 3)
    s['comradeship'] = round(clamp(s['comradeship'] + bond), 3)
    # Applied at most once by the next review. This is not an unbounded history.
    s['pending'].append(dict(year=int(year), reason=reason, trust=trust, bond=bond, **facts))


def record_aid(donor, recipient, transfers, year):
    if not donor.get('current_alliance') or donor.get('current_alliance') != recipient.get('current_alliance'):
        return
    amount = sum(max(0, float(v or 0)) for v in transfers.values())
    if amount <= 0:
        return
    ds, rs = sync(donor, year), sync(recipient, year)
    ds['aid_given'] += amount
    rs['aid_received'] += amount
    # Tiny repeated transfers cannot buy arbitrary trust/bond: proportional, capped.
    scale = amount / max(100, num(recipient, 'pop_total'))
    gain = min(4, 4 * scale)
    record_event(recipient, year, '盟友提供實際資源援助', gain, gain * .5)
    record_event(donor, year, '實際支援盟友', 0, gain * .25)


def record_refusal(countries, defender, ballot, year):
    refused = [k for k, vote in ballot.get('votes', {}).items()
               if k != defender and vote == '拒絕']
    if not refused or defender not in countries:
        return
    c = countries[defender]
    s = sync(c, year)
    # Cannot join because all fronts are full is not the same as deliberate abandonment.
    severe = [k for k in refused if ballot.get('reasons', {}).get(k) != '戰線已滿']
    if severe:
        s['breaches'] += 1
    penalty = min(24, len(severe) * 8 + (len(refused)-len(severe)) * 2)
    record_event(c, year, '共同防禦請求未獲部分盟友支援', -penalty, -penalty * .5,
                 refused=refused, reasons=ballot.get('reasons', {}))


def record_battle(countries, war, year, result, before):
    """One real combat year per country; use force deltas, never ballots as troops."""
    for side, other, winner in (('attacker', 'defender', 'ATTACKER'), ('defender', 'attacker', 'DEFENDER')):
        contribution = war.get(side + '_troop_contribution', {}) or {}
        old = before.get(side, {})
        fighting = [k for k, v in contribution.items() if v > old.get(k, 0) and k in countries]
        groups = {}
        for k in fighting:
            name = countries[k].get('current_alliance')
            if name:
                groups.setdefault(name, []).append(k)
        for name, members in groups.items():
            if len(members) < 2:
                continue
            # Danger is measured from forces before battle, avoiding false crises
            # caused by the enemy casualties from this same victorious round.
            danger = before.get(other + '_power', 0) > before.get(side + '_power', 0) * 1.3
            for k in members:
                c = countries[k]; s = sync(c, year)
                if s.get('last_combat_year') != year:
                    s['combat_years'] += 1; s['last_combat_year'] = year
                    record_event(c, year, '盟友實際共同作戰', .15, .35)
                rescue_token = [war.get('attacker_anchor'), war.get('started_turn', year)]
                if side == 'defender' and k == war.get('defender_anchor') and s.get('last_rescue_war') != rescue_token:
                    s['last_rescue_war'] = rescue_token
                    record_event(c, year, '遭受攻擊時盟友實際出兵', 7, 4)
                if danger and s.get('last_crisis_year', -10000) <= year - 20:
                    s['crises'] += 1; s['last_crisis_year'] = year
                    record_event(c, year, '共同抵禦優勢強敵', 3, 5)
        # Outcomes use cumulative real troop contributions so an exhausted veteran
        # does not lose credit merely because its last round has no usable soldiers.
        if result.get('ended') and result.get('winner'):
            veterans = {}
            for k, v in contribution.items():
                if v > 0 and k in countries and countries[k].get('current_alliance'):
                    veterans.setdefault(countries[k]['current_alliance'], []).append(k)
            for members in veterans.values():
                if len(members) < 2:
                    continue
                for k in members:
                    c = countries[k]; s = sync(c, year)
                    won = result['winner'] == winner
                    if won: s['shared_victories'] += 1
                    record_event(c, year, '聯盟共同作戰獲勝' if won else '共同戰敗，檢視長期收益',
                                 4 if won else -3, 4 if won else .5)


def context(countries, alliances, wars):
    alive = {k: c for k, c in countries.items() if c.get('is_alive', True)}
    order = sorted(alive, key=lambda k: (-num(alive[k], 'power'), k))
    ranks = {k: i+1 for i, k in enumerate(order)}
    fronts = {k: set() for k in alive}; enemies = {k: set() for k in alive}
    for wid, w in wars.items():
        for a, b in (('attacker', 'defender'), ('defender', 'attacker')):
            side = set(w.get(a+'_members') or []) & alive.keys()
            other = set(w.get(b+'_members') or []) & alive.keys()
            for k in side:
                fronts[k].add(wid); enemies[k].update(other)
    members = {n: [k for k in ms if k in alive] for n, ms in alliances.items()}
    powers = {n: sum(num(countries[k], 'power') for k in ms) for n, ms in members.items()}
    ranked = sorted(powers, key=lambda n: (-powers[n], n))
    return dict(alive=alive, ranks=ranks, fronts=fronts, enemies=enemies,
                members=members, powers=powers, alliance_ranks={n: i+1 for i,n in enumerate(ranked)})


def sync_metadata(countries, alliances, metadata, year):
    """Called after membership cleanup and again before snapshot export."""
    for name, ms in alliances.items():
        joins = [int(countries[k]['alliance_join_turn']) for k in ms
                 if countries[k].get('alliance_join_turn') is not None
                 and 0 <= int(countries[k]['alliance_join_turn']) <= year]
        meta = metadata.setdefault(name, dict(created_turn=None, observed_since=min(joins+[year])))
        for k in ms:
            c = countries[k]; c['current_alliance'] = name
            sync(c, year)
    for c in countries.values():
        if not c.get('current_alliance'):
            sync(c, year)
    # Ended alliances' metadata stays in the save as a historical record.


def register_alliance(metadata, name, year):
    metadata[name] = dict(created_turn=int(year), observed_since=int(year))


def tenure_text(c, year, alliance=None):
    s = c.get('alliance_confidence') or {}
    if alliance and c.get('current_alliance') != alliance:
        return '—'
    joined = s.get('joined', c.get('alliance_join_turn'))
    if joined is None:
        return '舊檔未記錄'
    years = max(0, int(year)-int(joined))
    return ('' if s.get('tenure_known', 'alliance_join_turn' in c) else '至少 ') + f'{years:,} 年'


def evaluate(key, name, countries, ctx, year):
    c = countries[key]; s = sync(c, year)
    members = ctx['members'].get(name, [])
    partners = [m for m in members if m != key]
    p = max(1, num(c, 'power')); total = max(p, ctx['powers'].get(name, p))
    strongest = max([num(countries[m], 'power') for m in partners] or [0])
    share = p / max(1, total)
    rank = ctx['ranks'][key]; world_size = len(ctx['alive'])
    if rank <= max(1, math.ceil(world_size*.05)):
        role = '霸權國'
    elif p < strongest*.4:
        role = '弱國'
    elif rank <= max(2, math.ceil(world_size*.25)):
        role = '強國'
    elif rank > world_size*.65:
        role = '弱國'
    else:
        role = '中型國'
    protection_weight = {'弱國':24, '中型國':17, '強國':8, '霸權國':5}[role]
    allies = sum(num(countries[m], 'power') for m in partners)
    threat = sum(num(countries[m], 'power') for m in ctx['enemies'][key])
    cover = min(1, allies/max(p, threat, 1))
    # Fear of a superior ally alone must never be a reason to betray it.
    benefit = 45 + protection_weight*cover
    reasons = [f'{role}：保護價值 +{protection_weight*cover:.1f}']
    hostility = sum(num(c.get('hostility') or {}, m) for m in partners)/max(1,len(partners))
    if hostility:
        cost = min(45, hostility*.45); benefit -= cost
        reasons.append(f'盟內利益衝突 -{cost:.1f}')
    samples = s['samples']
    sample = dict(year=year, power=p, population=num(c,'pop_total'),
                  resources=sum(num(c,r) for r in ('food','wood','metal')),
                  alliance_power=total, rank=ctx['alliance_ranks'].get(name,1),
                  core=strongest, war=bool(ctx['fronts'][key]),
                  received=s['aid_received'], given=s['aid_given'],
                  exhaustion=num(c,'war_exhaustion'))
    if not samples or samples[-1]['year'] != year:
        samples.append(sample)
    s['samples'] = samples[-7:]
    first = s['samples'][0]
    ready = year-first['year'] >= 20
    own_growth = (p-first['power'])/max(1000,first['power'])
    alliance_growth = (total-first['alliance_power'])/max(1000,first['alliance_power'])
    pop_growth = (sample['population']-first['population'])/max(1000,first['population'])
    stock_growth = (sample['resources']-first['resources'])/max(1000,first['resources'])
    growth = clamp(own_growth*15+pop_growth*10+stock_growth*5,-22,18) if ready else 0
    benefit += growth
    if ready:
        reasons.append(f'自身戰力／人口／資源長期收益 {growth:+.1f}')
        recent = s['samples'][-4:]
        at_war = any(t['war'] for t in recent)
        consistent_up = all(b['alliance_power']>a['alliance_power'] for a,b in zip(recent,recent[1:]))
        consistent_down = all(b['alliance_power']<a['alliance_power'] for a,b in zip(recent,recent[1:]))
        if at_war and (consistent_up or consistent_down):
            trend = clamp(alliance_growth*18,-18,15); benefit += trend
            reasons.append(f'戰時聯盟戰力持續趨勢 {trend:+.1f}')
        ranking = clamp((first['rank']-sample['rank'])*2,-12,10); benefit += ranking
        if ranking: reasons.append(f'聯盟國際排名變化 {ranking:+.1f}')
        if role == '弱國' and strongest < first['core']*.65:
            benefit -= 12; reasons.append('核心強國失去優勢 -12')
        # War burden applies when personal growth cannot compensate the cost.
        if sample['war'] and growth < 2:
            burden = min(24, num(c,'war_exhaustion')*.18 + max(0,-own_growth)*8)
            benefit -= burden; reasons.append(f'戰爭成本高於自身收益 -{burden:.1f}')
    received = max(0,s['aid_received']-first['received'])
    given = max(0,s['aid_given']-first['given'])
    aid = min(12, math.log1p(received)*1.2)
    burden = min(15, math.log1p(max(0,given-received))*.9) if growth < 3 else 0
    benefit += aid-burden
    if aid: reasons.append(f'實際獲援 +{aid:.1f}')
    if burden: reasons.append(f'單向援助成本未獲回報 -{burden:.1f}')
    if role in ('強國','霸權國'):
        leadership = 12*share; benefit += leadership
        reasons.append(f'維持主導地位 +{leadership:.1f}')
        # Opportunity cost is observed, never assume every strong country is constrained.
        if ready and share > .65 and growth <= 0 and given > received:
            benefit -= 16; reasons.append('主力長期付出且自身發展停滯 -16')
    dead = [k for k in s['previous_members'] if k not in members and not countries.get(k,{}).get('is_alive',False)]
    departed = [k for k in s['previous_members'] if k not in members and k not in dead]
    if dead:
        record_event(c,year,'盟友滅亡，保護能力受質疑',-min(25,len(dead)*12),-len(dead)*2, members=dead)
    if departed:
        record_event(c,year,'盟友離開，重新評估合作前景',-min(8,len(departed)*3),0,members=departed)
    s['previous_members'] = list(members)
    # Alone in a war is observational evidence, not proof everyone deliberately refused.
    shared = any(ctx['fronts'][key] & ctx['fronts'][m] for m in partners)
    if ctx['fronts'][key] and not shared:
        benefit -= 10; reasons.append('本國獨自承受戰線 -10')
    elif not ctx['fronts'][key] and role == '弱國' and own_growth > 0:
        benefit += 6; reasons.append('庇護下和平成長 +6')
    # Age can add only 8 bond points total, and requires actual shared experiences.
    age_bonus = min(8, max(0,year-s['joined'])/100) if s['combat_years'] >= 5 or s['aid_received'] > 0 else 0
    bond = clamp(s['comradeship']+age_bonus)
    benefit = clamp(benefit)
    target = .55*benefit + .30*s['trust'] + .15*bond
    # High bond cushions a short downturn, never imposes a permanent confidence floor.
    alpha = .16 if target < s['confidence'] and bond >= 60 else .30
    old = s['confidence']; new = round(clamp(old+alpha*(target-old)),1)
    if benefit < 25 and s['trust'] < 30:
        new = round(max(0,new-2),1)  # persistent existential conflict breaks inertia
    solo = clamp(48 + (18*share if role in ('強國','霸權國') else 0) - 25*min(1,threat/p))
    alternatives = [('保持中立／獨立', solo)]
    for other, ms in ctx['members'].items():
        if other == name or len(ms) >= 5 or any(m in ctx['enemies'][key] for m in ms): continue
        other_power = ctx['powers'][other]
        enmity = sum(num(c.get('hostility') or {},m) for m in ms)/max(1,len(ms))
        # An unaccepted application is discounted; no phantom promise of admission.
        expected = clamp(42+16*min(1,other_power/max(p,threat,1))-enmity*.3)
        alternatives.append((f'嘗試申請 {other}',expected))
    option,outside = max(alternatives,key=lambda t:t[1])
    comparable = .75*benefit+.25*s['trust']
    willing = (new>=85 and bond>=75 and s['trust']>=85 and benefit>=65
               and s['crises']>=2 and s['combat_years']>=20)
    s.update(confidence=new,benefit=round(benefit,1),bond_display=round(bond,1),role=role,
             outside_value=round(outside,1),stay_value=round(comparable,1),outside_option=option,
             review_year=year,observation_ready=ready,stand_together=willing)
    pending = s.pop('pending',[]); s['pending']=[]
    reasons += [e['reason'] for e in pending]
    reasons += [f'利益 {benefit:.1f}／信任 {s["trust"]:.1f}／情誼 {bond:.1f}',
                f'替代方案：{option} {outside:.1f}／留盟 {comparable:.1f}']
    s['last_reason']='；'.join(dict.fromkeys(reasons))
    return old,new,pending


def exit_allowed(c, year):
    s = c.get('alliance_confidence') or {}
    return (s.get('observation_ready',False) and s.get('confidence',60)<LOW_CONFIDENCE
            and s.get('low_reviews',0)>=LOW_REVIEWS and year-int(s.get('joined',year))>=MIN_TENURE
            and year>=int(s.get('cooldown_until',0)) and not s.get('stand_together',False)
            and s.get('outside_value',0)>=s.get('stay_value',100)+8)


def betrayal_allowed(c, year):
    s=c.get('alliance_confidence') or {}
    hostility=max([num(c.get('hostility') or {},k) for k in s.get('previous_members',[]) if k != c.get('country_key')] or [0])
    return exit_allowed(c,year) and s.get('trust',55)<25 and s.get('breaches',0)>=2 and hostility>=70


def stand_together(c):
    s = c.get('alliance_confidence') or {}
    return bool(c.get('current_alliance') and s.get('stand_together')
                and s.get('trust', 0) >= 85 and s.get('benefit', 0) >= 65
                and s.get('bond_display', 0) >= 75 and s.get('confidence', 0) >= 85)


def review(countries, alliances, wars, metadata, year, leave, log=print, audit_path=None):
    if year % REVIEW_YEARS:
        return
    ctx=context(countries,alliances,wars)
    for name, members in list(ctx['members'].items()):
        for key in members:
            c=countries[key]
            # Earlier member's exit may have dissolved this alliance this same review.
            if c.get('current_alliance') != name or name not in alliances: continue
            s=sync(c,year)
            if s.get('review_year')==year: continue
            old,new,pending=evaluate(key,name,countries,ctx,year)
            low = new<LOW_CONFIDENCE and s['outside_value']>=s['stay_value']+8
            s['low_reviews'] = s['low_reviews']+1 if low else 0
            event=dict(year=year,country=key,name=c.get('display_name',key),alliance=name,
                       old=old,confidence=new,benefit=s['benefit'],trust=s['trust'],
                       comradeship=s['bond_display'],reason=s['last_reason'],events=pending)
            # All score changes are durable; game.log remains a short on-screen window.
            if new != old or pending:
                journal(audit_path,event)
                log(f'🤝 [聯盟信心] 第{year}年【{event["name"]}】{name}：{old:.1f}→{new:.1f}；{s["last_reason"]}')
            notice=s.get('notice')
            if notice and not exit_allowed(c,year):
                s.pop('notice',None); s['last_decision']='信心／留盟利益回升，撤回退盟告知'
                log(f'🤝 [留盟]【{event["name"]}】{name}：{s["last_decision"]}')
                journal(audit_path,dict(year=year,country=key,alliance=name,decision=s['last_decision'],reason=s['last_reason']))
            elif notice and year>=notice['due']:
                shared_war=any(ctx['fronts'].get(k) for k in alliances.get(name,[]))
                emergency=s['benefit']<15 and s['trust']<20 and s['low_reviews']>=6
                if shared_war and not emergency:
                    s['last_decision']='告知期滿，等待共同戰事結束；重大存續危機可例外'
                    journal(audit_path,dict(year=year,country=key,alliance=name,decision=s['last_decision'],reason=s['last_reason']))
                elif leave(key,countries,alliances,reason='和平退盟：'+s['last_reason']):
                    s.pop('notice',None);s['cooldown_until']=year+COOLDOWN_YEARS
                    s['peaceful_exits']+=1;s['last_decision']=f'第{year}年和平退出 {name}'
                    journal(audit_path,dict(year=year,country=key,alliance=name,decision=s['last_decision'],reason=s['last_reason']))
                    ctx=context(countries,alliances,wars)
            elif not notice and exit_allowed(c,year):
                s['notice']=dict(alliance=name,due=year+NOTICE_YEARS)
                s['last_decision']=f'持續低信心，提出退盟告知；第{year+NOTICE_YEARS}年再確認'
                log(f'📜 [退盟告知]【{event["name"]}】{name}：{s["last_decision"]}；{s["last_reason"]}')
                journal(audit_path,dict(year=year,country=key,alliance=name,decision=s['last_decision'],reason=s['last_reason']))
            else:
                s['last_decision']='願與盟友共度存亡危機' if s['stand_together'] else '維持盟約，持續觀察自身利益'


def summary_fields(name, meta, year, rank, denominator):
    created=meta.get('created_turn')
    age=max(0,year-int(created if created is not None else meta.get('observed_since',year)))
    return dict(age_text=(f'{age:,} 年' if created is not None else f'至少 {age:,} 年（舊檔成立年未記錄）'),
                ranking_text=f'第 {rank} / {denominator} 名')
