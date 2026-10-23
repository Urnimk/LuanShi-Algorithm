"""V9 有界軍備子策略：估算可持續目標、調整冷卻、五年後回顧。"""
from war_strategy import record
TARGETS = (.18, .25, .30, .36, .42, .48)
STEP = .03
COOLDOWN = 5


def phase(c):
    remaining = max(0, int(c.get('season_years_remaining', 500)))
    return '時間:結算前10年' if remaining <= 10 else '時間:爭冠前50年' if remaining <= 50 else '時間:中程' if remaining <= 200 else '時間:長期'


def state(c):
    pop = max(1,c.get('pop_total',1));food=c.get('food',0)/max(1,pop+c.get('soldiers',0))
    return (phase(c),'糧荒' if food<3 else '偏緊' if food<6 else '安全',
            min(2,int(float(c.get('battle_threat_ratio',0)))),
            min(range(len(TARGETS)),key=lambda i:abs(TARGETS[i]-c.get('military_target_ratio',.3))),
            '可追' if c.get('champion_gap_ratio',1)<=.25 else '落後')


def candidates(c):
    pop=max(1,int(c.get('pop_total',1)));soldiers=max(0,int(c.get('soldiers',0)))
    years=max(1,min(30,int(c.get('season_years_remaining',500))))
    battle=c.get('battle_readiness') or []
    if battle:years=min(years,max(1,int(c.get('battle_starts_in',5))))
    growth_cap=max(3,min(60,int(pop*.012)))
    food=max(0,c.get('food',0));metal=max(0,c.get('metal',0))
    current=c.get('military_target_ratio',.3)
    contender=int(c.get('world_rank',999) or 999)<=10 and c.get('champion_gap_ratio',1)<.5 and c.get('season_years_remaining',500)<=50
    threat=float(c.get('battle_threat_ratio',0));result=[]
    for i,target in enumerate(TARGETS):
        step_target=max(.12,min(.5,current+max(-STEP,min(STEP,target-current))))
        achievable=min(pop//2,int(pop*step_target),soldiers+growth_cap*years,int(soldiers+metal/8))
        farmers=pop-achievable
        # 保守估算：只用現有庫存與可辨認農工生產，不把戰利品當保證收益。
        food_workers=float((c.get('adaptive_worker_shares') or {}).get('food',.5)) if isinstance(c.get('adaptive_worker_shares'),dict) else .5
        annual_food=pop+achievable+(achievable*.5 if battle else 0)
        production=farmers*max(.35,min(.8,food_workers))*6 * .8  # 現有每工6糧，保守折算八成
        net_food=food+(production-annual_food)*years
        metal_need=max(0,achievable-soldiers)*8+achievable*(1.25 if battle else .12)*years
        reserve=net_food/max(1,annual_food)
        score=(achievable/max(1,pop))*(3 if contender else 1.0)
        score+=min(1.5,threat)*achievable/max(1,pop)*2
        score+=farmers/pop*(.6 if not contender and not battle else .15)
        score-=max(0,3-reserve)*.8+max(0,metal_need-metal)/max(100,metal)*.4
        score-=abs(target-current)*.25
        result.append(dict(index=i,target=target,score=round(score,4),projected_power=achievable*50,
                           food_years=round(reserve,1),training_years=years))
    return result


def plan(agent,c,year):
    if year<int(c.get('military_plan_after',0)):
        return False
    options=candidates(c);s=state(c);policy=agent.military_policy
    key=policy.state_key(s)
    if key not in policy.q_table:
        policy.q_table[key]=[x['score'] for x in options]
    food_years=c.get('food',0)/max(1,c.get('pop_total',1)+c.get('soldiers',0))
    best=max(x['score'] for x in options)
    valid=[x['index'] for x in options if x['score']>=best-.6]
    advice=(getattr(agent,'_last_library_advice',None) or {}).get('military_bias')
    choice=policy.choose(s,valid,advice=advice) if advice else policy.choose(s,valid)
    selected=options[choice]
    old=float(c.get('military_target_ratio',.3));delta=max(-STEP,min(STEP,selected['target']-old))
    new=round(max(.12,min(.5,old+delta)),3)
    c['military_target_ratio']=new;c['military_plan_after']=year+COOLDOWN
    agent.military_pending=dict(state=list(s),action=choice,due=year+5,
                               generation=c.get('country_generation'),power=c.get('power',0),pop=c.get('pop_total',0),
                               food_years=food_years,threat=c.get('battle_threat_ratio',0))
    reason=(f'軍備目標 {old:.0%}→{new:.0%}；{phase(c)}；與首名差距 {c.get("champion_gap_ratio",1):.0%}；'
            f'{selected["training_years"]}年可達戰力約{selected["projected_power"]}；預估淨糧續航{selected["food_years"]}年（估計非保證）')
    c['military_plan_reason']=reason;record(c,year,'軍備規劃',reason)
    return True


def settle(agent,c,year):
    p=getattr(agent,'military_pending',None)
    if not p:return
    dead=not c.get('is_alive') or c.get('country_generation')!=p.get('generation')
    if year<p['due'] and not dead:return
    reward=-5 if dead else ((c.get('power',0)-p['power'])/max(50,p['power'])+
                          (c.get('pop_total',0)-p['pop'])/max(10,p['pop'])+
                          (c.get('food',0)/max(1,c.get('pop_total',1)+c.get('soldiers',0))-p['food_years'])*.1)
    agent.military_policy.learn(p['state'],p['action'],max(-5,min(5,reward)),state(c),list(range(len(TARGETS))),success=not dead)
    c['military_review_reward']=round(reward,3);agent.military_pending=None


def birth_worthwhile(c):
    pop=max(1,int(c.get('pop_total',1)));room=int(c.get('houses',0))*10-pop
    if int(c.get('world_rank', 999)) <= 10 and int(c.get('season_years_remaining', 500)) <= 3:
        return False
    return int(c.get('birth_policy_turns',0))<=1 and room>=max(2,min(20,int(pop*.01))) and c.get('food',0)>=(pop+c.get('soldiers',0))*4
