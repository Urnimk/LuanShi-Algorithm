import copy,json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import world_library as w
import library_paths as p
from library_reader import render_book_text,render_html
from test_world_library import country

def book(kind='冠軍成就',failure=False):
    points=[]
    for i in range(6):
        c=country('教材國',power=5000+i*3000,pop_total=1000+i*200,soldiers=100+i*60,food=(1000+i*200)*8,military_target_ratio=.25+max(0,i-2)*.03)
        s=w.snapshot('hero',c,i*100,{'hero':c,'top':country('大國',power=50000,soldiers=1000)},500-i*100)
        points.append(s)
    blocks={str(i):dict(actions=({'鼓勵生育':60,'調整產業配置':30,'基礎建設投資':10} if i<3 else {'戰時動員':65,'長期軍備規劃':25,'調整產業配置':10}),attempts={},decision_totals={'total':100,'success':100,'failed':0,'redirected':0}) for i in range(5)}
    if failure:
        kind='失敗與興亡'
        for i,s in enumerate(points):s.update(power=20000-i*3000,relative=.4-i*.06,ratio=.4-i*.05,target=.4-i*.03)
        points[-1].update(alive=False,power=0,pop=0,soldiers=0)
        blocks={str(i):dict(actions={'發動戰爭':60,'裁軍休養':30,'戰時動員':10},attempts={},decision_totals={}) for i in range(5)}
    return dict(id=1,country='hero',generation=1,title='教材國：'+kind,kind=kind,season=1,published_year=500,
                evidence_edition=2,rules=w.RULES,start=points[0],end=points[-1],observed_start=0,observed_end=500,
                complete_season=True,season_start=0,partial=False,gaps=[],blocks=blocks,checkpoints=points,timeline=points,
                cases=[],actions={'鼓勵生育':180},attempts={},decision_totals={'total':500,'success':500,'failed':0,'redirected':0},
                peak_power=20000,peak_year=500,decline_year=350 if failure else None,feedback={})

