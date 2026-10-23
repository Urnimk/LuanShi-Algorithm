"""Human readable, evidence-grounded books and self-contained HTML exports."""
import html
import json
import os
from collections import Counter
from world_library import ACTION_NAMES,RULES,SCHEMA,REVIEW_YEARS,MAX_BOOKS

GUIDE=f'''世界圖書館｜閱讀說明

這裡收錄本次程式實際觀察到的冠軍成就、成長復甦與失敗教訓。
每本書都能由玩家閱讀，也能供 AI 在相近處境下小幅參考。

一、什麼時候有書？
第一本冠軍之書在下一次屆末結算後出版。每百年另選最多兩個有明顯成長的案例；
觀測至少五年後滅亡的國家，可留下失敗與興亡之書。
舊存檔不會憑空補出尚未記錄的歷史；從屆中開始觀測時，書中會標示紀錄不完整。

二、書裡有什麼？
觀測起點、國力與糧食、聯盟與保護條件、重要轉折、觀測期間最高戰力、
首次持續衰退時間、已完成15年追蹤的決策案例，以及成果與限制。
每人存糧是糧食庫存除以人口，不等於可維持的年數。

三、AI如何參考？
只有已出版、已完成後續觀測的案例才能查閱，不能偷看未來。
季節階段、是否參戰、是否受保護必須相同，再比較國力、軍備、存糧、城防及盟友條件。
圖書館只小幅加減既有合法策略的選擇分數，不複製冠軍Q表，也不移除自主探索。
採用後{REVIEW_YEARS}年回顧，改善、惡化與中斷都會留下紀錄。這不是嚴格因果實驗。

四、如何閱讀與匯出？
選取書名後閱讀正文，可調整字級。匯出本書或整座圖書館為HTML，
下載後直接用瀏覽器打開，不需網路；也可以用瀏覽器列印為PDF。
圖書館最多{MAX_BOOKS}本；早期重要著作可手動匯出留存。
'''

def pct(a,b):return (a/max(1,b)-1)*100

