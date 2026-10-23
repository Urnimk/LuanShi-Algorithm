"""Alliance titles earned during membership, independent of lifetime titles.
Only constant-size counters are added. Old evidence is a lower bound when
former membership cannot be reconstructed. No AI or random calls.
"""
import re


def parse_round(record):
    match=re.match(r'^R(\d+)__',str(record))
    return int(match.group(1)) if match else None


def _membership(country,name,joined,epoch,kind,year,round_years,calendar_known):
    field='coalition_trophies' if kind=='coalition' else 'alliance_trophies'
    token=[name,joined,epoch]
    current=country.get(field)
    if isinstance(current,dict) and current.get('membership')==token:return current
    records=country.get('championship_records',[]) or []
    valid_join=joined is not None and 0<=int(joined)<=year
    observed=set();complete=bool(valid_join and calendar_known)
    for record in records:
        r=parse_round(record)
        if r is None:complete=False;continue
        # Original fixed calendar: season R ends in year R * YEARS_PER_SEASON.
        if valid_join and calendar_known and int(joined)<=r*round_years<=year:
            observed.add(r)
    current=country[field]=dict(membership=token,count=len(observed),complete=complete,
                                last_round=max(observed,default=0),since=year)
    return current


def _sync_entity(name,members,countries,meta,kind,year,round_years,calendar_known):
    meta.setdefault('observed_since',int(year))
    created=meta.get('created_turn')
    epoch=created if created is not None else meta.get('observed_since',year)
    member_counts={}
    for key in members:
        c=countries.get(key)
        if not c or not c.get('is_alive',True):continue
        joined=created if kind=='coalition' else c.get('alliance_join_turn')
        if kind=='alliance' and c.get('current_alliance')!=name:continue
        state=_membership(c,name,joined,epoch,kind,year,round_years,calendar_known)
        member_counts[key]=dict(count=int(state['count']),complete=bool(state['complete']))
    tally=meta.get('honors')
    if not isinstance(tally,dict):
        rounds=set()
        if calendar_known:
            for key in member_counts:
                c=countries[key]
                joined=created if kind=='coalition' else c.get('alliance_join_turn')
                if joined is None or not 0<=int(joined)<=year:continue
                for record in c.get('championship_records',[]) or []:
                    r=parse_round(record)
                    if r is not None and int(joined)<=r*round_years<=year:rounds.add(r)
        tally=meta['honors']=dict(count=len(rounds),complete=created is not None and int(created)>=year,
                                 since=year,last_round=max(rounds,default=0))
    # A single original season can establish only one alliance title even when
    # old duplicate settlements appear in more than one member's records.
    # Thereafter increment on real settlements; departures never subtract.
    return tally,member_counts


def synchronize(countries,alliances,metadata,coalitions,year,season_round,season_start,round_years):
    calendar_known=int(season_start)==(int(season_round)-1)*int(round_years)
    for name,members in alliances.items():
        meta=metadata.setdefault(name,dict(created_turn=None,observed_since=year))
        _sync_entity(name,members,countries,meta,'alliance',year,round_years,calendar_known)
    for name,meta in coalitions.items():
        _sync_entity(name,meta.get('members',[]),countries,meta,'coalition',year,round_years,calendar_known)


def record_champion(key,countries,alliances,metadata,coalitions,year,season_round,season_start,round_years):
    synchronize(countries,alliances,metadata,coalitions,year,season_round,season_start,round_years)
    entities=[]
    for name,members in alliances.items():
        if key in members:entities.append((metadata[name],'alliance_trophies'))
    for name,meta in coalitions.items():
        if key in meta.get('members',[]):entities.append((meta,'coalition_trophies'))
    for meta,field in entities:
        state=countries[key][field];tally=meta['honors']
        if int(state.get('last_round',0))<season_round:
            state['count']+=1;state['last_round']=int(season_round)
            # Only one champion per season; do not count a repeated settlement twice.
            if int(tally.get('last_round',0))<season_round:
                tally['count']+=1;tally['last_round']=int(season_round)


def snapshot(name,members,countries,meta,kind,year):
    created=meta.get('created_turn')
    age=max(0,int(year)-int(created if created is not None else meta.get('observed_since',year)))
    honors=meta.get('honors',{})
    field='coalition_trophies' if kind=='coalition' else 'alliance_trophies'
    counts={}
    for k in members:
        if k not in countries or not countries[k].get('is_alive',True):continue
        state=countries[k].get(field,{})
        if state.get('membership',[None])[0]!=name:continue
        counts[k]=dict(count=int(state.get('count',0)),complete=bool(state.get('complete',False)))
    total=int(honors.get('count',0))
    return dict(championship_count=total,championships_complete=bool(honors.get('complete',False)),
                championship_text=format_count(total,bool(honors.get('complete',False))),
                member_championships=counts,age_years=age,age_is_exact=created is not None,
                age_text_short=('' if created is not None else '至少 ')+f'{age:,} 年')


def format_count(count,complete=True):
    return ('' if complete else '至少 ')+f'{int(count):,}'


def member_text(details,key):
    info=(details.get('member_championships') or {}).get(key)
    if info is None:return '待更新'
    return format_count(info['count'],info.get('complete',False))
