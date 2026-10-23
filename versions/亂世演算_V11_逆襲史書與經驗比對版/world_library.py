"""Observed history and small, contextual policy advice. No fabricated historical backfill."""
import copy
import json
import math
import os
from collections import Counter

SCHEMA=2
EVIDENCE_EDITION=2
RULES='V10-library1:power=soldiers*50:refused-peace=capital-fall'
MAX_BOOKS=100
MAX_CASES=24
MAX_TRACK_POINTS=32
MAX_BOOK_POINTS=24
MAX_READINGS=200
MAX_COUNTRIES=200
REVIEW_YEARS=200
CASE_YEARS=15
CONSULT_COOLDOWN=25
BIAS_LIMIT=.18
ACTION_NAMES={0:'基礎建設投資',1:'產業配置',2:'戰時動員',3:'防禦工事',4:'結盟與共同防禦',5:'主動戰爭',6:'有限襲擾',7:'人口與生產政策',8:'反霸權圍剿',9:'背叛與機會主義',10:'聲望與外交修復',11:'短期裁軍休養',12:'長期軍備規劃'}
ENGINE_NAMES={0:'發動戰爭',1:'締結同盟',2:'號召圍剿',3:'基礎建設投資',4:'背叛背刺',5:'加固防線',6:'戰時動員',7:'調整產業配置',8:'市場貿易',9:'修復聲望',10:'小規模襲擾',11:'裁軍休養',12:'鼓勵生育',13:'增產補貼',16:'長期軍備規劃'}

def clamp(x,lo,hi):return max(lo,min(hi,x))
def num(c,k,default=0):
    try:
        value=float(c.get(k,default) or 0)
        return value if math.isfinite(value) else default
    except (TypeError,ValueError):return default

def phase(remaining):return '決勝期' if remaining<=50 else '後段' if remaining<=166 else '中段' if remaining<=333 else '前段'

def thin(points,limit):
    if len(points)<=limit:return points
    keep={0,len(points)-1,max(range(len(points)),key=lambda i:points[i]['power'])}
    keep.update(round(i*(len(points)-1)/(limit-1)) for i in range(limit))
    while len(keep)>limit:
        protected={0,len(points)-1,max(range(len(points)),key=lambda i:points[i]['power'])}
        candidates=sorted(keep-protected)
        keep.remove(min(candidates,key=lambda i:min(i-max(j for j in keep if j<i),min(j for j in keep if j>i)-i)))
    return [points[i] for i in sorted(keep)]

def snapshot(key,c,year,peers=None,remaining=None):
    peers=peers or {key:c}
    alive=sorted(((k,d) for k,d in peers.items() if d.get('is_alive',True)),key=lambda p:-num(p[1],'power'))
    rank=next((i+1 for i,(k,d) in enumerate(alive) if k==key),len(alive)+1)
    tied_rank=1+sum(num(d,'power')>num(c,'power') for _,d in alive)
    tied_count=sum(num(d,'power')==num(c,'power') for _,d in alive) if c.get('is_alive',True) else 0
    count=max(1,len(alive));top=max([num(d,'power') for _,d in alive]+[1]);pop=max(1,num(c,'pop_total',1))
    ally=c.get('current_alliance') or ''
    core=max([num(d,'power') for k,d in alive if k!=key and ally and d.get('current_alliance')==ally]+[0])
    gen=int(c.get('country_generation',c.get('gen',1)) or 1)
    role='霸權國' if rank==1 else '強國' if rank/count<=.2 or num(c,'power')/top>=.6 else '中型國' if rank/count<=.6 else '弱國'
    cs=c.get('alliance_confidence') or {}
    remaining=int(num(c,'season_years_remaining',500) if remaining is None else remaining)
    protection=max(num(c,'newbie_protection_until_turn'),num(c,'rebuild_protection_until_turn'))>year or num(c,'protection_remaining_years')>0
    return dict(key=key,name=str(c.get('display_name',key)),generation=gen,year=int(year),alive=bool(c.get('is_alive',True)),power=int(num(c,'power')),pop=int(num(c,'pop_total')),soldiers=int(num(c,'soldiers')),ratio=round(num(c,'soldiers')/pop,4),target=round(num(c,'military_target_ratio',.3),4),food=int(num(c,'food')),buffer=round(num(c,'food')/pop,3),fort=round(num(c,'fortification'),1),fatigue=round(num(c,'war_exhaustion'),1),stability=round(num(c,'political_stability',75),1),rank=rank,tied_rank=tied_rank,tied_count=tied_count,rank_pct=round(((tied_rank if c.get('is_alive',True) else rank)-1)/count,4),count=count,relative=round(num(c,'power')/top,4),role=role,alliance=str(ally),core_ratio=round(min(10,core/max(1,num(c,'power'))),3),trust=round(num(cs,'trust',55),1),wars=len(c.get('current_wars',[]) or []),protected=protection,remaining=max(0,remaining),phase=phase(remaining),event=str(c.get('last_event',''))[:180])

