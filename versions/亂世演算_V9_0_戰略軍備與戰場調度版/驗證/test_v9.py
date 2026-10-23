import unittest,sys,importlib.util,copy,json,tempfile,math
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('tested_engine',ROOT/(ROOT.name+'.py'));e=importlib.util.module_from_spec(spec);spec.loader.exec_module(e)
w=e.war_strategy;m=e.military_strategy

def country(**extra):
 c=dict(is_alive=True,display_name='測試國',country_generation=1,pop_total=1000,soldiers=300,farmers=700,
        food=20000,wood=10000,metal=10000,gold=10000,power=15000,fortification=50,houses=150,
        war_exhaustion=0,political_stability=75,infamy=0,current_wars=[],current_alliance='A',
        military_target_ratio=.3,season_years_remaining=500,world_rank=20,season_phase='EARLY',
        alliance_confidence=dict(trust=50,comradeship=0,aid_received=0),newbie_protection_until_turn=0,
        rebuild_protection_until_turn=0,current_turn=100)
 c.update(extra);return c

def war(**extra):
 d=dict(attacker_anchor='x',defender_anchor='a',attacker_members=['x'],defender_members=['a'],
        attacker_name='X',defender_name='A',started_turn=90,combat_starts_turn=100,phase='MUSTERING',
        planned_duration=10,rounds=0,attacker_initial_soldiers=1000,defender_initial_soldiers=1000,
        attacker_loss_streak=0,defender_loss_streak=0,target_initial_soldiers=300)
 d.update(extra);return d

