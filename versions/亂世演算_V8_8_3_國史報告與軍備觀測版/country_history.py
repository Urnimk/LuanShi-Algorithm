"""Evidence-based country histories. No gameplay decisions or randomness.
National lifetimes end at extinction, not at every succession/coup generation.
Annual observation is bounded to the first 1000 observed years per lifetime;
endpoints/chronicle peaks remain available beyond that window.
"""
import csv
import hashlib
import json
import os
from pathlib import Path
import threading

MAX_YEARS=1000
_lock=threading.RLock()
_root=None
_before={}
_events={}
_handles={}
_counts={}
economy_key=None


def periods(c):
    groups=[];current=[]
    for entry in c.get('country_chronicle',[]) or []:
        if not isinstance(entry,dict):continue
        current.append(entry)
        if '滅國' in str(entry.get('end_reason','')) or '滅亡' in str(entry.get('end_reason','')):
            groups.append(current);current=[]
    if current:groups.append(current)
    return groups


def identity(key, group):
    start=min([int(e.get('start_year',1) or 1) for e in group] or [1])
    generation=min([int(e.get('generation',1) or 1) for e in group] or [1])
    token=hashlib.sha256(str(key).encode()).hexdigest()[:20]
    return f'{token}_{start}_{generation}',start


def snapshot(c):
    pop=max(0,int(c.get('pop_total',0) or 0));soldiers=max(0,int(c.get('soldiers',0) or 0))
    return dict(name=c.get('display_name',''),generation=c.get('country_generation',1),
                alive=bool(c.get('is_alive',True)),power=soldiers*50 if c.get('is_alive',True) else 0,
                population=pop,soldiers=soldiers,ratio=round(soldiers/max(1,pop),6),
                target=float(c.get('military_target_ratio',.3)),food=c.get('food',0),
                metal=c.get('metal',0),wood=c.get('wood',0),fortification=c.get('fortification',0),
                stability=c.get('political_stability',75),
                exhaustion=c.get('war_exhaustion',0),alliance=c.get('current_alliance',''),
                won=c.get('wars_won',0),lost=c.get('wars_lost',0),
                champions=len(c.get('championship_records',[])),
                wars=list(c.get('current_wars',[]) or []))


def configure(path):
    global _root,_before,_events
    with _lock:
        flush(close=True)
        _root=Path(path);_root.mkdir(parents=True,exist_ok=True)
        _before={};_events={};_counts.clear()


def begin(countries):
    global _before,_events
    with _lock:
        _before={k:snapshot(c) for k,c in countries.items()}
        _events={}


def event(key,kind,**facts):
    with _lock:
        if _root is not None:
            _events.setdefault(key,[]).append(dict(kind=kind,**facts))


def path_for(root,key,group):
    token,start=identity(key,group)
    return Path(root)/(token+'.jsonl')


def annual(countries,year,phase,remaining):
    if _root is None:return
    with _lock:
        ranks={k:i+1 for i,k in enumerate(sorted(
            (k for k,c in countries.items() if c.get('is_alive',True)),
            key=lambda k:(-countries[k].get('power',0),k)))}
        for key,c in countries.items():
            groups=periods(c)
            if not groups:continue
            group=groups[-1];path=path_for(_root,key,group)
            if path not in _counts:
                rows=read_rows(path)
                # Preserve an abandoned future on rollback; never blend divergent timelines.
                if rows and rows[-1]['year']>year:
                    archive=path.with_suffix(f'.branch-{rows[-1]["year"]}.jsonl')
                    suffix=0
                    while archive.exists():
                        suffix+=1;archive=path.with_suffix(f'.branch-{rows[-1]["year"]}-{suffix}.jsonl')
                    os.replace(path,archive)
                    rows=[r for r in rows if r['year']<year]
                    with path.open('w',encoding='utf-8') as f:
                        for row in rows:f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
                # Preserve, then remove an interrupted trailing fragment before append.
                if path.exists():
                    raw=path.read_bytes()
                    if raw and not raw.endswith(b'\n'):
                        fragment=raw[raw.rfind(b'\n')+1:]
                        try:
                            json.loads(fragment)
                            path.write_bytes(raw+b'\n')
                        except (ValueError,UnicodeError):
                            archive=path.with_suffix('.interrupted.bin');suffix=0
                            while archive.exists():
                                suffix+=1;archive=path.with_suffix(f'.interrupted-{suffix}.bin')
                            archive.write_bytes(fragment)
                            path.write_bytes(raw[:raw.rfind(b'\n')+1])
                _counts[path]=[sum(r.get("phase")!="INITIAL" for r in rows),rows[-1]['year'] if rows else -1]
            count,last=_counts[path]
            if last>=year:continue
            alive=bool(c.get('is_alive',True))
            death=not alive and _before.get(key,{}).get('alive',True)
            if count>=MAX_YEARS and not death:continue
            # Repeated dead years are not a country's active history.
            if not alive and not death:continue
            row=snapshot(c)
            row.update(year=int(year),rank=ranks.get(key),phase=phase,remaining=int(remaining),
                       before=_before.get(key),events=_events.get(key,[]))
            f=_handles.get(path)
            if f is None:
                f=_handles[path]=path.open('a',encoding='utf-8')
            f.write(json.dumps(row,ensure_ascii=False,separators=(',',':'))+'\n')
            _counts[path]=[count+(phase!="INITIAL"),year]
            if not alive:
                f.flush();f.close();_handles.pop(path,None)
        if year%10==0:flush()


