"""Run: python 驗證/test_confidence.py (no Tk display required)."""
import copy
import importlib.util
import json
from pathlib import Path
import random
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import alliance_confidence as d

def country(power=10000,alliance='A',joined=0):
    c=dict(power=power,pop_total=10000,food=20000,wood=2000,metal=1000,
           soldiers=1000,farmers=9000,is_alive=True,display_name='試驗國',
           political_stability=75,war_exhaustion=0,current_alliance=alliance,
           current_turn=0,hostility={},infamy=0)
    if joined is not None: c['alliance_join_turn']=joined
    return c

def sample_world():
    return {'a':country(100000),'b':country(1000),'c':country(500)}, {'A':['a','b','c']}

def leave(k,cs,als,reason):
    a=cs[k]['current_alliance'];als[a].remove(k);cs[k]['current_alliance']=''
    return True

def review(cs,als,t,wars=None,metadata=None):
    d.sync_metadata(cs,als,metadata if metadata is not None else {},t)
    d.review(cs,als,wars or {},{},t,leave,log=lambda s:None)


class ConfidenceTests(unittest.TestCase):
    def test_old_join_dates_and_year_zero(self):
        c=country(joined=0);d.sync(c,150000)
        self.assertEqual(d.tenure_text(c,150000),'150,000 年')
        c=country(joined=None);d.sync(c,150000)
        self.assertEqual(d.tenure_text(c,150010),'至少 10 年')
        meta={};cs,als=sample_world();d.sync_metadata(cs,als,meta,150000)
        self.assertIn('至少 150,010 年',d.summary_fields('A',meta['A'],150010,1,2)['age_text'])
        unknown={'u':country(joined=None),'v':country(joined=None)}
        d.sync_metadata(unknown,{'U':['u','v']},meta,150000)
        self.assertIn('至少 10 年',d.summary_fields('U',meta['U'],150010,1,2)['age_text'])
        d.register_alliance(meta,'B',0)
        self.assertEqual(d.summary_fields('B',meta['B'],50,2,2)['age_text'],'50 年')

    def test_individual_interests_and_roles(self):
        cs,als=sample_world();review(cs,als,10)
        a,b=d.sync(cs['a'],10),d.sync(cs['b'],10)
        self.assertNotEqual(a['benefit'],b['benefit'])
        self.assertEqual(a['role'],'霸權國');self.assertEqual(b['role'],'弱國')
        cs['b']['power']=200000;review(cs,als,20)
        self.assertEqual(d.sync(cs['b'],20)['role'],'霸權國')

    def test_strong_protector_is_not_a_betrayal_reason(self):
        cs,als=sample_world()
        for t in range(10,210,10): review(cs,als,t)
        self.assertFalse(d.betrayal_allowed(cs['b'],210))
        self.assertEqual(cs['b']['current_alliance'],'A')

    def test_sustained_wartime_growth_beats_war_frequency(self):
        cs,als=sample_world();cs['enemy']=country(1000,'',None)
        wars={'W':{'attacker_members':['a','b','c'],'defender_members':['enemy']}}
        for t in range(10,80,10):
            for k in ('a','b','c'): cs[k]['power']*=1.15;cs[k]['pop_total']*=1.05
            review(cs,als,t,wars)
        s=d.sync(cs['b'],70)
        self.assertIn('戰時聯盟戰力持續趨勢 +',s['last_reason'])
        self.assertGreater(s['benefit'],70)

    def test_no_bond_from_tenure_alone(self):
        cs,als=sample_world();review(cs,als,100000)
        for c in cs.values():
            s=d.sync(c,100000)
            self.assertEqual(s['bond_display'],0)
            self.assertFalse(s['stand_together'])

    def test_actual_battle_evidence_and_no_credit_from_ballot(self):
        cs,als=sample_world()
        war=dict(attacker_members=['a','b'],defender_members=['x'],
                 attacker_troop_contribution={},defender_troop_contribution={},started_turn=1)
        before={'attacker':{},'defender':{},'attacker_power':100,'defender_power':300}
        d.record_battle(cs,war,10,{},before)
        self.assertEqual(d.sync(cs['b'],10)['combat_years'],0)
        war['attacker_troop_contribution']={'a':40,'b':20}
        d.record_battle(cs,war,10,{},before)
        d.record_battle(cs,war,10,{},before) # two fronts in one year cannot double annual bond
        self.assertEqual(d.sync(cs['b'],10)['combat_years'],1)
        self.assertEqual(d.sync(cs['b'],10)['crises'],1)
        d.record_battle(cs,war,11,{'ended':True,'winner':'ATTACKER'},
                        {'attacker':{'a':40,'b':20},'defender':{}})
        self.assertEqual(d.sync(cs['b'],11)['shared_victories'],1)

    def test_aid_observation_does_not_move_resources(self):
        a,b=country(),country();snapshot=copy.deepcopy((a,b))
        d.record_aid(a,b,{'food':100},20)
        self.assertEqual(a['food'],snapshot[0]['food'])
        self.assertEqual(b['food'],snapshot[1]['food'])
        self.assertEqual(d.sync(b,20)['aid_received'],100)
        self.assertGreater(d.sync(b,20)['trust'],55)

    def test_abandonment_breaks_bond_and_is_causal(self):
        cs,als=sample_world();s=d.sync(cs['b'],10);s['comradeship']=90;s['trust']=90
        d.record_refusal(cs,'b',{'votes':{'a':'拒絕','b':'支援','c':'拒絕'},'reasons':{'a':'拒絕增援','c':'戰線已滿'}},10)
        review(cs,als,10)
        self.assertLess(s['trust'],90)
        self.assertLess(s['bond_display'],90)
        self.assertIn('共同防禦請求未獲部分盟友支援',s['last_reason'])

    def test_inertia_and_revolutionary_bond_cushion(self):
        cs,als=sample_world();fresh=copy.deepcopy(cs)
        s=d.sync(cs['a'],10);s.update(confidence=90,comradeship=85,trust=90,combat_years=100)
        s2=d.sync(fresh['a'],10);s2.update(confidence=90,comradeship=0,trust=90)
        for data in (cs,fresh): data['a']['hostility']={'b':100,'c':100}
        review(cs,als,10);review(fresh,copy.deepcopy(als),10)
        self.assertGreater(s['confidence'],s2['confidence'])
        self.assertGreater(s['confidence'],60)
        self.assertFalse(d.exit_allowed(cs['a'],10))

    def test_peaceful_exit_has_persistence_notice_and_no_theft(self):
        cs,als=sample_world();cs['a']['hostility']={'b':100,'c':100}
        s=d.sync(cs['a'],0);s['trust']=10
        saw_notice=False
        for t in range(10,210,10):
            review(cs,als,t)
            saw_notice=saw_notice or bool(s.get('notice'))
            if not cs['a']['current_alliance']: break
        self.assertTrue(saw_notice);self.assertEqual(cs['a']['current_alliance'],'')
        self.assertGreaterEqual(t,50)
        self.assertEqual(cs['a']['food'],20000);self.assertEqual(cs['a']['infamy'],0)
        self.assertGreater(s['cooldown_until'],t)

    def test_recovery_cancels_notice(self):
        cs,als=sample_world();cs['a']['hostility']={'b':100,'c':100}
        s=d.sync(cs['a'],0);s.update(trust=10)
        for t in range(10,210,10):
            review(cs,als,t)
            if s.get('notice'): break
        self.assertIn('notice',s)
        cs['a']['hostility']={};s['trust']=90
        review(cs,als,t+10)
        self.assertNotIn('notice',s);self.assertEqual(cs['a']['current_alliance'],'A')

    def test_war_defers_exit_but_survival_crisis_can_end_delay(self):
        cs,als=sample_world();cs['a']['hostility']={'b':100,'c':100}
        cs['x']=country(100,'');s=d.sync(cs['a'],0);s.update(trust=24)
        wars={'W':{'attacker_members':['b'],'defender_members':['x']}}
        for t in range(10,210,10):
            review(cs,als,t,wars)
            if s.get('notice') and t>=s['notice']['due']: break
        self.assertIn('notice',s);self.assertEqual(cs['a']['current_alliance'],'A')
        self.assertIn('等待共同戰事',s['last_decision'])

    def test_extreme_pact_is_not_just_age_and_can_break(self):
        c=country();s=d.sync(c,1000)
        s.update(confidence=95,benefit=90,trust=95,bond_display=90,stand_together=True,crises=3,combat_years=100)
        self.assertTrue(d.stand_together(c))
        d.record_event(c,1000,'革命情誼遭盟友背叛',-35,-35)
        self.assertFalse(d.stand_together(c))

    def test_continued_loss_can_overcome_old_bond(self):
        cs,als=sample_world();cs['a']['hostility']={'b':200,'c':200}
        s=d.sync(cs['a'],0);s.update(comradeship=100,trust=5,combat_years=100,confidence=95)
        for t in range(10,510,10):
            cs['a']['power']*=.9
            review(cs,als,t)
            if not cs['a']['current_alliance']:break
        self.assertEqual(cs['a']['current_alliance'],'')

    def test_save_reload_decision_continuity(self):
        cs,als=sample_world();cs['a']['hostility']={'b':100,'c':100}
        d.sync(cs['a'],0)['trust']=10
        for t in range(10,60,10):review(cs,als,t)
        other,others=json.loads(json.dumps(cs)),json.loads(json.dumps(als))
        for t in range(60,130,10):
            review(cs,als,t);review(other,others,t)
        self.assertEqual(cs,other);self.assertEqual(als,others)

    def test_review_is_idempotent_and_does_not_draw_randomness(self):
        cs,als=sample_world();before=random.getstate();review(cs,als,10)
        saved=copy.deepcopy(cs);review(cs,als,10)
        self.assertEqual(cs,saved);self.assertEqual(random.getstate(),before)

    def test_archive_records_all_changes(self):
        cs,als=sample_world()
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'events.jsonl'
            d.review(cs,als,{}, {},10,leave,log=lambda s:None,audit_path=p)
            entries=[json.loads(l) for l in p.read_text().splitlines()]
            self.assertEqual(len(entries),3)
            self.assertTrue(all(e['reason'] and e['old']!=e['confidence'] for e in entries))

    def test_engine_guards_all_leave_callers_and_action_mask(self):
        source=ROOT/(ROOT.name+'.py')
        spec=importlib.util.spec_from_file_location('confidence_engine',source)
        engine=importlib.util.module_from_spec(spec);spec.loader.exec_module(engine)
        cs,als=sample_world()
        for c in cs.values(): c['current_turn']=100
        self.assertFalse(engine._leave_alliance('b',cs,als,reason='聯盟成員爭執'))
        self.assertFalse(engine._leave_alliance('b',cs,als,reason='政變'))
        self.assertNotIn(4,engine.get_valid_rl_actions('b',cs,als,{},list(cs),100))
        s=d.sync(cs['b'],100)
        s.update(confidence=10,trust=10,low_reviews=4,observation_ready=True,
                 outside_value=90,stay_value=10,breaches=3,previous_members=['a','b','c'])
        cs['b']['hostility']={'a':100}
        self.assertIn(4,engine.get_valid_rl_actions('b',cs,als,{},list(cs),100))
        self.assertTrue(d.betrayal_allowed(cs['b'],100))

    def test_gui_summary_and_member_rows_without_display(self):
        from types import SimpleNamespace
        spec=importlib.util.spec_from_file_location('confidence_ui',ROOT/(ROOT.name+'_啟動.py'))
        ui=importlib.util.module_from_spec(spec);spec.loader.exec_module(ui)
        cs,als=sample_world();review(cs,als,100)
        rows={};selected=['A']
        fake=SimpleNamespace(
            ally_cb=SimpleNamespace(get=lambda:selected[0]),
            raw_countries_data=cs,raw_turn_counter=100,raw_active_wars={},
            raw_alliances_data={
                'A':dict(members=['a','b','c'],total_power=101500,member_count=3,alive_member_count=3,
                         confidence_summary=dict(age_text='100 年',ranking_text='第 1 / 2 名（普通聯盟，依總戰力）')),
                'C':dict(members=['a','b'],is_coalition=True,total_power=101000,created_turn=40)},
            _last_alliance_log_owner='',alliance_summary_tree='summary',
            alliance_member_tree='members',alliance_war_tree='wars',ally_log_text=None,
            resolve_country_key=lambda k:k,_build_rank_map=lambda:{'a':1,'b':2,'c':3},
            _relation_display_name=lambda k,c:k,_relation_status=lambda k,c,status:status,
            _replace_tree_rows=lambda tree,r:rows.update({tree:r}),
            load_specific_logs=lambda *a,**kw:None,_compact_text=lambda s,n:s)
        ui.GameInterfaceUI.on_alliance_selected(fake)
        self.assertEqual(len(rows['members']),3)
        self.assertTrue(all(len(row)==9 for row in rows['members']))
        self.assertEqual(rows['members'][0][-3],'100 年')
        self.assertIn(('存在年數','100 年'),rows['summary'])
        self.assertTrue(any('第 1 / 2 名' in str(r) for r in rows['summary']))
        selected[0]='C';ui.GameInterfaceUI.on_alliance_selected(fake)
        self.assertIn(('存在年數','60 年'),rows['summary'])
        self.assertTrue(any('第 1 / 1 名（臨時聯軍）' in str(r) for r in rows['summary']))


if __name__=='__main__': unittest.main(verbosity=2)