def outcome(before,after):
    if not after['alive'] or before['generation']!=after['generation']:return -1.0
    growth=lambda k:clamp(math.log((after[k]+1)/(before[k]+1)),-1,1)
    score=.35*growth('power')+.25*growth('pop')+.2*clamp((after['buffer']-before['buffer'])/8,-1,1)+.2*clamp((before['rank_pct']-after['rank_pct'])*3,-1,1)
    if after['buffer']<1:score-=.15
    return round(clamp(score,-1,1),4)

def similarity(a,b):
    # War, protection and seasonal time scale must match. A large army is not a substitute for safety.
    if a['phase']!=b['phase'] or min(2,a['wars'])!=min(2,b['wars']) or a['protected']!=b['protected']:return 0
    role_dist=abs(['弱國','中型國','強國','霸權國'].index(a['role'])-['弱國','中型國','強國','霸權國'].index(b['role']))
    if role_dist>1:return 0
    distances=[abs(a['ratio']-b['ratio'])/.5,abs(a['target']-b['target'])/.5,abs(min(a['buffer'],20)-min(b['buffer'],20))/20,abs(a['rank_pct']-b['rank_pct']),abs(a['fatigue']-b['fatigue'])/100,abs(a['fort']-b['fort'])/100,abs(min(a['core_ratio'],3)-min(b['core_ratio'],3))/3,float(bool(a['alliance'])!=bool(b['alliance']))]
    return max(0,1-sum(distances)/len(distances)-.08*role_dist)

def origin_similarity(a,b):
    # A whole history is relevant only when its starting resources and security are comparable.
    # Use rank share and relative power rather than raw world-era army sizes.
    if a.get('protected')!=b.get('protected') or min(2,a.get('wars',0))!=min(2,b.get('wars',0)):return 0
    if bool(a.get('alliance'))!=bool(b.get('alliance')):return 0
    if abs(a['rank_pct']-b['rank_pct'])>.35 or abs(a['relative']-b['relative'])>.4:return 0
    x=dict(a,phase='起點');y=dict(b,phase='起點')
    base=similarity(x,y)
    scale=abs(math.log((a['pop']+1)/(b['pop']+1)))
    return max(0,base-.12*min(2,scale)-.12*abs(a['relative']-b['relative']))