def flush(close=False):
    with _lock:
        for f in list(_handles.values()):
            f.flush()
            if close:f.close()
        if close:_handles.clear()


def read_rows(path):
    if not Path(path).exists():return []
    rows=[]
    with Path(path).open(encoding='utf-8') as f:
        for line in f:
            try:row=json.loads(line)
            except json.JSONDecodeError:continue # tolerate an interrupted final line
            if isinstance(row,dict) and 'year' in row:rows.append(row)
    return rows


def analyse(rows):
    """Sustained decline: 10 observed consecutive years below 80% of prior high.
    Recovery ends a spell; this is a retrospective threshold, not causal proof.
    """
    annual=sorted({r['year']:r for r in rows}.values(),key=lambda r:r['year'])
    high=0;streak=[];decline=None
    flags=[];demobs=[];population_dilution=[]
    for r in annual:
        if not r.get('alive',True):continue
        high=max(high,float(r.get('power',0)))
        if high>0 and r['power']<high*.8:
            if streak and r['year']!=streak[-1]+1:streak=[]
            streak.append(r['year'])
            if len(streak)>=10 and decline is None:decline=streak[0]
        else:streak=[]
        b=r.get('before') or {}
        if r.get('ratio',0)<b.get('ratio',0) and r.get('soldiers',0)>=b.get('soldiers',0):
            population_dilution.append(r['year'])
        for e in r.get('events',[]):
            if e.get('kind')=='裁軍執行':
                demobs.append(dict(year=r['year'],**e))
                # Flag is a review candidate, not a counterfactual proof of error.
                pre=e.get('before',{})
                if e.get('phase')=='LATE' and (e.get('rank') or 999)>0 and (e.get('rank') or 999)<=10:
                    flags.append(dict(year=r['year'],remaining=e.get('remaining'),rank=e.get('rank'),
                                      target_before=pre.get('target'),target_after=e.get('target_after'),
                                      runway=e.get('runway'),exhaustion=pre.get('exhaustion'),
                                      demobilized=e.get('demobilized')))
    peak=max(annual,key=lambda r:r.get('power',0)) if annual else None
    terminal=None
    if annual and not annual[-1].get('alive',True) and peak and peak.get('power',0)>0:
        after=[r for r in annual if r['year']>peak['year']]
        tail=[]
        for r in reversed(after):
            if r.get('power',0)<peak['power']*.8:tail.append(r['year'])
            else:break
        if tail:terminal=min(tail)
    return dict(rows=annual,decline=decline,terminal=terminal,peak=peak,late_demobs=flags,demobs=demobs,
                dilution=population_dilution)


