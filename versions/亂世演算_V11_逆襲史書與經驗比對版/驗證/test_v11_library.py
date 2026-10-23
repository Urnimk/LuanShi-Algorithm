"""V11 collection criteria, accounting, migration, temporal and contextual boundaries."""
import copy,json,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import world_library as w
from library_reader import render_book_text,render_html
from test_world_library import country,history

class CollectionTests(unittest.TestCase):
    def make_world(self):
        p={str(i):country(str(i),power=(10-i)*5000,soldiers=(10-i)*100) for i in range(10)}
        l=w.WorldLibrary('unused');l.observe(p,0,1,0,500);return l,p
    def season(self,l,p,update=None):
        for year in range(1,501):
            if update:update(year)
            for key,c in p.items():
                before=w.snapshot(key,c,year,p,500-year)
                l.record_decision(key,c,year,0,3,True,before)
            l.observe(p,year,1,0,500-year)
    def test_weak_champion_and_growth_have_exact_season_counts(self):
        l,p=self.make_world()
        def grow(y):
            for key,base,delta in [('9',5000,140),('8',10000,115)]:
                p[key].update(power=base+y*delta,soldiers=(base+y*delta)//50,pop_total=1000+y*4,food=10000+y*20)
        self.season(l,p,grow);b=l.settle_season('9',500,1)
        self.assertEqual(b['tag'],'弱國逆襲');self.assertTrue(b['complete_season']);self.assertEqual(b['decision_totals']['total'],500)
        self.assertEqual(sum(x['decision_totals']['total'] for x in b['blocks'].values()),500)
        growth=next(b for b in l.books if b['country']=='8' and b['kind']=='成長與復甦')
        self.assertEqual(growth['tag'],'弱國崛起');self.assertEqual(growth['start']['year'],0);self.assertEqual(growth['end']['year'],500)
        self.assertEqual(len(b['checkpoints']),6)
    def test_no_century_growth_publication_and_no_partial_growth(self):
        l,p=self.make_world()
        for y in (100,200,300,400):
            p['9'].update(power=200000,pop_total=5000,soldiers=4000);l.observe(p,y,1,0,500-y)
        self.assertFalse(l.books);l.observe(p,500,1,0,0);l.settle_season('0',500,1)
        self.assertFalse(any(b['kind']=='成長與復甦' for b in l.books))
    def test_equal_power_start_is_not_a_fake_underdog(self):
        p={str(i):country(str(i)) for i in range(100)}
        a=w.snapshot('0',p['0'],0,p);z=w.snapshot('99',p['99'],0,p)
        self.assertEqual(z['rank'],100);self.assertEqual(z['tied_rank'],1);self.assertEqual(z['tied_count'],100)
        self.assertEqual(z['rank_pct'],0);self.assertFalse(w.WorldLibrary._weak_start(z))
        self.assertGreater(w.origin_similarity(a,z),.78)

    def test_rank_only_growth_does_not_qualify(self):
        l,p=self.make_world()
        self.season(l,p)
        t=l.tracks['9'];t['last']=dict(t['last'],rank=1,rank_pct=0,relative=1)
        self.assertFalse(l._growth(t))
    def test_zero_or_negative_food_prevents_growth_book(self):
        l,p=self.make_world();t=l.tracks['9'];t['last']=dict(t['last'],power=100000,pop=5000,rank=1,rank_pct=0,relative=1,buffer=0)
        self.assertFalse(l._growth(t))
    def test_alive_decline_is_collected(self):
        l,p=self.make_world()
        def decline(y):
            p['0'].update(power=max(5000,50000-y*100),soldiers=max(100,1000-y*2))
        self.season(l,p,decline);l.settle_season('1',500,1)
        b=next(b for b in l.books if b['country']=='0' and b['kind']=='失敗與興亡')
        self.assertEqual(b['tag'],'存續中的衰退');self.assertTrue(b['end']['alive']);self.assertIn('仍存續但嚴重衰退',render_book_text(b))
    def test_death_history_crosses_seasons_but_never_exceeds_300(self):
        l,p=self.make_world()
        for y in range(1,651):
            if y==650:p['0'].update(is_alive=False,power=0,pop_total=0,soldiers=0)
            before=w.snapshot('0',p['0'],y,p,500-y if y<=500 else 1000-y)
            if y<650:l.record_decision('0',p['0'],y,0,3,True,before)
            l.observe(p,y,1 if y<=500 else 2,0 if y<=500 else 500,500-y if y<=500 else 1000-y)
        b=next(b for b in l.books if b['kind']=='失敗與興亡')
        self.assertEqual(b['observed_start'],350);self.assertEqual(b['observed_end'],650)
        self.assertEqual(b['decision_totals']['total'],299);self.assertEqual(b['window'],'覆亡前最多300年')
        self.assertEqual(b['peak_year'],350);self.assertEqual(b['peak_power'],50000)
    def test_weak_low_rank_death_is_not_priority_case(self):
        l,p=self.make_world()
        for y in range(1,11):l.observe(p,y,1,0,500-y)
        p['9'].update(is_alive=False,power=0);l.observe(p,11,1,0,489)
        self.assertFalse(any(b['country']=='9' for b in l.books))
    def test_generation_change_does_not_stitch_histories(self):
        l,p=self.make_world();l.observe(p,300,1,0,200)
        p['0']['country_generation']=2;l.observe(p,301,1,0,199)
        p['0']['is_alive']=False;l.observe(p,302,1,0,198)
        self.assertFalse(l.books);self.assertEqual(l.histories['0']['metrics'][0][0],301)
    def test_rolling_storage_is_bounded(self):
        l,p=self.make_world()
        for y in range(1,1201):
            before=w.snapshot('0',p['0'],y,p)
            l.record_decision('0',p['0'],y,0,3,True,before)
            season=(y-1)//500+1;start=(season-1)*500
            l.observe(p,y,season,start,500-(y-start))
        for h in l.histories.values():
            self.assertLessEqual(len(h['metrics']),301);self.assertLessEqual(len(h['points']),32);self.assertLessEqual(len(h['decisions']),300)
        self.assertEqual(l.tracks['0']['decision_totals']['total'],200)

class AccountingAndMatchingTests(unittest.TestCase):
    def test_attempts_failed_redirected_do_not_make_false_case(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,0,1,0,500)
        for year,success,matched in [(1,True,True),(2,False,True),(3,True,False)]:
            l.record_decision('a',p['a'],year,0,3,success,w.snapshot('a',p['a'],year,p),matched=matched)
        self.assertEqual(l.tracks['a']['decision_totals'],dict(total=3,success=2,failed=1,redirected=1))
        self.assertEqual(len(l.pending['a']),1)
    def test_first_decision_of_new_season_is_not_lost(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,500,1,0,0)
        l.record_decision('a',p['a'],501,0,3,True,w.snapshot('a',p['a'],501,p,499))
        l.observe(p,501,2,500,499)
        self.assertEqual(l.tracks['a']['season'],2);self.assertEqual(l.tracks['a']['start']['year'],500)
        self.assertEqual(l.tracks['a']['decision_totals']['total'],1)
    def test_first_action_of_rebuilt_generation_is_counted(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,100,1,0,400)
        p['a']['country_generation']=2
        l.record_decision('a',p['a'],101,0,3,True,w.snapshot('a',p['a'],101,p,399))
        l.observe(p,101,1,0,399)
        self.assertEqual(l.tracks['a']['decision_totals']['total'],1);self.assertEqual(l.tracks['a']['start']['generation'],2)
    def test_decision_cases_and_adoption_reviews_have_separate_horizons(self):
        self.assertEqual(w.CASE_YEARS,15);self.assertEqual(w.REVIEW_YEARS,200)
        l,b,p,before=history();self.assertTrue(b['cases']);advice=l.advise('a',country(),22,[2])
        l.record_decision('a',country(),22,2,6,True,w.snapshot('a',country(),22,l.peers),advice)
        self.assertEqual(l.adoptions['a']['due'],222)
    def test_rolling_book_counts_first_rebuilt_year(self):
        l=w.WorldLibrary('unused');p={'a':country()};l.observe(p,100,1,0,400)
        p['a']['country_generation']=2
        for y in range(101,110):
            l.record_decision('a',p['a'],y,0,3,True,w.snapshot('a',p['a'],y,p,500-y));l.observe(p,y,1,0,500-y)
        p['a']['is_alive']=False;l.observe(p,110,1,0,390)
        b=l.books[-1];self.assertEqual(b['decision_totals']['total'],9)

    def test_origin_mismatch_blocks_even_identical_current_conditions(self):
        l,b,p,before=history();self.assertTrue(l.advise('a',country(),22,[2]))
        l.tracks['a']['start']=dict(l.tracks['a']['start'],protected=True)
        self.assertFalse(l.advise('a',country(),22,[2]))
    def test_origin_similarity_is_a_separate_recorded_score(self):
        l,b,p,before=history();a=l.advise('a',country(),22,[2]);self.assertGreaterEqual(a['sources'][0]['origin_similarity'],.78)
        self.assertGreaterEqual(a['sources'][0]['similarity'],.8)
    def test_one_front_and_multiple_fronts_do_not_match(self):
        s=w.snapshot('a',country(current_wars=['a']),1)
        z=dict(s,wars=2);self.assertEqual(w.similarity(s,z),0);self.assertEqual(w.origin_similarity(s,z),0)
    def test_legacy_schema_keeps_readable_books_not_false_statistics(self):
        l,b,p,before=history();b.pop('evidence_edition');b.pop('decision_totals')
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'world_library.json';l.path=str(path);l.save(True);data=json.loads(path.read_text());data['schema']=1;path.write_text(json.dumps(data))
            g=w.WorldLibrary(path);g.load(21);self.assertEqual(len(g.books),1);self.assertFalse(g.index);self.assertFalse(g.tracks)
            self.assertIn('不補造缺少的統計',render_book_text(g.books[0]))
    def test_decision_totals_are_complete_and_html_escaped(self):
        l,b,p,before=history();b['selection_reason']='<script>unsafe</script>'
        text=render_book_text(b)
        for term in ['決策帳','百年分期','同戰力並列百分位','適合誰讀','入選原因']:self.assertIn(term,text)
        self.assertIn('&lt;script&gt;unsafe',render_html([b]));self.assertEqual(b['decision_totals']['total'],1)

if __name__=='__main__':unittest.main()