class V9Tests(unittest.TestCase):
 def setUp(self):e.random.seed(90)
 def test_defense_no_demob_fallback(self):
  a=e.CountryRLAgent('a');self.assertNotIn(3,a._strategic_valid_actions([11]));self.assertEqual(a._resolve_engine_action(3,[5,11],country(war_exhaustion=99)),5)
 def test_military_split(self):
  self.assertEqual(e.STRATEGIC_TO_ENGINE_ACTIONS[11],(11,));self.assertEqual(e.STRATEGIC_TO_ENGINE_ACTIONS[12],(16,))
 def test_bounded_timing_state(self):
  a=country();b=country(season_years_remaining=5);self.assertNotEqual(e.current_strategic_state('a',{'a':a}),e.current_strategic_state('a',{'a':b}));self.assertEqual(len(e.current_strategic_state('a',{'a':a})),5)
 def test_capital_only_target(self):
  c={'a':country(soldiers=300,fortification=80),'b':country(soldiers=0,fortification=0)};ww=war()
  for t in range(5):self.assertFalse(w.capital_status(ww,c,100+t,2000,100)[0])
 def test_occupation_requires_continuous_progress(self):
  c={'a':country(soldiers=50,fortification=10)};ww=war()
  self.assertFalse(w.capital_status(ww,c,101,1000,100)[0]);self.assertFalse(w.capital_status(ww,c,102,1000,100)[0])
  c['a']['fortification']=50;self.assertFalse(w.capital_status(ww,c,103,1000,100)[0]);self.assertEqual(ww['target_occupation'],0)
  c['a']['fortification']=10
  self.assertFalse(w.capital_status(ww,c,104,1000,100)[0]);self.assertFalse(w.capital_status(ww,c,105,1000,100)[0]);self.assertTrue(w.capital_status(ww,c,106,1000,100)[0])
 def test_protected_and_relief_capital(self):
  c={'a':country(soldiers=0,fortification=0,newbie_protection_until_turn=200)}
  self.assertFalse(w.capital_status(war(),c,100,1000,0)[0]);c['a']['newbie_protection_until_turn']=0
  self.assertFalse(w.capital_status(war(),c,100,100,200)[0]);self.assertTrue(w.capital_status(war(),c,100,100,0)[0])
 def test_rejected_peace_never_annexes(self):
  cs={'a':country(soldiers=300,fortification=50),'x':country(soldiers=1000,fortification=50)};ww=war(rounds=3,defender_initial_soldiers=10000)
  wars={'W':ww};e._war_index_rebuild(wars)
  # Freeze casualty/fort mutations to isolate the rejected peace route itself.
  with patch.object(e,'_war_avg_fort',return_value=10),patch.object(e,'_war_decide_surrender',return_value=(False,'測試拒絕')) as offer,patch.object(e,'_war_apply_soldier_losses',return_value=0),patch.object(e,'_war_damage_fort',return_value=(0,0)),patch.object(e,'_war_resolve_capital_defeat') as annex:
   result=e.resolve_persistent_war_round('W',ww,cs,wars,100,lambda *a:None)
   self.assertTrue(offer.called);annex.assert_not_called();self.assertFalse(result['ended']);self.assertTrue(cs['a']['is_alive']);self.assertEqual(ww['next_surrender_offer'],103)
 def test_duration_bounded(self):
  cs={'a':country(),'x':country()};ww=war(rounds=29,planned_duration=999)
  with patch.object(e,'_war_apply_soldier_losses',return_value=0),patch.object(e,'_war_damage_fort',return_value=(0,0)):
   result=e.resolve_persistent_war_round('W',ww,cs,{'W':ww},100,lambda *a:None)
  self.assertEqual(ww['planned_duration'],30);self.assertTrue(result['ended'])
 def test_force_pool_not_duplicated(self):
  wars={'O':war(attacker_members=['a'],defender_members=['x']), 'H':war(attacker_members=['x'],defender_members=['a'])}
  total=sum(w.front_share('a',wid,wars) for wid in wars);self.assertAlmostEqual(total,1);self.assertGreater(w.front_share('a','H',wars),w.front_share('a','O',wars))
 def test_troops_in_transit_reserve_the_same_pool(self):
  wars={'O':war(attacker_members=['b'],defender_members=['x']), 'H':war(reinforcements=[dict(country='b',arrival=102,generation=1)])}
  cs={'a':country(),'b':country(),'x':country()}
  self.assertLess(w.side_force(['b'],'O',wars,cs),300);self.assertEqual(w.side_force(['a'],'H',wars,cs),300)
  self.assertAlmostEqual(sum(w.front_share('b',wid,wars) for wid in wars),1)
 def test_new_front_prediction_matches_shared_pool(self):
  wars={'O':war(attacker_members=['b'],defender_members=['x'])}
  self.assertAlmostEqual(w.projected_front_share('b',wars,False),.5)
  self.assertAlmostEqual(w.projected_front_share('b',wars,True),2/3)
 def test_safe_aid(self):
  c=country(food=1000,metal=200);self.assertEqual(w.safe_aid_amount(c,'food',.1),0);self.assertEqual(w.safe_aid_amount(c,'metal',.1),0)
  c['food']=10000;take=w.safe_aid_amount(c,'food',.9);self.assertGreaterEqual(c['food']-take,7800)
 def test_protected_offense(self):
  cs={'a':country(newbie_protection_until_turn=200),'x':country()}
  self.assertEqual(e._alliance_vote_member_offense('a','a','x',cs,{'A':['a']},{},{},100)[0],'反對')
  valid=e.get_valid_rl_actions('a',cs,{'A':['a']},{},['x','a'],100);self.assertFalse(set(valid)&{0,2,4,10})
  self.assertEqual(e._war_filter_members_for_new_front(['a'],{},cs,100),[])
 def test_birth_no_repeated_payment(self):
  for c in [country(houses=100),country(birth_policy_turns=10),country(food=500)]:
   before=copy.deepcopy(c);self.assertEqual(e._apply_birth_policy(c,{}),(False,0));self.assertEqual(c,before)
 def test_birth_can_resume(self):
  c=country(birth_policy_turns=0);ok,_=e._apply_birth_policy(c,{});self.assertTrue(ok);self.assertGreater(c['pop_total'],1000)
 def test_military_step_cooldown_and_learning(self):
  a=e.CountryRLAgent('a');c=country();self.assertTrue(m.plan(a,c,100));self.assertLessEqual(abs(c['military_target_ratio']-.3),.030001);self.assertFalse(m.plan(a,c,101));m.settle(a,c,105);self.assertIsNone(a.military_pending);self.assertTrue(a.military_policy.action_stats)
 def test_military_save_pending_roundtrip(self):
  a=e.CountryRLAgent('a');c=country();m.plan(a,c,100);b=e.CountryRLAgent('a',policy_data=json.loads(json.dumps(a.policy_payload())));self.assertEqual(a.military_pending,b.military_pending);self.assertEqual(a.military_policy.q_table,b.military_policy.q_table)
 def test_military_forecast_finite(self):
  for c in [country(food=0,metal=0),country(pop_total=1,soldiers=0),country(battle_threat_ratio=10,season_years_remaining=1)]:
   self.assertTrue(all(math.isfinite(x['score']) and x['projected_power']>=0 for x in m.candidates(c)))
 def test_reinforcements_arrive_and_cost_no_duplication(self):
  cs={'a':country(soldiers=30),'x':country(soldiers=300),'b':country()};alliances={'A':['a','b']};ww=war();wars={'W':ww}
  with patch.object(e,'_alliance_member_defense_support',return_value=(True,'情誼測試')):
   w.prepare_year(e,cs,alliances,{},wars,100,lambda *a:None)
   self.assertEqual(ww['reinforcements'][0]['country'],'b');self.assertNotIn('b',ww['defender_members'])
   w.prepare_year(e,cs,alliances,{},wars,102,lambda *a:None)
  self.assertIn('b',ww['defender_members']);self.assertEqual(cs['b']['soldiers'],300);self.assertEqual(e._war_country_war_count('b',wars),1)
 def test_reinforcement_cancels_after_regime_rebuild_or_exit(self):
  cs={'a':country(soldiers=30),'x':country(soldiers=300),'b':country()};ww=war(reinforcements=[dict(country='b',generation=0,arrival=100)]);wars={'W':ww}
  with patch.object(e,'_alliance_member_defense_support',return_value=(False,'不再履約')):
   w.prepare_year(e,cs,{'A':['a','b']},{},wars,100,lambda *a:None)
  self.assertNotIn('b',ww['defender_members']);self.assertEqual(ww['reinforcements'],[])
 def test_withdraw_for_homeland(self):
  cs={'a':country(),'x':country(soldiers=1500),'z':country()};wars={'O':war(attacker_anchor='a',defender_anchor='z',attacker_members=['a'],defender_members=['z']), 'H':war(attacker_members=['x'],defender_members=['a'])}
  w.prepare_year(e,cs,{}, {},wars,100,lambda *a:None);self.assertNotIn('a',wars['O']['attacker_members']);self.assertIn('a',wars['H']['defender_members']);self.assertGreater(cs['a']['front_redeploy_after'],100)
 def test_protected_legacy_war_sanitized(self):
  cs={'a':country(),'x':country(),'b':country(rebuild_protection_until_turn=200)};ww=war(attacker_members=['x','b']);wars={'W':ww}
  w.prepare_year(e,cs,{}, {},wars,100,lambda *a:None);self.assertNotIn('b',ww['attacker_members'])
 def test_bounded_logs(self):
  c=country()
  for i in range(500):w.record(c,i,'測試','原因')
  self.assertEqual(len(c['strategy_events']),100)
 def test_migration_preserves_subpolicies_and_archives(self):
  payload={'a':{'rl_version':8,'action_size':16,'q_table':{'old':[1]*16},'policies':{'strategic':{'q_table':{'old':[1]*11}},'fiscal':{'q_table':{'["f"]':[1,2,3,4]}},'market':{'q_table':{'["m"]':[1]*7}}}}}
  with tempfile.TemporaryDirectory() as td:
   path=Path(td)/'q.json';path.write_text(json.dumps(payload));agents=e.load_all_agents(['a'],str(path));a=agents['a']
   self.assertEqual(a.strategic_policy.q_table,{});self.assertEqual(a.fiscal_policy.q_table,payload['a']['policies']['fiscal']['q_table']);self.assertTrue(Path(str(path)+'.pre_v9_backup').exists())
 def test_rank_unchanged(self):self.assertEqual(e.calculate_rts_power(country(soldiers=123)),6150)

if __name__=='__main__':unittest.main(verbosity=2)