def render_report(key,c,root,group=None):
    flush()
    groups=periods(c)
    if not groups:return '尚無編年史，無法建立國史報告。'
    group=group or groups[-1]
    token,start=identity(key,group)
    end=group[-1].get('end_year')
    extinct='滅國' in str(group[-1].get('end_reason','')) or '滅亡' in str(group[-1].get('end_reason',''))
    rows=read_rows(path_for(root,key,group));a=analyse(rows)
    peaks=[e for e in group if e.get('peak_power') is not None]
    peak=max(peaks,key=lambda e:float(e.get('peak_power',0))) if peaks else {}
    high=int(peak.get('peak_power',0));highyear=peak.get('peak_power_year')
    if a['peak'] and a['peak']['power']>high:
        high=int(a['peak']['power']);highyear=a['peak']['year']
    title=f'《{key}國史：{group[0].get("name",key)}的興衰》'
    status=f'第{end}年滅國，終結者：{group[-1].get("ended_by") or "原始紀錄未載"}' if extinct else '本次觀察結束時尚未滅國，以下不是完整亡國史'
    coverage=(f'逐年證據：第{rows[0]["year"]}～{rows[-1]["year"]}年，共{len(rows)}筆。' if rows else '沒有逐年觀測資料；本報告只能引用既有編年史摘要。')
    lines=[title,'═'*34,'一、史料與範圍',f'國家識別：{key}；此輪國家存續起於第{start}年。',status,
           coverage,'每輪國家存續最多觀測1000年；正常交接、政變會累加為同一段國家歷史，只有滅國才分段。',
           '未觀測的舊年不補寫原因；軍隊比例下降不直接等於裁軍；相關性不等於因果。','',
           '二、立國、極盛與轉折',
           f'第{start}年，{group[0].get("name",key)}的旗幟見於現存編年史。其後經歷{len(group)}個政權世代，國號與政府的更替，並不等於國家的消失。',
           f'依現存紀錄，最高戰力為{high:,}，達到於第{highyear}年。' if highyear is not None else f'最高戰力為{high:,}，但原始史料沒有留下確切年份。']
    if rows and rows[0]['year']>start:
        lines.append(f'注意：第{start}～{rows[0]["year"]-1}年的逐年決策未被觀測。下列衰弱年份僅是觀測範圍內的起點，不能據此認定為整個國家歷史最早的衰弱。')
    if a['decline'] is not None:
        lines.append(f'軍勢由盛轉衰的可辨識起點是第{a["decline"]}年：從這年開始，連續至少10個觀測年低於此前已觀測最高戰力的80%。這是統計上的衰弱段，並不保證其後沒有中興。')
    else:
        lines.append('現有逐年證據尚未辨認出「連續10年低於此前高峰80%」的衰弱段；資料不足時，不把最後一次高峰直接當成衰敗起點。')
    if a['terminal'] is not None:
        lines.append(f'終局急跌段則從第{a["terminal"]}年開始：此後一直低於觀測高峰80%，直到滅國，期間未恢復。即使不足10年，仍屬可確認的急速崩落，不能因未滿長期門檻而漏記。')
    if rows:
        first=rows[0]
        beginning='立國當年' if first['year']==start else '現存逐年觀測開始時'
        lines.append(f'{beginning}，戶籍記有人口{int(first.get("population",0)):,}，在冊士兵{int(first.get("soldiers",0)):,}，長期軍備目標{first.get("target",0):.0%}。這是本段故事可核對的起點，而非後世補寫的盛世。')
        alliance_row=next((r for r in rows if r.get('alliance')),None)
        if alliance_row:
            lines.append(f'第{alliance_row["year"]}年，觀測盟籍中見「{alliance_row["alliance"]}」。這份盟約可證明外交歸屬，不能單憑盟名就斷言每場危機都得到救援。')
        last_living=next((r for r in reversed(rows) if r.get('alive',True)),None)
        if extinct and last_living:
            lines.append(f'極盛與終局之間，史料留下了沉重的落差：最後一筆存活紀錄在第{last_living["year"]}年，尚有人口{int(last_living.get("population",0)):,}、士兵{int(last_living.get("soldiers",0)):,}。其後第{end}年，國號在此輪國家存續的篇章中落幕；終結者由原始編年史記為{group[-1].get("ended_by") or "未載"}。')
    lines += ['','三、軍備政策的客觀檢視',f'有證據的主動裁軍：{len(a["demobs"])}次；其中屆末前十名裁軍：{len(a["late_demobs"])}次。',
              f'士兵數未減、但士兵比例下降的年度：{len(a["dilution"])}個，屬人口分母變化，不能記成將領解散軍隊。']
    for f in a['late_demobs'][:20]:
        runway='未記錄' if f['runway'] is None else f'{f["runway"]:.1f}年'
        lines.append(f'第{f["year"]}年：名次{f["rank"]}，距結算{f["remaining"]}年；主動退役{f["demobilized"]}人，長期目標{f["target_before"]:.0%}→{f["target_after"]:.0%}，行動前糧食續航{runway}、疲勞{f["exhaustion"]}。此為應複核的爭冠取捨，不據此斷言必輸冠軍。')
    if len(a['late_demobs'])>20:lines.append('更多年度見逐年CSV與原始JSONL。')
    lines += ['','四、國勢年表（有證據的節點）']
    for e in group:
        lines.append(f'第{e.get("start_year","?")}～{e.get("end_year") or "尚未結束"}年｜{e.get("name",key)}｜{e.get("regime_type","")}｜高峰{int(e.get("peak_power",0)):,}｜結束：{e.get("end_reason") or "尚在延續"}。')
    changes=[];previous=None
    for r in a['rows']:
        if previous:
            if r.get('alliance')!=previous.get('alliance'):changes.append(f'第{r["year"]}年，聯盟由「{previous.get("alliance") or "無"}」變為「{r.get("alliance") or "無"}」。')
            for field,label in [('won','勝仗'),('lost','敗仗'),('champions','奪冠')]:
                gain=int(r.get(field,0))-int(previous.get(field,0))
                if gain>0:changes.append(f'第{r["year"]}年，累計{label}增加{gain}次。')
        previous=r
    lines += changes[:80]
    if len(changes)>80:lines.append('節點過多，此處列前80項，其餘保留於原始逐年資料。')
    lines += ['','五、史論與改進建議',
              '這個國家的命運不是單一士兵比例所能概括。軍隊需要糧食，也需要能把發展轉化為屆末優勢的政策；修養可以保存國力，無目的的長期降編則可能讓冠軍拱手他人。',
              '建議一：將「缺糧時的臨時縮編」與「長期軍備目標下降」分開。一次休養不應無期限降低之後每年的徵兵目標。',
              '建議二：屆末爭冠只在有資源、接近冠軍且風險可控時提高優先度；比較絕對士兵增量、與榜首差距、剩餘年數與可維持的糧食續航。',
              '建議三：對安全情況下的爭冠裁軍設機會成本；嚴重飢荒、補給斷裂仍可例外，不能為冠軍強迫餓死。',
              '建議四：增加政策冷卻與可回復的軍備目標，追蹤招募／裁軍往返震盪；修改後應以同存檔、同隨機狀態比較屆末戰力、糧荒、死亡與奪冠率。',
              '建議五：目前「防禦修復與休養」同時映射加固與裁軍；疲勞超過45就偏向裁軍，加固不可用時也可能只剩裁軍。應讓非降編的休養有獨立出口，並考慮距結算時間。',
              '建議六：前三名的前段／後段可能壓縮成相同256狀態；軍備目標未進入RL快照，裁軍也沒有自己的延遲評估。應先補足政策後果的可觀測性，再設計相容的時限與延遲學習；修改狀態語義時須標示Q表相容性。',
              '以上為建議，本版不自動修改兵力平衡、AI獎勵或裁軍規則。',
              '', '六、史家的界線',
              ('此輪國家的旗幟最終在第'+str(end)+'年落下。可以確證的，是編年史所記的終局；無法確證的密議、背叛動機與將領心聲，不寫入客觀史。' if extinct else '觀察至此，旗幟仍未落下。故事可以停筆，史實卻不能被代寫成滅亡。'),
              '本報告使用規則與真實數據生成敘事，不呼叫外部大型語言模型，也不補造戰役、人物、因果或未來結果。']
    return '\n'.join(lines)


def export_csv(rows,path):
    fields=['year','name','generation','alive','power','rank','population','soldiers','ratio','target',
            'food','metal','stability','exhaustion','alliance','won','lost','champions','phase','remaining','events']
    with open(path,'w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader()
        for row in rows:
            w.writerow({**row,'events':json.dumps(row.get('events',[]),ensure_ascii=False)})
