"""Evidence-grounded whole-history and century-stage lessons, derived from book accounts.

No RNG, no simulation mutation, no assumption that a common action caused victory.
Successful histories provide positive priors; only explicit decline risks supply
negative priors. Fifteen-year episode scores never decide a book's direction.
"""
import math

MODEL=1
ENGINE_STRATEGY={'基礎建設投資':0,'調整產業配置':1,'戰時動員':2,'加固防線':3,'締結同盟':4,'發動戰爭':5,'小規模襲擾':6,'鼓勵生育':7,'增產補貼':7,'號召圍剿':8,'背叛背刺':9,'修復聲望':10,'裁軍休養':11,'長期軍備規劃':12}

def clamp(x,a,b):return max(a,min(b,x))
def progress(a,z):
    if not z.get('alive',True) or a['generation']!=z['generation']:return -1.
    growth=lambda k:clamp(math.log((z[k]+1)/(a[k]+1)),-1,1)
    # Consuming surplus stock is not a failure. Only the safety band contributes.
    food=(min(6,z['buffer'])-min(6,a['buffer']))/6
    value=.35*growth('power')+.25*growth('pop')+.2*food+.2*clamp((a['rank_pct']-z['rank_pct'])*3,-1,1)
    if z['buffer']<1:value-=.15
    return round(clamp(value,-1,1),4)

def strategy_mix(row):
    counts={}
    if row.get('strategies') and sum(row['strategies'].values())>=sum(row.get('actions',{}).values()):
        counts={int(k):v for k,v in row['strategies'].items() if v>0}
    else:
        for name,n in row.get('actions',{}).items():
            action=ENGINE_STRATEGY.get(name)
            if action is not None and n>0:counts[action]=counts.get(action,0)+n
    total=sum(counts.values())
    return {a:n/total for a,n in counts.items()} if total else {}

def valid_case(book,case):
    a=book['start'];x,y=case['before'],case['after'];lo=a['year']
    if x['generation']!=a['generation'] or y['year']>book['observed_end']:return False
    if x['year']<lo or x['year']==lo and not a.get('before_action'):return False
    if book.get('window')!='覆亡前最多300年' and case.get('season',book['season'])!=book['season']:return False
    return x['year']<y['year']<=book['published_year']

def build_path(book):
    a,z=book['start'],book['end'];failure=book['kind']=='失敗與興亡'
    full=bool(book.get('complete_season')) and z['year']-a['year']==500 and not book.get('gaps')
    result=dict(model=MODEL,direction='avoid' if failure else 'learn',eligible=False,stages=[],warnings=[],full=full,
                quality=0,reason='缺少完整路徑的分期帳或連續觀測，僅供閱讀。')
    if a['generation']!=z['generation'] or book.get('gaps') or z['year']>book['published_year']:return result
    if failure:
        if z['year']-a['year']<40:return result
        if z['alive'] and (book.get('decline_year') is None or z['power']>book.get('peak_power',z['power'])*.55):return result
        quality=.7 if not z['alive'] else .55
    else:
        if not full or not z['alive']:return result
        if book['kind']=='成長與復甦' and (z['power']<=a['power'] or z['pop']<=a['pop']):return result
        quality=(.7 if book['kind']=='冠軍成就' else .6)+.25*max(0,progress(a,z))
    pool={}
    for s in list(book.get('timeline',[]))+list(book.get('checkpoints',[]))+[a,z]:
        if s['generation']==a['generation'] and a['year']<=s['year']<=z['year']:pool[s['year']]=s
    points=sorted(pool.values(),key=lambda s:s['year'])
    base=a['year'] if book.get('window')=='覆亡前最多300年' else book.get('season_start',a['year'])
    for block,row in sorted(book.get('blocks',{}).items(),key=lambda x:int(x[0])):
        i=int(block);lo=max(a['year'],base+i*100);hi=min(z['year'],base+(i+1)*100)
        # No interpolation: a complete endpoint pair is needed for a stage's results.
        start=pool.get(lo);end=pool.get(hi)
        mix=strategy_mix(row)
        if not start or not end or hi-lo<30 or not mix:continue
        anchors=[s for s in points if lo<=s['year']<hi and s.get('alive',True)]
        score=progress(start,end)
        warning=[]
        if end['buffer']<3 and end['buffer']<start['buffer']:warning.append('存糧安全餘裕縮小')
        if end['fatigue']>=70:warning.append('戰爭疲勞偏高')
        if end['ratio']>start['ratio']+.1:warning.append('軍備擴張同時提高生產與補給負擔')
        if end['power']<start['power']*.8:warning.append('階段戰力下滑，須區分投入、戰損與政策效果')
        stage=dict(index=i,start=start,end=end,anchors=anchors,mix=mix,actions=row.get('actions',{}),score=score,
                   total=sum(row.get('actions',{}).values()),warnings=warning,
                   phase=anchors[0]['phase'] if anchors else start['phase'])
        result['stages'].append(stage);result['warnings'].extend(warning)
    result.update(eligible=bool(result['stages']),quality=min(1,quality),reason='確認衰亡後回看風險路徑，避免把補救行動一概判錯。' if failure else '依整屆成果選路徑，再依所在百年階段比較配置；短期負分不會反轉成功方向。')
    if not result['eligible']:result['reason']='缺少足夠的分期行動帳與精確起訖節點，只供閱讀，不編造AI路徑。'
    return result