class WorldLibrary:
    def __init__(self,path,enabled=True,printer=None):
        self.path=str(path);self.enabled=enabled;self.printer=printer or (lambda text:None)
        self.histories={};self.books=[];self.tracks={};self.completed={};self.pending={};self.adoptions={};self.cooldowns={};self.capture_after={};self.readings=[];self.case_feedback={}
        self.last_year=0;self.seq=0;self.revision=0;self.peers={};self.index={};self.dirty=False;self.error='';self.stats={'consultations':0,'adoptions':0,'reviews':0}
    def load(self,year):
        try:
            if os.path.getsize(self.path)>20_000_000:raise ValueError('圖書館超過20MB讀取上限')
            with open(self.path,encoding='utf-8') as f:data=json.load(f)
            if data.get('schema') not in (1,SCHEMA):raise ValueError('圖書館格式版本不相容')
            self.books=[b for b in data.get('books',[]) if b.get('published_year',year+1)<=year][-MAX_BOOKS:]
            self.seq=int(data.get('seq',0));self.revision=int(data.get('revision',0));self.last_year=min(year,int(data.get('last_year',year)))
            if data.get('last_year',0)<=year and data.get('rules')==RULES:
                for name in ('tracks','histories','completed','pending','adoptions','cooldowns','capture_after'):
                    setattr(self,name,dict(list((data.get(name) or {}).items())[:MAX_COUNTRIES]))
                self.readings=data.get('readings',[])[-MAX_READINGS:];self.case_feedback=dict(data.get('case_feedback') or {});self.stats.update(data.get('stats') or {})
            if data.get('schema')==1:
                self.tracks={};self.histories={};self.completed={};self.pending={};self.adoptions={}
            self._bound();self._reindex()
        except FileNotFoundError:pass
        except (OSError,ValueError,TypeError,KeyError) as exc:
            self.error=str(exc);self.printer(f'📚 [圖書館讀取] {exc}；本次從空白觀測資料開始，不修改國家與Q表。')
    def bind(self,countries):
        self.peers=countries
        current=set(list(countries)[:MAX_COUNTRIES])
        for name in ('tracks','histories','completed','pending','adoptions','cooldowns','capture_after'):
            table=getattr(self,name)
            for key in list(table):
                if key not in current:table.pop(key,None)
    def _bound(self):
        # Diverse shelves; newest records replace older records within the same kind.
        caps={'冠軍成就':40,'成長與復甦':28,'失敗與興亡':32}
        keep=[]
        for kind,cap in caps.items():
            shelf=[b for b in self.books if b.get('kind')==kind]
            preferred=[b for b in shelf if b.get('tag') in ('弱國逆襲','弱國崛起','衰退後復甦')]
            selected=preferred[-(cap*3//4):]
            selected_ids={b['id'] for b in selected}
            selected+= [b for b in shelf if b['id'] not in selected_ids][-(cap-len(selected)):]
            keep.extend(selected)
        self.books=sorted(keep,key=lambda b:b['id'])[-MAX_BOOKS:]
        for k,t in self.tracks.items():t['timeline']=thin(t.get('timeline',[]),MAX_TRACK_POINTS)
        for k in self.completed:self.completed[k]=self.completed[k][-MAX_CASES:]
        self.readings=self.readings[-MAX_READINGS:]
        retained={self._case_id(c) for b in self.books for c in b.get('cases',[])}
        retained.update(p.get('case_id','') for p in self.adoptions.values())
        self.case_feedback={k:v for k,v in self.case_feedback.items() if k in retained}
    def _reindex(self):
        self.index={}
        for book in self.books:
            if book.get('rules')!=RULES or book.get('evidence_edition')!=EVIDENCE_EDITION:continue
            for i,case in enumerate(book.get('cases',[])):
                f=case['before'];bucket=(f['phase'],bool(f['wars']),f['protected'])
                self.index.setdefault(bucket,[]).append((book,i,case))
    def _new_track(self,s,season,season_start):
        return dict(start=s,last=s,season=int(season),season_start=int(season_start),timeline=[s],peak_power=s['power'],peak_year=s['year'],actions={},decay_candidate=None,decline_year=None,dead_published=False,gaps=[],attempts={},decision_totals={'total':0,'success':0,'failed':0,'redirected':0},blocks={},checkpoints=[s])
    @staticmethod
    def _origin(t):
        return t['start']
    @staticmethod
    def _strong_start(s):
        return s['rank_pct']<=.5 or s['relative']>=.35
    @staticmethod
    def _weak_start(s):
        return s['rank_pct']>=.4 and s['relative']<=.6
    @staticmethod
    def _complete(t):
        return t['start']['year']==t['season_start'] and t['last']['year']-t['season_start']>=500 and not t.get('gaps')
    @staticmethod
    def _growth(t):
        a,z=t['start'],t['last']
        # Relative rank gains alone can be caused by other countries disappearing.
        return (z['alive'] and z['power']>=max(1000,a['power']*1.8)
                and z['pop']>=a['pop']*1.2 and z['buffer']>=1
                and a['rank_pct']-z['rank_pct']>=.15
                and z['relative']>=a['relative']+.10)
    def _new_history(self,s):
        return dict(generation=s['generation'],points=[s],metrics=[[s['year'],s['power'],s['rank'],s['count'],s['relative']]],decisions=[],gaps=[])
    def _advance(self,t,s):
        old=t['last'];t['last']=s;year=s['year']
        if (year-t['season_start'])%100==0 and (not t.get('checkpoints') or t['checkpoints'][-1]['year']!=year):t.setdefault('checkpoints',[]).append(s)
        if year-old['year']>1:
            t['decay_candidate']=None
            t.setdefault('gaps',[]).append([old['year']+1,year-1]);t['gaps']=t['gaps'][-8:]
        if s['power']>t['peak_power']:t['peak_power']=s['power'];t['peak_year']=year
        if s['power']<=t['peak_power']*.8 and t['peak_power']>0:
            if t['decay_candidate'] is None:t['decay_candidate']=year
            if year-t['decay_candidate']>=4 and t['decline_year'] is None:t['decline_year']=t['decay_candidate']
        else:t['decay_candidate']=None
        if year-t['timeline'][-1]['year']>=20 or old['alive']!=s['alive'] or old['alliance']!=s['alliance'] or (old['wars']==0)!=(s['wars']==0):
            t['timeline'].append(s);t['timeline']=thin(t['timeline'],MAX_TRACK_POINTS)
        return old
    def _history_track(self,key,s):
        h=self.histories[key];cutoff=s['year']-300
        points=[x for x in h['points'] if x['year']>=cutoff]
        # A ten-year checkpoint may miss the exact cutoff: report the actual shorter window.
        if not points or points[-1]['year']!=s['year']:points.append(s)
        a=points[0];metrics=[x for x in h['metrics'] if x[0]>=a['year']]
        t=self._new_track(a,self.tracks[key]['season'],self.tracks[key]['season_start'])
        t['last']=s;t['timeline']=points;t['window']='覆亡前最多300年'
        t['checkpoints']=[x for x in points if (x['year']-a['year'])%100==0]
        peak=max(metrics,key=lambda x:x[1]);t['peak_year'],t['peak_power']=peak[0],peak[1]
        running=0;candidate=None;previous=None
        for y,power,rank,count,relative in metrics:
            if previous is not None and y-previous!=1:candidate=None
            running=max(running,power)
            if running>0 and power<=running*.8:
                if candidate is None:candidate=y
                if y-candidate>=4 and t['decline_year'] is None:t['decline_year']=candidate
            else:candidate=None
            previous=y
        t['gaps']=[[max(a['year'],x),min(s['year'],y)] for x,y in h.get('gaps',[]) if y>=a['year'] and x<=s['year']]
        for row in h['decisions']:
            if row['year']<a['year'] or row['year']==a['year'] and not a.get('before_action'):continue
            self._merge_counts(t,row)
            block=str(min(4,max(0,(row['year']-a['year']-(0 if a.get('before_action') else 1))//100)))
            dest=t['blocks'].setdefault(block,dict(actions={},attempts={},decision_totals={'total':0,'success':0,'failed':0,'redirected':0}))
            self._merge_counts(dest,row)
        return t
    @staticmethod
    def _merge_counts(dest,source):
        for field in ('actions','attempts','decision_totals'):
            table=dest.setdefault(field,{})
            for k,v in source.get(field,{}).items():table[k]=table.get(k,0)+v
    def observe(self,countries,year,season,season_start,remaining):
        if not self.enabled:return
        self.bind(countries);self.last_year=int(year)
        for key,c in list(countries.items())[:MAX_COUNTRIES]:
            s=snapshot(key,c,year,countries,remaining)
            self._finish_cases(key,s);self._review(key,s)
            t=self.tracks.get(key);h=self.histories.get(key)
            if h is None or h['generation']!=s['generation']:
                # An unobserved generation replacement is not an observed military death.
                self.histories[key]=self._new_history(s);h=self.histories[key]
            else:
                prev=h['metrics'][-1][0]
                if year>prev:
                    if year-prev>1:h['gaps'].append([prev+1,year-1])
                    h['metrics'].append([year,s['power'],s['rank'],s['count'],s['relative']])
                    if year-h['points'][-1]['year']>=10 or not s['alive']:h['points'].append(s)
                h['metrics']=[x for x in h['metrics'] if x[0]>=year-300][-301:]
                h['points']=[x for x in h['points'] if x['year']>=year-300][-32:]
                h['decisions']=[x for x in h['decisions'] if x['year']>year-300][-300:]
                h['gaps']=[x for x in h['gaps'] if x[1]>=year-300][-8:]
            if not t or t['season']!=season or t['last']['generation']!=s['generation']:
                # Carry the last settlement snapshot into the new season only when exact.
                origin=(dict(t['last'],remaining=500,phase=phase(500)) if t and t['last']['generation']==s['generation'] and t['last']['year']==season_start and t['last']['alive'] else s)
                self.tracks[key]=self._new_track(origin,season,season_start)
                self.completed[key]=[x for x in self.completed.get(key,[]) if x['before']['generation']==s['generation']]
                t=self.tracks[key]
                if origin['year']==s['year']:continue
            old=self._advance(t,s)
            if old['alive'] and not s['alive'] and not t['dead_published']:
                death=self._history_track(key,s)
                good=any((rank-1)/max(1,count)<=.5 or relative>=.35 for y,power,rank,count,relative in h['metrics'] if y<s['year'])
                if s['year']-death['start']['year']>=5 and good:
                    self._publish(key,death,'失敗與興亡',year,tag='覆亡警示',reason='覆亡前觀測窗內曾具相當實力，現已確認滅亡；優先核對衰退前與危機後的選擇。')
                t['dead_published']=True
        self.dirty=True
    def _finish_cases(self,key,s):
        waiting=[]
        for p in self.pending.get(key,[]):
            if s['year']>=p['due'] or not s['alive'] or s['generation']!=p['before']['generation']:
                if s['year']<=p['before']['year']:continue
                case=dict(p,after=s,score=outcome(p['before'],s),observed_years=s['year']-p['before']['year'])
                self.completed.setdefault(key,[]).append(case)
                self.completed[key]=self._retain_cases(self.completed[key])
            else:waiting.append(p)
        self.pending[key]=waiting
    @staticmethod
    def _retain_cases(cases):
        if len(cases)<=MAX_CASES:return cases
        newest=sorted(cases,key=lambda c:c['before']['year'],reverse=True)[:3]
        keep=list(newest);seen={(c['action'],c['before']['phase'],c['score']>=0) for c in keep}
        for c in sorted(cases,key=lambda c:-abs(c['score'])):
            label=(c['action'],c['before']['phase'],c['score']>=0)
            if label not in seen:keep.append(c);seen.add(label)
            if len(keep)>=MAX_CASES:break
        return sorted(keep,key=lambda c:c['before']['year'])
    def _prepare_track(self,key,before):
        t=self.tracks[key];year=before['year']
        if year>t['season_start']+500 and t['last']['year']==t['season_start']+500:
            boundary=t['season_start']+500
            origin=dict(t['last'],remaining=500,phase=phase(500))
            t=self._new_track(origin,t['season']+1,boundary);self.tracks[key]=t
        if t['start']['generation']!=before['generation']:
            origin=dict(before,before_action=True)
            t=self._new_track(origin,t['season'],t['season_start']);self.tracks[key]=t
            self.histories[key]=self._new_history(origin)
            self.completed[key]=[];self.capture_after.pop(key,None)
        return t
    def record_decision(self,key,c,year,strategic_action,engine_action,success,before,advice=None,matched=True):
        if not self.enabled or key not in self.tracks:return
        t=self._prepare_track(key,before)
        name=ENGINE_NAMES.get(engine_action,str(engine_action))
        row=dict(actions={name:1} if success else {},attempts={name:1},decision_totals={'total':1,'success':int(bool(success)),'failed':int(not success),'redirected':int(not matched)})
        if not t['start']['alive'] or t['start']['generation']!=before['generation']:return
        # Decisions belong to the season in which they execute, including its first year.
        self._merge_counts(t,row)
        block=str(min(4,max(0,(year-t['season_start']-1)//100)))
        dest=t.setdefault('blocks',{}).setdefault(block,dict(actions={},attempts={},decision_totals={'total':0,'success':0,'failed':0,'redirected':0}))
        self._merge_counts(dest,row)
        h=self.histories.get(key)
        if h and h['generation']==before['generation']:
            if not h['decisions'] or h['decisions'][-1]['year']!=year:h['decisions'].append(dict(year=year,actions={},attempts={},decision_totals={}))
            self._merge_counts(h['decisions'][-1],row)
            h['decisions']=h['decisions'][-300:]
        self.dirty=True
        if not matched:return
        if success and year>=self.capture_after.get(key,0) and len(self.pending.get(key,[]))<2:
            self.pending.setdefault(key,[]).append(dict(before=before,action=int(strategic_action),engine_action=int(engine_action),due=year+CASE_YEARS,immediate={'soldiers':int(num(c,'soldiers')),'target':num(c,'military_target_ratio',.3)}))
            self.capture_after[key]=year+10
        if not advice or not success or key in self.adoptions or year<self.cooldowns.get(key,0):return
        chosen=next((x for x in advice.get('sources',[]) if x['score']>0 and x['action']==strategic_action),None)
        mode='借鏡'
        if chosen is None:
            chosen=next((x for x in advice.get('sources',[]) if x['score']<0 and x['action']!=strategic_action),None);mode='參考反例'
        if chosen is None:return
        self.adoptions[key]=dict(book_id=chosen['book_id'],case_index=chosen['case_index'],case_id=chosen['case_id'],before=before,action=int(strategic_action),due=year+REVIEW_YEARS,mode=mode)
        self.cooldowns[key]=year+CONSULT_COOLDOWN;self.stats['adoptions']+=1
        title=chosen['title'];text=f"第{year}年【{c.get('display_name',key)}】{mode}《{title}》；起點相似度{chosen.get('origin_similarity',0):.2f}、當下相似度{chosen.get('similarity',0):.2f}（不是成功率）；相近處境：{before['role']}、本屆{before['phase']}、{'正在作戰' if before['wars'] else '未參戰'}；本次採取「{ACTION_NAMES.get(strategic_action)}」，{REVIEW_YEARS}年後檢視成效。經驗只小幅影響偏好，並非勝利保證。"
        self.readings.append(dict(year=year,country=key,name=before['name'],book_id=chosen['book_id'],kind='研習',text=text));self.readings=self.readings[-MAX_READINGS:]
        self.printer('📚 [世界圖書館] '+text);self.dirty=True
    def advise(self,key,c,year,valid,remaining=None):
        if not self.enabled or key not in self.tracks:return {}
        s=snapshot(key,c,year,self.peers,remaining)
        self._prepare_track(key,s)
        if key in self.adoptions or year<self.cooldowns.get(key,0):return {}
        bucket=(s['phase'],bool(s['wars']),s['protected']);matches=[]
        for book,i,case in self.index.get(bucket,[]):
            if book['published_year']>=year or case['after']['year']>=year or abs(case['score'])<.08:continue
            if case['action'] not in valid:continue
            origin=self.tracks[key]['start']
            origin_sim=origin_similarity(origin,book['start'])
            if origin_sim<.78:continue
            sim=similarity(s,case['before'])
            if sim<.80:continue
            feedback=self.case_feedback.get(self._case_id(case),{}).get(self._context(s),{'good':0,'bad':0})
            reliability=(2+feedback['good'])/(3+feedback['good']+2*feedback['bad']+.35*feedback.get('neutral',0))
            age=1/(1+(year-case['after']['year'])/2500)
            weight=sim*origin_sim*min(1,abs(case['score'])*3)*reliability*age
            matches.append((weight,book,i,case,sim,origin_sim))
        if not matches:return {}
        # Distinct source books prevent a prolific single winner from dominating the shortlist.
        sources=[];used=set();used_cases=set();bias={}
        for weight,book,i,case,sim,origin_sim in sorted(matches,key=lambda x:(-x[0],-x[1]['id'],x[2])):
            case_id=self._case_id(case)
            if book['id'] in used or case_id in used_cases:continue
            used.add(book['id']);used_cases.add(case_id);direction=1 if case['score']>0 else -1
            action=case['action'];bias[action]=clamp(bias.get(action,0)+direction*BIAS_LIMIT*weight,-BIAS_LIMIT,BIAS_LIMIT)
            sources.append(dict(book_id=book['id'],title=book['title'],case_index=i,case_id=case_id,action=action,score=case['score'],similarity=round(sim,3),origin_similarity=round(origin_sim,3)))
            if len(sources)>=3:break
        self.stats['consultations']+=1
        return dict(bias=bias,sources=sources,context=s)
    @staticmethod
    def _case_id(c):
        s=c['before'];return f"{s['key']}:{s['generation']}:{s['year']}:{c['action']}"
    @staticmethod
    def _context(s):return s['role']+'|'+s['phase']+'|'+str(min(2,s['wars']))+'|'+str(s['protected'])
    def _review(self,key,s):
        p=self.adoptions.get(key)
        if not p or (s['year']<p['due'] and s['alive'] and s['generation']==p['before']['generation']):return
        score=outcome(p['before'],s);book=next((b for b in self.books if b['id']==p['book_id']),None)
        if book:
            feedback=book.setdefault('feedback',{});context=self._context(p['before'])
            f=feedback.setdefault(context,{'good':0,'bad':0,'neutral':0})
            f['good' if score>.05 else 'bad' if score<-.05 else 'neutral']+=1
            while len(feedback)>16:feedback.pop(next(iter(feedback)))
        case_id=p.get('case_id')
        if case_id:
            feedback=self.case_feedback.setdefault(case_id,{})
            f=feedback.setdefault(self._context(p['before']),{'good':0,'bad':0,'neutral':0})
            f['good' if score>.05 else 'bad' if score<-.05 else 'neutral']+=1
            while len(feedback)>16:feedback.pop(next(iter(feedback)))
        result='改善' if score>.05 else '惡化' if score<-.05 else '變化有限'
        text=f"第{s['year']}年【{p['before']['name']}】研習後{s['year']-p['before']['year']}年回顧：綜合觀測{result}；戰力 {p['before']['power']:,}→{s['power']:,}、人口 {p['before']['pop']:,}→{s['pop']:,}、每人存糧 {p['before']['buffer']:.1f}→{s['buffer']:.1f}。{'國家滅亡或政權世代更替，視為本次策略連續性中斷。' if not s['alive'] or s['generation']!=p['before']['generation'] else ''}此為同時期結果，不能單獨歸因於研習；已更新相近處境的參考權重。"
        self.readings.append(dict(year=s['year'],country=key,name=p['before']['name'],book_id=p['book_id'],kind='回顧',score=score,text=text));self.readings=self.readings[-MAX_READINGS:]
        self.printer('🧠 [研習回顧] '+text);self.stats['reviews']+=1;self.adoptions.pop(key,None);self.revision+=1;self.dirty=True
    def settle_season(self,key,year,season):
        champion=None
        t=self.tracks.get(key)
        if t and t['last']['alive']:
            comeback=self._weak_start(t['start']) and self._growth(t) and self._complete(t)
            tag='弱國逆襲' if comeback else '同起點競逐' if t['start'].get('tied_count',1)>1 and t['start'].get('tied_rank',t['start']['rank'])==1 else '霸權守成' if t['start']['rank_pct']<=.2 else '中堅突破'
            if not self._complete(t):tag='觀測未完整'
            champion=self._publish(key,t,'冠軍成就',year,tag=tag,reason='已由遊戲結算確認奪冠；逆襲分類另要求完整屆初、低起點及實質成長。')
        growth=[];decline=[]
        for k,t in self.tracks.items():
            if t['season']!=season or not self._complete(t) or not t['last']['alive']:continue
            a,z=t['start'],t['last']
            if k!=key and self._growth(t):growth.append((int(self._weak_start(a)),outcome(a,z),k,t))
            # Sustained decline must have been observed; a single last-year demobilization is insufficient.
            if self._strong_start(a) and t['decline_year'] is not None and z['power']<=t['peak_power']*.55 and (z['rank_pct']-a['rank_pct']>=.15 or z['relative']<=a['relative']*.6):
                decline.append((z['power']/max(1,t['peak_power']),k,t))
        # Keep at most one high-start growth example; weaker starts have first priority.
        high=0;selected=0
        for weak,score,k,t in sorted(growth,key=lambda x:(-x[0],-x[1],x[2])):
            if not weak and high>=1:continue
            tag='弱國崛起' if weak else '強國發展'
            if t['decline_year'] is not None and t['last']['power']>=t['peak_power']*.9:tag='衰退後復甦'
            self._publish(k,t,'成長與復甦',year,tag=tag,reason='完整一屆內戰力至少增長80%、人口至少增長20%、排名百分位提升至少15個百分點，且相對領先者戰力提升、每人存糧不低於1。')
            high+=int(not weak);selected+=1
            if selected>=4:break
        for ratio,k,t in sorted(decline)[:2]:
            self._publish(k,t,'失敗與興亡',year,tag='存續中的衰退',reason='屆初處於前半段或具有相當相對戰力，曾持續衰退，屆末戰力不及高峰55%，且排名或相對戰力明顯滑落。')
        return champion
    def _publish(self,key,t,kind,year,tag=None,reason=None):
        identity=(key,t['start']['generation'],t['season'],kind)
        if any(tuple(b.get('identity',[]))==identity for b in self.books):return None
        self.seq+=1;start,last=t['start'],t['last']
        suffix='冠軍之路' if kind=='冠軍成就' else '成長與復甦紀' if kind=='成長與復甦' else '興衰與覆亡'
        title=f"{last['name']}：{suffix}（第{t['season']}屆）"
        timeline=list(t['timeline'])
        if not timeline or timeline[-1]['year']!=last['year']:timeline.append(last)
        timeline=thin(timeline,MAX_BOOK_POINTS)
        cases=[c for c in self.completed.get(key,[]) if c['before']['year']>=start['year'] and c['before']['generation']==start['generation'] and c['after']['year']<=year]
        # Retain different actions and both positive and negative observations.
        chosen=[];seen=set()
        ordered=sorted(cases,key=lambda c:-abs(c['score']))
        preferred=[]
        for sign in (1,-1):
            match=next((c for c in ordered if c['score']*sign>=.08),None)
            if match is not None:preferred.append(match)
        for stage in ('前段','中段','後段','決勝期'):
            match=next((c for c in ordered if c['before']['phase']==stage),None)
            if match is not None:preferred.append(match)
        for c in preferred+ordered:
            label=(c['action'],c['before']['phase'],c['score']>=0)
            if label not in seen:chosen.append(copy.deepcopy(c));seen.add(label)
            if len(chosen)>=6:break
        book=dict(checkpoints=copy.deepcopy(t.get('checkpoints',[])),evidence_edition=EVIDENCE_EDITION,tag=tag or '觀測案例',selection_reason=reason or '依實際觀測入選。',window=t.get('window','本屆500年'),origin_scope='覆亡前觀測窗起點' if t.get('window') else '本屆觀測起點',decision_totals=copy.deepcopy(t.get('decision_totals',{})),attempts=dict(t.get('attempts',{})),blocks=copy.deepcopy(t.get('blocks',{})),season_start=t['season_start'],complete_season=self._complete(t),id=self.seq,identity=list(identity),title=title,kind=kind,country=key,season=t['season'],generation=start['generation'],published_year=int(year),rules=RULES,observed_start=start['year'],observed_end=last['year'],partial=start['year']>t['season_start'],gaps=list(t.get('gaps',[])),start=copy.deepcopy(start),end=copy.deepcopy(last),timeline=copy.deepcopy(timeline),peak_power=t['peak_power'],peak_year=t['peak_year'],decline_year=t['decline_year'],actions=dict(t['actions']),cases=chosen,feedback={})
        self.books.append(book);self._bound();self._reindex();self.revision+=1;self.dirty=True
        self.printer(f'📖 [圖書館新書] 第{year}年收錄《{title}》【{book["tag"]}】；觀測 {start["year"]}—{last["year"]} 年，{len(chosen)}則已完成追蹤的決策案例。')
        return book
    def save(self,force=False):
        if not self.enabled or not self.dirty or (not force and self.last_year%10):return
        self._bound()
        data={name:getattr(self,name) for name in ('books','tracks','histories','completed','pending','adoptions','cooldowns','capture_after','readings','last_year','seq','revision','stats','case_feedback')}
        data.update(schema=SCHEMA,rules=RULES)
        try:
            os.makedirs(os.path.dirname(self.path) or '.',exist_ok=True)
            temp=self.path+'.tmp'
            with open(temp,'w',encoding='utf-8') as f:json.dump(data,f,ensure_ascii=False,separators=(',',':'),allow_nan=False)
            os.replace(temp,self.path);self.dirty=False;self.error=''
        except (OSError,ValueError) as exc:
            self.error=str(exc);self.printer(f'⚠️ [圖書館存檔] {exc}；世界存檔與Q表不受此檔寫入影響。')