def book_chapters(b):
    a,z=b['start'],b['end'];year=b['published_year'];kind=b['kind'];partial=b.get('partial',True)
    opening=(f"世界曆第{b['observed_start']:,}年，史官開始記下{a['name']}的這一段道路。當時，它在{a['count']}個存活國家中位列第{a['rank']}，擁有{a['pop']:,}人口、{a['soldiers']:,}士兵與{a['power']:,}戰力。" )
    ending=(f"至第{year:,}年，{z['name']}登上第{b['season']}屆冠軍之位。這是一個已由遊戲結算確認的結果；以下追索其可觀測的成就過程。" if kind=='冠軍成就' else f"至第{b['observed_end']:,}年，這段紀錄以{'國家滅亡' if not z['alive'] else '持續成長的階段性成果'}告一段落。興亡留下的數字與選擇，成為後世可供核對的經驗。")
    conditions=f"起點士兵占人口{a['ratio']:.1%}，長期軍備目標{a['target']:.1%}；城防{a['fort']:.0f}/100，戰爭疲勞{a['fatigue']:.1f}/100。存糧{a['food']:,}，每人存糧{a['buffer']:.1f}。這是庫存比例，不能直接當作補給年數。"
    alliance=(f"其時身在{a['alliance']}，最強存活盟友的名義戰力約為本國{a['core_ratio']:.2f}倍，盟友信任值{a['trust']:.1f}。盟友實力代表潛在支援條件，並不保證一定出兵。" if a['alliance'] else '觀測起點並無普通聯盟庇護，發展與軍備安排必須放在這個條件下理解。')
    protection='當時仍受新生或重建保護，不能把保護期的低軍備策略原封不動用在無保護的國家。' if a['protected'] else '起點沒有新生或重建保護，安全條件應與其他無保護案例比較。'
    counts=sorted(b.get('actions',{}).items(),key=lambda p:(-p[1],p[0]))
    actions='；'.join(f'{name}{count}次' for name,count in counts[:6]) or '尚未累積足夠的成功執行決策紀錄'
    road=f"在已觀測且成功執行的行動中，較常見的是：{actions}。這些是實際行動次數，並非人工替它指定的性格，也不代表每次都有長期收益。"
    points=b.get('timeline',[])
    story=[]
    if len(points)>2:
        mid=points[len(points)//2]
        story.append(f"走到第{mid['year']:,}年的年表節點，{mid['name']}的人口已為{mid['pop']:,}，戰力{mid['power']:,}，士兵占人口{mid['ratio']:.1%}。與觀測起點相比，這些數字呈現的是國力累積的過程，而不只是最後一年突然出現的冠軍戰力。")
        first_ally=next((x for x in points if x['alliance']),None)
        if first_ally:
            story.append(f"同盟也是這段歷程的背景。年表最早在第{first_ally['year']:,}年的節點記錄它身處{first_ally['alliance']}；終點盟籍則為{z['alliance'] or '無聯盟'}。這些節點可以核對結盟環境，但不能僅因有盟籍，就推定每場危機都曾獲救。")
        late=next((x for x in points if x['remaining']<=50),None)
        if late and late['year']<z['year']:
            story.append(f"進入本屆最後50年的決勝時間後，可見的早期節點是第{late['year']:,}年：戰力{late['power']:,}、人口{late['pop']:,}、士兵比例{late['ratio']:.1%}、每人存糧{late['buffer']:.1f}。到終點，戰力變為{z['power']:,}，士兵比例{z['ratio']:.1%}。閱讀末段軍備時，應同時看這段變化與糧食，而不能只用「兵越多越好」概括。")
    if a['pop']>0 and a['ratio']>0:
        story.append(f"依本版排名規則，名義戰力就是士兵數乘以50。這段歷程的人口規模變為起點的{z['pop']/a['pop']:.2f}倍，士兵占比則變為起點的{z['ratio']/a['ratio']:.2f}倍；兩者共同構成兵力規模的變化。這項分解說明成就如何呈現在數字上，但不直接證明哪些政策造成了人口成長。")
    peak=f"有紀錄年份中的最高戰力為{b['peak_power']:,}，首次達到於第{b['peak_year']:,}年。書中年表只保留重要節點；程式每個運行年均追蹤高峰，不限於年表節點。若有觀測缺口，不能排除缺口內曾出現更高戰力。"
    decline=(f"首次符合持續明顯衰退條件的起點為第{b['decline_year']:,}年：名義戰力降至此前高峰的80%以下，並連續維持至少5年。這表示曾出現衰退，不代表後來一定無法恢復。" if b.get('decline_year') is not None else '觀測期間沒有確認持續至少5年的明顯戰力衰退。短期下跌仍可能存在；這也不等於從未遭遇危機。')
    change=f"從觀測起點到終點，戰力{a['power']:,}→{z['power']:,}（{pct(z['power'],a['power']):+.1f}%），人口{a['pop']:,}→{z['pop']:,}（{pct(z['pop'],a['pop']):+.1f}%）；士兵比例{a['ratio']:.1%}→{z['ratio']:.1%}，每人存糧{a['buffer']:.1f}→{z['buffer']:.1f}。終點{'仍然存續' if z['alive'] else '已失去國家存續'}。"
    if a['power']>0 and z['power']>a['power']*1.2 and z['buffer']<a['buffer']*.5:
        inference='可供留意的是：軍力上升同時伴隨每人存糧明顯減少。後來的讀者應把軍備成長與供應壓力放在一起評估。'
    elif z['pop']>a['pop']*1.2:
        inference='人口擴大是這段歷程中可確認的變化。但人口、生產、聯盟、戰爭與外部局勢會共同影響結果，不能只憑最後名次把功勞歸給某一項政策。'
    else:inference='這段歷程沒有提供一條保證成功的公式。它提供的是帶有時代條件的經驗，讓後來者比較自己的處境，而不是照抄最後的兵力比例。'
    coverage=(f"這是屆中或該政權世代中途才開始的觀測，並非完整建國史。早於第{b['observed_start']:,}年的經歷未被補寫。" if partial else '這段觀測涵蓋本屆起點至目前結束位置；它仍然不是整個國家自最初建國起的完整歷史。')
    if b.get('gaps'):
        coverage+=' 另有未連續觀測的年份：'+'、'.join(f'{x}—{y}年' for x,y in b['gaps'])+'，不推定缺口中的事件。'
    rules='本書規則與目前AI參考版本一致。' if b.get('rules')==RULES else '本書來自不同規則版本，保留供玩家閱讀，AI不會套用其中的策略案例。'
    chapters=[('卷首｜一段道路的起點',[opening,ending]),('第一章｜起家的條件',[conditions,alliance,protection]),('第二章｜選擇如何累積',[road]+story),('第三章｜高峰與轉折',[peak,decline,change]),('第四章｜可供借鏡的觀察',[inference])]
    evidence=[]
    for i,c in enumerate(b.get('cases',[]),1):
        x,y=c['before'],c['after'];label='改善' if c['score']>.05 else '惡化' if c['score']<-.05 else '變化有限'
        immediate=c.get('immediate',{});effect=(f"當次長期軍備目標{x['target']:.1%}→{immediate['target']:.1%}。" if c.get('engine_action')==16 and 'target' in immediate else f"當次士兵{x['soldiers']:,}→{immediate['soldiers']:,}。" if c.get('engine_action') in (6,11) and 'soldiers' in immediate else '')
        evidence.append(f"案例{i}：第{x['year']:,}年，{x['name']}處於{x['role']}、本屆{x['phase']}，{'正在作戰' if x['wars'] else '未參戰'}，{'受保護' if x['protected'] else '無保護'}；實際執行「{ENGINE_LABEL(c)}」。{effect}其後{c['observed_years']}年，戰力{x['power']:,}→{y['power']:,}、人口{x['pop']:,}→{y['pop']:,}、每人存糧{x['buffer']:.1f}→{y['buffer']:.1f}。綜合觀測{label}（分數{c['score']:+.3f}）。這段期間可能有其他決策與事件，不能將全部結果單獨歸因於這次行動。")
    chapters.append(('附卷一｜決策與後續證據',evidence or ['本書尚無已完成追蹤、可供AI借鏡的決策案例；可以閱讀歷史，但不憑空生成策略建議。']))
    timeline=[]
    for s in b.get('timeline',[]):
        timeline.append(f"第{s['year']:,}年｜{s['name']}：戰力{s['power']:,}，人口{s['pop']:,}，士兵{s['soldiers']:,}（{s['ratio']:.1%}），排名第{s['rank']}/{s['count']}；{'戰中' if s['wars'] else '未參戰'}；{s['alliance'] or '無聯盟'}。"+(f"最後記錄事件：{s['event']}" if s.get('event') else ''))
    chapters.append(('附卷二｜可核對的年表',timeline))
    feedback=b.get('feedback',{});good=sum(x.get('good',0) for x in feedback.values());bad=sum(x.get('bad',0) for x in feedback.values());neutral=sum(x.get('neutral',0) for x in feedback.values())
    chapters.append(('編者記｜紀錄的邊界',[coverage,f"本書刊行於第{year:,}年。刊行後的研習回顧：改善{good}次、惡化{bad}次、變化有限{neutral}次。這些是觀測結果，並非受控實驗的策略勝率。",rules,'本書由實際數據與規則模板編寫，未虛構人物動機、對話、未記錄的戰役或不可驗證的因果。冠軍也可能原本就占有優勢；閱讀時應同時比較起點與代價。']))
    return chapters

def ENGINE_LABEL(case):
    from world_library import ENGINE_NAMES
    return ENGINE_NAMES.get(case.get('engine_action'),ACTION_NAMES.get(case.get('action'),'未記錄行動'))

def render_book_text(book):
    chunks=[book['title'],f"{book['kind']}｜觀測 {book['observed_start']:,}—{book['observed_end']:,} 年｜第{book['season']}屆｜國家第{book['generation']}代"]
    for title,paragraphs in book_chapters(book):chunks.extend(['\n'+title]+paragraphs)
    return '\n\n'.join(chunks)

def render_html(books,readings=(),title='世界圖書館｜文明留下的經驗'):
    esc=html.escape;nav=[];body=[]
    for b in books:
        target=f"book-{b['id']}";nav.append(f'<a href="#{target}">{esc(b["title"])}</a>')
        sections=''.join('<section><h3>'+esc(t)+'</h3>'+''.join('<p>'+esc(p)+'</p>' for p in ps)+'</section>' for t,ps in book_chapters(b))
        body.append(f'<article id="{target}"><div class="eyebrow">{esc(b["kind"])} · 第{b["season"]}屆 · 觀測 {b["observed_start"]:,}—{b["observed_end"]:,} 年</div><h2>{esc(b["title"])}</h2>{sections}</article>')
    review_html=''.join('<p>'+esc(r['text'])+'</p>' for r in list(readings)[-50:])
    document='''<!doctype html><html lang="zh-Hant"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>__TITLE__</title><style>
:root{font-size:19px;color-scheme:light}*{box-sizing:border-box}body{margin:0;background:#f3efe5;color:#24382f;font-family:"Microsoft JhengHei","Noto Sans TC",sans-serif;line-height:1.95}header{background:#173e35;color:#f6f1df;padding:2.8rem 6vw}h1{font-size:2rem;margin:.2rem 0}header p{max-width:48rem;color:#dbe8db}main{display:grid;grid-template-columns:260px minmax(0,820px);gap:2.5rem;max-width:1200px;margin:auto;padding:2rem 1.5rem}nav{position:sticky;top:1rem;align-self:start;max-height:90vh;overflow:auto;font-size:.85rem}nav a{display:block;color:#265c4b;text-decoration:none;padding:.6rem;border-bottom:1px solid #d4d8cc}article{background:#fffdf7;padding:2.3rem;margin-bottom:2rem;border:1px solid #d7d9c8;border-radius:12px;scroll-margin-top:1rem}h2{line-height:1.5;font-size:1.65rem;margin:.5rem 0 1.6rem}h3{font-size:1.12rem;border-bottom:1px solid #d5d9c9;padding-bottom:.5rem;color:#456a50}p{overflow-wrap:anywhere}.eyebrow{font-size:.75rem;color:#697c65;letter-spacing:.05em}button{font:inherit;padding:.3rem .8rem;background:#fff9e9;border:1px solid #b7c8b5;border-radius:6px;color:#244b3e;cursor:pointer}.guide{white-space:pre-line;font-size:.92rem}footer{padding:1rem 6vw 3rem;color:#637566;font-size:.8rem}@media(max-width:850px){main{display:block;padding:1rem}nav{position:static;max-height:12rem;margin-bottom:1rem}article{padding:1.2rem}}@media print{nav,button{display:none}body{background:white;color:black}main{display:block;max-width:none;padding:0}header{background:white;color:black;padding:1rem}header p{color:black}article{border:0;padding:1rem 0;break-before:page}h3{break-after:avoid}p{orphans:3;widows:3}}
</style><header><div class="eyebrow" style="color:#c9d6b3">亂世演算 · 世界圖書館</div><h1>__TITLE__</h1><p>國家各有興亡，經驗可以留給後世。閱讀成就，也核對起點、代價與證據。</p><button onclick="document.documentElement.style.fontSize=(parseFloat(getComputedStyle(document.documentElement).fontSize)+1)+'px'">放大字級</button> <button onclick="document.documentElement.style.fontSize=Math.max(14,parseFloat(getComputedStyle(document.documentElement).fontSize)-1)+'px'">縮小字級</button> <button onclick="window.print()">列印／存為PDF</button></header><main><nav><a href="#guide">閱讀說明</a>__NAV__<a href="#readings">研習與回顧</a></nav><div><article id="guide"><h2>如何閱讀這座圖書館</h2><div class="guide">__GUIDE__</div></article>__BOOKS__<article id="readings"><h2>研習與回顧</h2>__READINGS__</article></div></main><footer>離線閱讀版。紀錄來自指定世界的實際觀測；成功相關性不等於已證明的因果。</footer></html>'''
    return document.replace('__TITLE__',esc(title)).replace('__NAV__',''.join(nav)).replace('__GUIDE__',esc(GUIDE)).replace('__BOOKS__',''.join(body)).replace('__READINGS__',review_html or '<p>尚無研習紀錄。</p>')

class LibraryReaderMixin:
    def setup_world_library(self):
        import tkinter as tk
        from tkinter import ttk,scrolledtext
        self.tab_library=ttk.Frame(self.left_notebook);self.left_notebook.add(self.tab_library,text=' 📚 世界圖書館 ')
        bar=ttk.Frame(self.tab_library);bar.pack(fill='x',padx=8,pady=6)
        self.library_kind=tk.StringVar(value='全部藏書');self.library_filter=ttk.Combobox(bar,textvariable=self.library_kind,values=('全部藏書','冠軍成就','成長與復甦','失敗與興亡'),state='readonly',width=13);self.library_filter.pack(side='left')
        self.library_search=tk.StringVar();ttk.Entry(bar,textvariable=self.library_search,width=16).pack(side='left',padx=4)
        ttk.Button(bar,text='搜尋',command=lambda:self.refresh_world_library(True)).pack(side='left')
        ttk.Button(bar,text='閱讀說明',command=self.show_library_guide).pack(side='left',padx=4)
        self.library_status=ttk.Label(self.tab_library,text='等待觀測資料；下一次屆末將出版冠軍之書。');self.library_status.pack(fill='x',padx=8)
        self.library_list=ttk.Treeview(self.tab_library,columns=('title','kind','year'),show='headings',height=5,selectmode='browse')
        for name,label,width in [('title','書名',370),('kind','書架',110),('year','出版年',90)]:self.library_list.heading(name,text=label);self.library_list.column(name,width=width,minwidth=60)
        list_frame=ttk.Frame(self.tab_library);list_frame.pack(fill='x',padx=8,pady=4)
        self.library_list.pack(in_=list_frame,side='left',fill='both',expand=True)
        scrollbar=ttk.Scrollbar(list_frame,orient='vertical',command=self.library_list.yview);scrollbar.pack(side='right',fill='y');self.library_list.configure(yscrollcommand=scrollbar.set)
        self.library_list.bind('<<TreeviewSelect>>',self.read_library_book)
        self.library_filter.bind('<<ComboboxSelected>>',lambda e:self.refresh_world_library(True))
        toolbar=ttk.Frame(self.tab_library);toolbar.pack(fill='x',padx=8,pady=3)
        ttk.Button(toolbar,text='匯出本書 HTML',command=lambda:self.export_library(False)).pack(side='left')
        ttk.Button(toolbar,text='匯出全部 HTML',command=lambda:self.export_library(True)).pack(side='left',padx=4)
        ttk.Button(toolbar,text='研習與成效回顧',command=self.show_library_readings).pack(side='left')
        ttk.Button(toolbar,text='字＋',command=lambda:self.resize_library_font(1)).pack(side='right');ttk.Button(toolbar,text='字－',command=lambda:self.resize_library_font(-1)).pack(side='right')
        self.library_text=scrolledtext.ScrolledText(self.tab_library,wrap='word',font=('Microsoft JhengHei',13),bg='#fffdf5',fg='#24382f',padx=16,pady=12)
        self.library_text.pack(fill='both',expand=True,padx=8,pady=(3,8));self.library_text.tag_configure('heading',font=('Microsoft JhengHei',15,'bold'),foreground='#285442',spacing1=14,spacing3=5)
        self._library_font_size=13;self._library_data={};self._library_stamp=None;self._library_read_id=None;self._library_mode='guide';self._library_body_revision=None
        self.show_library_guide()
    def _library_set_text(self,text):
        self.library_text.configure(state='normal');self.library_text.delete('1.0','end');self.library_text.insert('1.0',text);self.library_text.configure(state='disabled');self.library_text.yview_moveto(0)
    def show_library_guide(self):
        self._library_mode='guide';self._library_set_text(GUIDE)
    def resize_library_font(self,amount):
        self._library_font_size=max(10,min(24,self._library_font_size+amount));self.library_text.configure(font=('Microsoft JhengHei',self._library_font_size));self.library_text.tag_configure('heading',font=('Microsoft JhengHei',self._library_font_size+2,'bold'))
    def refresh_world_library(self,force=False):
        path=self._library_file_path
        try:
            stat=os.stat(path);stamp=(stat.st_mtime_ns,stat.st_size)
            if stamp==self._library_stamp and not force:return
            if stat.st_size>20_000_000:raise ValueError('圖書館檔案超過20MB讀取上限')
            with open(path,encoding='utf-8') as f:data=json.load(f)
            if data.get('schema')!=SCHEMA:raise ValueError('圖書館格式不相容')
            self._library_data=data;self._library_stamp=stamp
        except FileNotFoundError:
            self.library_status.configure(text='尚未建立圖書館。引擎開始觀測後，每10年保存；下一次屆末出版冠軍之書。');return
        except (OSError,ValueError,TypeError) as exc:
            self.library_status.configure(text=f'暫時無法讀取圖書館：{exc}');return
        all_books=self._library_data.get('books',[]);query=self.library_search.get().strip().casefold();kind=self.library_kind.get()
        books=[b for b in reversed(all_books) if (kind=='全部藏書' or b['kind']==kind) and (not query or query in (b['title']+b['country']).casefold())]
        ids={str(b['id']) for b in books}
        for item in self.library_list.get_children():
            if item not in ids:self.library_list.delete(item)
        for idx,b in enumerate(books):
            item=str(b['id']);values=(b['title'],b['kind'],f"{b['published_year']:,}")
            if self.library_list.exists(item):self.library_list.item(item,values=values)
            else:self.library_list.insert('','end',iid=item,values=values)
            self.library_list.move(item,'',idx)
        stats=self._library_data.get('stats',{});self.library_status.configure(text=f"藏書 {len(all_books)}/{MAX_BOOKS} 本｜觀測至第{self._library_data.get('last_year',0):,}年｜研習 {stats.get('adoptions',0)} 次／完成回顧 {stats.get('reviews',0)} 次")
        # Keep the open book and exact reading position stable while the simulation runs.
        if self._library_mode=='book' and not any(str(b['id'])==str(self._library_read_id) for b in all_books):
            self.library_status.configure(text='目前閱讀的著作已被新書替換；正文保留，可先匯出留存。')
    def read_library_book(self,event=None):
        chosen=self.library_list.selection()
        if not chosen:return
        book=next((b for b in self._library_data.get('books',[]) if str(b['id'])==chosen[0]),None)
        if not book:return
        if self._library_mode=='book' and self._library_read_id==book['id']:return
        self._library_read_id=book['id'];self._library_open_book=book;self._library_mode='book'
        view=self.library_text;view.configure(state='normal');view.delete('1.0','end');view.insert('end',book['title']+'\n\n','heading')
        for title,paragraphs in book_chapters(book):
            view.insert('end',title+'\n','heading')
            for p in paragraphs:view.insert('end',p+'\n\n')
        view.configure(state='disabled');view.yview_moveto(0)
    def show_library_readings(self):
        self._library_mode='reviews';readings=self._library_data.get('readings',[])
        self._library_set_text('研習與成效回顧\n\n'+'\n\n'.join(r['text'] for r in reversed(readings)) if readings else '尚無研習紀錄。需要先出版帶有完成追蹤案例的書籍，再由相近處境的國家自行選擇參考。')
    def export_library(self,all_books=False):
        from tkinter import filedialog,messagebox
        books=self._library_data.get('books',[]) if all_books else ([self._library_open_book] if self.__dict__.get('_library_open_book') else [])
        if not books:messagebox.showinfo('世界圖書館','請先選一本書，或等待實際觀測資料累積成書。',parent=self.root);return
        path=filedialog.asksaveasfilename(parent=self.root,title='匯出離線閱讀版',defaultextension='.html',initialfile='世界圖書館.html' if all_books else f"世界圖書館_卷{books[0]['id']}.html",filetypes=[('網頁閱讀檔','*.html')])
        if not path:return
        try:
            readings=[r for r in self._library_data.get('readings',[]) if all_books or r['book_id']==books[0]['id']]
            with open(path,'w',encoding='utf-8') as f:f.write(render_html(books,readings))
            messagebox.showinfo('匯出完成','已匯出完整正文與年表。以瀏覽器開啟即可離線閱讀，亦可列印為PDF。',parent=self.root)
        except OSError as exc:messagebox.showerror('匯出失敗',str(exc),parent=self.root)