def learner(b=None,elapsed=20):
    b=b or book();l=w.WorldLibrary('unused');l.books=[b]
    origin=copy.deepcopy(b['start']);key='learner'
    original=country('學習國',power=origin['power'],pop_total=origin['pop'],soldiers=origin['soldiers'],food=origin['food'],military_target_ratio=origin['target'])
    peers={key:original,'top':country('大國',power=50000,soldiers=1000)}
    l.observe(peers,1000,3,1000,500)
    # Keep the current situation close to the actual start-of-century anchor.
    anchor=b['checkpoints'][min(4,elapsed//100)]
    c=country('學習國',power=anchor['power'],pop_total=max(1,anchor['pop']),soldiers=anchor['soldiers'],food=anchor['food'],military_target_ratio=anchor['target'],season_years_remaining=500-elapsed)
    peers[key]=c;l.bind(peers);l._reindex()
    return l,c,1000+elapsed

class PathLearningTests(unittest.TestCase):
    def test_success_path_prefers_growth_early_and_military_late(self):
        l,c,y=learner(elapsed=20);early=l.advise('learner',c,y,list(range(13)));self.assertGreater(early['bias'][7],early['bias'].get(2,0))
        l,c,y=learner(elapsed=420);late=l.advise('learner',c,y,list(range(13)));self.assertGreater(late['bias'][2],late['bias'].get(7,0));self.assertTrue(late['military_bias'])
    def test_short_negative_episode_cannot_reverse_a_champion(self):
        b=book();x=dict(b['start'],year=1);z=dict(x,year=16,power=1000,buffer=0);b['cases']=[dict(before=x,after=z,action=7,score=-1,observed_years=15)]
        l,c,y=learner(b);a=l.advise('learner',c,y,[7,1]);self.assertGreater(a['bias'][7],0);self.assertTrue(all(s['direction']=='learn' for s in a['sources']))
    def test_growth_books_also_teach_positive_paths(self):
        l,c,y=learner(book('成長與復甦'));a=l.advise('learner',c,y,[7]);self.assertGreater(a['bias'][7],0)
    def test_bad_overall_outcome_does_not_become_growth_template(self):
        b=book('成長與復甦');b['end']=dict(b['end'],power=100,pop=500)
        self.assertFalse(p.build_path(b)['eligible'])
    def test_champion_title_does_not_make_partial_history_a_full_path(self):
        b=book();b['complete_season']=False;l,c,y=learner(b);self.assertFalse(l.advise('learner',c,y,[7]))
    def test_missing_century_counts_cannot_be_invented(self):
        b=book();b['blocks']={};self.assertFalse(p.build_path(b)['eligible'])
    def test_failure_books_never_promote_actions(self):
        b=book(failure=True);l,c,y=learner(b);a=l.advise('learner',c,y,[5,11,2,7]);self.assertTrue(a)
        self.assertTrue(all(v<=0 for v in a['bias'].values()));self.assertTrue(all(s['direction']=='avoid' for s in a['sources']))
    def test_failure_does_not_label_all_actions_as_bad(self):
        b=book(failure=True);l,c,y=learner(b);a=l.advise('learner',c,y,list(range(13)))
        self.assertNotIn(7,a['bias']);self.assertNotIn(3,a['bias']);self.assertNotIn(2,a['bias'])
    def test_emergency_demobilization_is_not_suppressed_by_failure(self):
        b=book(failure=True);path=p.build_path(b);s=dict(b['start'],buffer=0,fatigue=90)
        vec,reasons=p.vectors(b,path,path['stages'][0],s);self.assertNotIn(11,vec)
    def test_ample_food_spending_is_not_a_negative_outcome(self):
        a=book()['start'];z=dict(a,buffer=18,power=a['power']+100,pop=a['pop']+100);a=dict(a,buffer=22)
        self.assertGreater(w.outcome(a,z),0)
    def test_legal_actions_and_future_publications_are_guarded(self):
        l,c,y=learner();self.assertFalse(l.advise('learner',c,y,[9]));l.books[0]['published_year']=y;l._reindex();self.assertFalse(l.advise('learner',c,y,[7]))
    def test_future_internal_endpoints_cannot_leak(self):
        b=book();b['published_year']=499;self.assertFalse(p.build_path(b)['eligible'])

    def test_origin_and_current_conditions_both_must_match(self):
        l,c,y=learner();self.assertTrue(l.advise('learner',c,y,[7]));l.tracks['learner']['start']['protected']=True
        self.assertFalse(l.advise('learner',c,y,[7]))
        l,c,y=learner();c['current_wars']=['w'];self.assertFalse(l.advise('learner',c,y,[7]))
    def test_same_history_republished_does_not_double_weight(self):
        l,c,y=learner();a=l.advise('learner',c,y,[7]);clone=copy.deepcopy(l.books[0]);clone['id']=2;l.books.append(clone);l._reindex()
        b=l.advise('learner',c,y,[7]);self.assertEqual(a['bias'],b['bias']);self.assertEqual(len(b['sources']),1)
    def test_any_different_action_is_not_a_negative_adoption(self):
        l,c,y=learner(book(failure=True));a=l.advise('learner',c,y,[5,7]);self.assertLess(a['bias'][5],0)
        l.record_decision('learner',c,y,7,12,True,l.decision_snapshot('learner',c,y),a)
        self.assertFalse(l.adoptions);self.assertFalse(l.readings)
    def test_negative_adoption_requires_real_preference_set_change(self):
        l,c,y=learner(book(failure=True));a=l.advise('learner',c,y,[5,7]);a['selection_effect']=dict(exploring=False,best_set_changed=True,baseline_best=[5])
        l.record_decision('learner',c,y,7,12,True,l.decision_snapshot('learner',c,y),a)
        self.assertEqual(l.adoptions['learner']['mode'],'避開衰亡路徑風險');self.assertIn('主動戰爭',l.readings[-1]['text'])
    def test_exploration_does_not_get_false_adoption_credit(self):
        l,c,y=learner();a=l.advise('learner',c,y,[7]);a['selection_effect']=dict(exploring=True,best_set_changed=True,baseline_best=[1])
        l.record_decision('learner',c,y,7,12,True,l.decision_snapshot('learner',c,y),a);self.assertFalse(l.adoptions)
    def test_positive_adoption_and_200_year_review_are_path_based(self):
        l,c,y=learner();a=l.advise('learner',c,y,[7]);old=a['bias'][7]
        l.record_decision('learner',c,y,7,12,True,l.decision_snapshot('learner',c,y),a)
        self.assertEqual(l.adoptions['learner']['due'],y+200);self.assertIn('成功路徑',l.readings[-1]['text'])
        death=l.decision_snapshot('learner',dict(c,is_alive=False),y+1);l._review('learner',death)
        self.assertFalse(l.adoptions);self.assertEqual(l.stats['reviews'],1);self.assertEqual(l.readings[-1]['learning_model'],p.MODEL)
        self.assertLess(l.advise('learner',c,y+30,[7])['bias'][7],old)
    def test_neutral_feedback_reduces_path_weight(self):
        l,c,y=learner();a=l.advise('learner',c,y,[7]);sid=a['sources'][0]['case_id'];context=l._context(a['context']);l.case_feedback[sid]={context:dict(good=0,bad=0,neutral=100)}
        self.assertLess(l.advise('learner',c,y,[7])['bias'][7],a['bias'][7])
    def test_neutral_feedback_is_context_specific(self):
        l,c,y=learner();a=l.advise('learner',c,y,[7]);sid=a['sources'][0]['case_id'];l.case_feedback[sid]={'unrelated':dict(good=0,bad=100)}
        self.assertEqual(l.advise('learner',c,y,[7])['bias'],a['bias'])
    def test_boundary_episode_is_excluded_from_next_season_book(self):
        b=book();x=dict(b['start'],year=0,remaining=1,phase='決勝期');z=dict(x,year=15)
        b['cases']=[dict(before=x,after=z,action=2,score=-.1)];l,c,y=learner(b);self.assertFalse(l.books[0]['cases'])
    def test_decision_time_remaining_is_not_last_year_value(self):
        l,c,y=learner(elapsed=20);c['season_years_remaining']=481
        self.assertEqual(l.decision_snapshot('learner',c,y)['remaining'],480)
    def test_schema2_migration_keeps_accounts_but_ends_old_adoptions(self):
        with tempfile.TemporaryDirectory() as d:
            path=Path(d)/'world_library.json';b=book();b['feedback']={'old':dict(good=0,bad=99)}
            path.write_text(json.dumps(dict(schema=2,rules=w.RULES,last_year=1000,books=[b],adoptions={'old':dict(before=b['start'])})))
            l=w.WorldLibrary(path);l.load(1000);self.assertFalse(l.adoptions);self.assertTrue(l.index);self.assertIn('legacy_feedback',l.books[0]);self.assertEqual(l.books[0]['blocks'],b['blocks'])
    def test_save_reload_keeps_new_path_feedback_and_adoption(self):
        with tempfile.TemporaryDirectory() as d:
            l,c,y=learner();l.path=str(Path(d)/'x.json');a=l.advise('learner',c,y,[7]);l.record_decision('learner',c,y,7,12,True,l.decision_snapshot('learner',c,y),a)
            l.last_year=y;l.dirty=True;l.save(True);g=w.WorldLibrary(l.path);g.load(y);self.assertEqual(g.adoptions,l.adoptions)
    def test_reader_shows_all_three_levels(self):
        b=book();text=render_book_text(b)
        for t in ['主要｜','其次｜','輔助｜','整體路徑','單次15年']:self.assertIn(t,text)
        self.assertIn('學習提要',render_html([b]))

if __name__=='__main__':unittest.main()
