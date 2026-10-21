import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import country_history as h
from strategy_states import strategic_state_256

def entry(name,start,end=None,reason='',peak=500,peakyear=5,generation=1):
    return dict(name=name,start_year=start,end_year=end,end_reason=reason,
                peak_power=peak,peak_power_year=peakyear,generation=generation,
                regime_type='正統政權',ended_by='敵國' if reason=='滅國' else '')

def country(history=None):
    return dict(display_name='試驗國',is_alive=True,power=500,soldiers=10,pop_total=100,
                military_target_ratio=.3,country_chronicle=history or [entry('試驗國',1)])

class HistoryTests(unittest.TestCase):
    def tearDown(self):h.flush(close=True)

    def test_lifetimes_do_not_end_at_succession_or_coup(self):
        c=country([entry('甲',1,10,'正統交接'),entry('甲二世',10,20,'政變'),
                   entry('乙',20,30,'滅國'),entry('乙II',36)])
        groups=h.periods(c)
        self.assertEqual([len(g) for g in groups],[3,1])
        self.assertEqual(h.identity('a',groups[0])[1],1)

    def test_no_fabricated_decline_from_old_peak(self):
        c=country([entry('甲',1,10,'滅國',1000,7)])
        with tempfile.TemporaryDirectory() as tmp:
            report=h.render_report('a',c,tmp)
        self.assertIn('第7年',report)
        self.assertIn('沒有逐年觀測資料',report)
        self.assertNotIn('起點是第7年',report)

    def test_cap_baseline_plus_1000_years_and_extinction_endpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            h.configure(tmp);c=country();cs={'a':c};before=copy.deepcopy(c)
            h.begin(cs);h.annual(cs,0,'INITIAL',500)
            for t in range(1,1005):h.begin(cs);h.annual(cs,t,'EARLY',400)
            h.begin(cs);c['is_alive']=False;c['soldiers']=0
            c['country_chronicle'][0].update(end_year=1005,end_reason='滅國')
            h.annual(cs,1005,'LATE',5);h.flush()
            rows=h.read_rows(h.path_for(tmp,'a',h.periods(c)[0]))
            self.assertEqual(len(rows),1002)
            self.assertEqual(rows[-1]['year'],1005)
            self.assertFalse(rows[-1]['alive'])
            self.assertEqual(len(h._handles),0)
            self.assertEqual(c['military_target_ratio'],before['military_target_ratio'])

    def test_same_year_reload_does_not_duplicate(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=country();cs={'a':c}
            for _ in range(2):
                h.configure(tmp);h.begin(cs);h.annual(cs,10,'EARLY',400);h.flush()
            self.assertEqual(len(h.read_rows(h.path_for(tmp,'a',h.periods(c)[0]))),1)

    def test_rollback_preserves_old_future_separately(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=country();cs={'a':c}
            h.configure(tmp)
            for t in (10,11,12):h.begin(cs);h.annual(cs,t,'EARLY',400)
            h.configure(tmp);h.begin(cs);h.annual(cs,11,'EARLY',400);h.flush()
            self.assertEqual([r['year'] for r in h.read_rows(h.path_for(tmp,'a',h.periods(c)[0]))],[10,11])
            self.assertEqual(len(list(Path(tmp).glob('*.branch-*.jsonl'))),1)

    def test_observation_keeps_population_dilution_separate(self):
        rows=[dict(year=1,power=500,alive=True,ratio=.1,soldiers=10,
                   before=dict(ratio=.2,soldiers=10),events=[])]
        a=h.analyse(rows)
        self.assertEqual(a['dilution'],[1]);self.assertEqual(a['demobs'],[])

    def test_interrupted_tail_is_preserved_and_append_recovers(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=country();cs={'a':c};h.configure(tmp)
            h.begin(cs);h.annual(cs,10,'EARLY',400);h.flush(close=True)
            path=h.path_for(tmp,'a',h.periods(c)[0])
            with path.open('ab') as f:f.write(b'{"year":11,')
            h.configure(tmp);h.begin(cs);h.annual(cs,11,'EARLY',399);h.flush()
            self.assertEqual([r['year'] for r in h.read_rows(path)],[10,11])
            self.assertEqual(len(list(Path(tmp).glob('*.interrupted.bin'))),1)

    def test_decline_needs_consecutive_observed_years(self):
        rows=[dict(year=1,power=1000,alive=True)]+[dict(year=t,power=700,alive=True) for t in range(2,12)]
        self.assertEqual(h.analyse(rows)['decline'],2)
        rows[5]['year']=100
        self.assertIsNone(h.analyse(rows)['decline'])

    def test_sudden_terminal_collapse_is_not_hidden_by_ten_year_rule(self):
        rows=[dict(year=1,power=1000,alive=True),dict(year=2,power=700,alive=True),
              dict(year=3,power=0,alive=False)]
        a=h.analyse(rows)
        self.assertIsNone(a['decline']);self.assertEqual(a['terminal'],2)

    def test_real_decision_metadata_and_no_game_state_mutation(self):
        with tempfile.TemporaryDirectory() as tmp:
            c=country();cs={'a':c};original=copy.deepcopy(cs)
            h.configure(tmp);h.begin(cs)
            h.event('a','裁軍執行',before=h.snapshot(c),phase='LATE',rank=2,
                    remaining=1,target_after=.2,demobilized=2,runway=9)
            h.annual(cs,4,'LATE',1);h.flush()
            rows=h.read_rows(h.path_for(tmp,'a',h.periods(c)[0]))
            self.assertEqual(len(h.analyse(rows)['late_demobs']),1)
            self.assertEqual(cs,original)

    def test_top_three_phase_alias_is_reproducible(self):
        state=('STRONG','SAFE','OK','AMPLE','PEACE','STABLE','ALLIED','CALM','LOW',
               'NORMAL','EARLY','FUNDED','TOP3')
        c=dict(world_rank=2,current_turn=100,is_alive=True)
        early=strategic_state_256(state,c)
        late=strategic_state_256(state[:10]+('LATE',)+state[11:],c)
        self.assertEqual(early,late)

if __name__=='__main__':unittest.main(verbosity=2)