def stage_risks(book,stage,current):
    """Penalize only identifiable discretionary risks, never every action of a loser."""
    a,z=stage['start'],stage['end'];mix=stage['mix'];penalties={};reasons=[]
    crisis=book.get('decline_year')
    pre_crisis=crisis is None or a['year']<crisis
    decline=(z['power']<a['power']*.85 or z['relative']<a['relative']*.8)
    # Wars launched before decline are discretionary; defensive mobilization is not.
    if pre_crisis and decline:
        for action in (5,6,8,9):
            if mix.get(action):penalties[action]=mix[action];reasons.append('衰退前的對外冒險與後續損失並存')
    if decline and z['ratio']<a['ratio']-.03 and mix.get(11) and current['buffer']>=3 and current['fatigue']<70:
        penalties[11]=mix[11];reasons.append('軍備收縮與實力下滑並存')
    if z['buffer']<3 and z['buffer']<a['buffer']-1 and z['ratio']>a['ratio']+.03 and not current['wars']:
        if mix.get(2):penalties[2]=mix[2];reasons.append('補給惡化時仍擴軍')
    # 0/1 are evaluated development choices; don't infer their failure from war losses.
    return penalties,list(dict.fromkeys(reasons))

def vectors(book,path,stage,current):
    i=path['stages'].index(stage);future=path['stages'][min(i+1,len(path['stages'])-1)]
    main={a:.8*stage['mix'].get(a,0)+.2*future['mix'].get(a,0) for a in set(stage['mix'])|set(future['mix'])}
    if path['direction']=='avoid':
        risks,reasons=stage_risks(book,stage,current)
        return {a:-(.65*main.get(a,0)+.25*v) for a,v in risks.items()},reasons
    # Whole-path outcome supplies the main weight. Stage payoff is secondary, never negative here.
    stage_weight=.25*(.5+.5*max(0,stage['score']))
    vector={a:.65*v+stage_weight*stage['mix'].get(a,0) for a,v in main.items()}
    warnings=list(stage['warnings'])
    if current['buffer']<1.5:
        for action in (2,5,6,8,9):vector.pop(action,None)
        warnings.append('本國存糧不足，不提高擴軍或主動冒險偏好')
    if current['protected']:
        for action in (5,6,8,9):vector.pop(action,None)
    return vector,warnings

def path_id(book,stage):return f"path:{book['country']}:{book['generation']}:{book['observed_start']}:{book['kind']}:{stage['index']}"

def lesson_text(book,path):
    rows=[];direction='衰亡反例' if path['direction']=='avoid' else '成功路徑'
    rows.append(f"主要｜{direction}：{book['start']['year']}—{book['end']['year']}年，排名第{book['start']['rank']}/{book['start']['count']}→"+(f"第{book['end']['rank']}/{book['end']['count']}" if book['end']['alive'] else '滅亡')+f"；戰力{book['start']['power']:,}→{book['end']['power']:,}、人口{book['start']['pop']:,}→{book['end']['pop']:,}。")
    rows.append(path['reason'])
    for stage in path['stages']:
        x,y=stage['start'],stage['end'];top=sorted(stage['actions'].items(),key=lambda x:(-x[1],x[0]))[:4]
        rows.append(f"其次｜第{x['year']+1}—{y['year']}年階段："+'、'.join(f'{k}{v}次' for k,v in top)+f"；人口{x['pop']:,}→{y['pop']:,}、戰力{x['power']:,}→{y['power']:,}、軍備目標{x['target']:.0%}→{y['target']:.0%}、每人存糧{x['buffer']:.1f}→{y['buffer']:.1f}。")
    warnings=list(dict.fromkeys(path['warnings']))
    rows.append('輔助｜代價與警訊：'+('；'.join(warnings) if warnings else '未在分期節點確認上述明顯風險；仍須核對年表與外部局勢。'))
    rows.append('成功書不因單次15年下降變成反例；衰亡書也不把防禦、動員與恢復人口等補救一概判錯。這些是有條件的觀測經驗，不是已證明的致勝或亡國因果。')
    return rows
