import copy,importlib.util,json,os,random,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import world_library as w
from library_reader import book_chapters,render_book_text,render_html,LibraryReaderMixin

def country(name='甲國',**kw):
    d=dict(display_name=name,country_generation=1,is_alive=True,pop_total=1000,soldiers=100,power=5000,food=5000,fortification=30,war_exhaustion=0,political_stability=75,military_target_ratio=.25,current_wars=[],current_alliance='',season_years_remaining=450)
    d.update(kw);return d

def history(path='unused.json'):
    l=w.WorldLibrary(path);a=country();peers={'a':a,'b':country('乙國',power=50000,soldiers=1000)}
    l.observe(peers,0,1,0,500)
    before=w.snapshot('a',a,1,peers,499)
    l.record_decision('a',a,1,2,6,True,before)
    for year in range(2,22):
        a.update(pop_total=1000+year*30,power=5000+year*500,soldiers=100+year*10,food=5000+year*800)
        l.observe(peers,year,1,0,500-year)
    b=l.settle_season('a',21,1)
    return l,b,peers,before

class LibraryTests(unittest.TestCase):
    def test_same_year_unpublished_case_cannot_leak(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,1,1,0,499);before=w.snapshot('a',p['a'],1,p)
        l.record_decision('a',p['a'],1,2,6,True,before);self.assertFalse(l.completed.get('a'))
        l.observe(p,15,1,0,485);self.assertFalse(l.completed.get('a'))
        l.observe(p,16,1,0,484);self.assertEqual(len(l.completed['a']),1)
    def test_illegal_actions_never_advised(self):
        l,b,peers,before=history();self.assertFalse(l.advise('a',country(),22,[0]))
    def test_different_war_protection_and_phase_rejected(self):
        l,b,peers,before=history()
        for change in [dict(current_wars=['W1']),dict(protection_remaining_years=10),dict(season_years_remaining=10)]:
            self.assertFalse(l.advise('a',country(**change),22,[2]),change)
    def test_extreme_different_conditions_rejected(self):
        l,b,peers,before=history();other=country(food=0,war_exhaustion=100,fortification=100,military_target_ratio=.5,soldiers=500)
        self.assertFalse(l.advise('a',other,22,[2]))
    def test_rules_mismatch_readable_but_not_learned(self):
        l,b,peers,before=history();b['rules']='old';l._reindex();self.assertFalse(l.advise('a',country(),22,[2]));self.assertIn('不同規則',render_book_text(b))
    def test_failed_execution_does_not_create_adoption(self):
        l,b,peers,before=history();advice=l.advise('a',country(),22,[2]);l.record_decision('a',country(),22,2,6,False,before,advice);self.assertNotIn('a',l.adoptions)
    def test_archive_and_timelines_bounded(self):
        l,b,peers,before=history();l.books=[]
        for i in range(160):
            x=copy.deepcopy(b);x['id']=i;x['kind']=['冠軍成就','成長與復甦','失敗與興亡'][i%3];l.books.append(x)
        l._bound();self.assertLessEqual(len(l.books),w.MAX_BOOKS)
        points=[dict(b['start'],year=i,power=100000 if i==37 else i) for i in range(500)]
        result=w.thin(points,24);self.assertEqual(len(result),24);self.assertEqual(result[0]['year'],0);self.assertEqual(result[-1]['year'],499);self.assertTrue(any(x['year']==37 for x in result))
    def test_save_reload_preserves_pending_and_archive(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'library.json');l,b,peers,before=history(p);l.save(True)
            g=w.WorldLibrary(p);g.load(21);self.assertEqual(g.books,l.books);self.assertEqual(g.pending,l.pending);self.assertEqual(g.last_year,21)
    def test_rollback_cannot_retain_future_books_or_trackers(self):
        with tempfile.TemporaryDirectory() as d:
            p=str(Path(d)/'library.json');l,b,peers,before=history(p);l.save(True)
            g=w.WorldLibrary(p);g.load(10);self.assertFalse(g.books);self.assertFalse(g.tracks);self.assertEqual(g.last_year,10);self.assertGreaterEqual(g.seq,b['id'])
    def test_broken_library_does_not_touch_world(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'library.json';p.write_text('{broken');l=w.WorldLibrary(p);l.load(10);self.assertFalse(l.books);self.assertTrue(l.error)
    def test_disabled_library_has_no_observations_or_rng_effect(self):
        state=random.getstate();l=w.WorldLibrary('unused',enabled=False);c={'a':country()};old=copy.deepcopy(c)
        l.observe(c,100,1,0,400);self.assertFalse(l.tracks);self.assertFalse(l.advise('a',c['a'],100,[2]));self.assertEqual(c,old);self.assertEqual(state,random.getstate())
    def test_missing_early_years_are_not_backfilled(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,300,1,0,200);l.observe(p,500,1,0,0);b=l.settle_season('a',500,1)
        self.assertTrue(b['partial']);text=render_book_text(b);self.assertIn('並非完整建國史',text);self.assertEqual(b['observed_start'],300)
    def test_death_book_uses_actual_record(self):
        l=w.WorldLibrary('unused');p={'a':country()}
        for y in range(1,8):l.observe(p,y,1,0,500-y)
        p['a'].update(is_alive=False,pop_total=0,power=0,soldiers=0);l.observe(p,8,1,0,492)
        self.assertEqual(l.books[-1]['kind'],'失敗與興亡');self.assertFalse(l.books[-1]['end']['alive']);self.assertIn('國家滅亡',render_book_text(l.books[-1]))
    def test_five_year_decline_confirmation(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,0,1,0,500)
        for y in range(1,5):p['a']['power']=3000;l.observe(p,y,1,0,500-y)
        self.assertIsNone(l.tracks['a']['decline_year']);l.observe(p,5,1,0,495);self.assertEqual(l.tracks['a']['decline_year'],1)
    def test_book_has_evidence_and_no_causal_guarantee(self):
        l,b,peers,before=history();text=render_book_text(b)
        for word in ['起家的條件','高峰與轉折','決策與後續證據','年表','不能','每人存糧','觀測期間']:self.assertIn(word,text)
        self.assertGreater(len(text),1000)
    def test_export_is_offline_escaped_and_printable(self):
        l,b,peers,before=history();b['title']='<script>alert(1)</script>';doc=render_html([b])
        self.assertIn('&lt;script&gt;',doc);self.assertNotIn('<script>alert',doc);self.assertNotIn('https://',doc);self.assertIn('@media print',doc);self.assertIn('viewport',doc)
    def test_cases_keep_different_phases_and_directions(self):
        l,b,peers,before=history();case=b['cases'][0];cases=[]
        for i in range(40):
            x=copy.deepcopy(case);x['before']['year']=i;x['action']=i%13;x['before']['phase']=['前段','中段','後段','決勝期'][i%4];x['score']=.2 if i%2 else -.5;cases.append(x)
        keep=l._retain_cases(cases);self.assertLessEqual(len(keep),w.MAX_CASES);self.assertTrue(any(x['score']<0 for x in keep));self.assertTrue(any(x['score']>0 for x in keep))

class SelectionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec=importlib.util.spec_from_file_location('library_test_engine',ROOT/(ROOT.name+'.py'));cls.e=importlib.util.module_from_spec(spec);spec.loader.exec_module(cls.e)
    def test_advice_changes_selection_without_changing_q_or_mask(self):
        # Use a real policy instance from the existing agent, avoiding a duplicate policy implementation.
        agent=self.e.CountryRLAgent('測試');p=agent.strategic_policy;state=('x',);q=p._ensure(p.state_key(state));q[0]=.01;q[2]=0;before=list(q)
        with patch.object(p,'effective_epsilon',return_value=0),patch.object(self.e.random,'random',return_value=.99):
            self.assertEqual(p.choose(state,[0,2],advice={2:.18,5:999}),2)
        self.assertEqual(q,before)
    def test_large_advice_is_clamped(self):
        agent=self.e.CountryRLAgent('測試');p=agent.strategic_policy;state=('x',);q=p._ensure(p.state_key(state));q[0]=1
        with patch.object(p,'effective_epsilon',return_value=0),patch.object(self.e.random,'random',return_value=.99):self.assertEqual(p.choose(state,[0,2],advice={2:9999}),0)
    def test_exploration_is_retained(self):
        agent=self.e.CountryRLAgent('測試');p=agent.strategic_policy;state=('x',)
        with patch.object(p,'effective_epsilon',return_value=1),patch.object(self.e.random,'choice',side_effect=lambda xs:xs[0]):self.assertEqual(p.choose(state,[0,2],advice={2:.18}),0)


class AdditionalEvidenceTests(unittest.TestCase):
    # V12 path feedback tests live in test_path_learning.py.
    def test_gap_does_not_invent_five_year_continuous_decline(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,0,1,0,500);p['a']['power']=2000;l.observe(p,1,1,0,499);l.observe(p,10,1,0,490)
        self.assertIsNone(l.tracks['a']['decline_year']);self.assertEqual(l.tracks['a']['gaps'],[[2,9]])
    def test_unknown_countries_do_not_grow_runtime_tables(self):
        l,b,peers,before=history();l.record_decision('unknown',country(),22,2,6,True,before);self.assertNotIn('unknown',l.pending);self.assertFalse(l.advise('unknown',country(),22,[2]))

class ReaderTests(unittest.TestCase):
    def test_live_refresh_preserves_book_body_and_reading_position(self):
        from types import SimpleNamespace
        class Value:
            def __init__(self,v):self.v=v
            def get(self):return self.v
            def configure(self,**kw):self.options=kw
        class Tree:
            def __init__(self):self.rows={};self.chosen=[]
            def get_children(self):return list(self.rows)
            def exists(self,item):return item in self.rows
            def insert(self,*a,iid,values):self.rows[iid]=values
            def item(self,item,values=None):
                if values:self.rows[item]=values
            def delete(self,item):self.rows.pop(item)
            def move(self,*a):pass
            def selection(self):return self.chosen
        class Text:
            def __init__(self):self.body='';self.top=.35;self.deletes=0
            def configure(self,**kw):pass
            def delete(self,*a):self.body='';self.deletes+=1
            def insert(self,index,text,*args):self.body+=text
            def yview_moveto(self,y):self.top=y
        class View(LibraryReaderMixin):pass
        with tempfile.TemporaryDirectory() as d:
            path=str(Path(d)/'world_library.json');l,b,peers,before=history(path);l.save(True)
            v=View();v._library_file_path=path;v._library_stamp=None;v._library_data={};v.library_kind=Value('全部藏書');v.library_search=Value('');v.library_status=Value('');v.library_list=Tree();v.library_text=Text();v._library_mode='guide';v._library_read_id=None
            v.refresh_world_library();v.library_list.chosen=[str(b['id'])];v.read_library_book();body=v.library_text.body;v.library_text.top=.35;deletes=v.library_text.deletes
            clone=copy.deepcopy(b);clone['id']+=1;clone['title']='新書';l.books.append(clone);l.last_year=30;l.dirty=True;l.save(True);v.refresh_world_library()
            self.assertEqual(v.library_text.body,body);self.assertEqual(v.library_text.top,.35);self.assertEqual(v.library_text.deletes,deletes)
            self.assertEqual(len(v.library_list.rows),2)

if __name__=='__main__':unittest.main()
