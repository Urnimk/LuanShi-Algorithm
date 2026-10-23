from pathlib import Path
import ast,copy,importlib.util,json,sys,tempfile,unittest
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import alliance_honors as h
import chronicle_retention as retention

def country(alliance='A',joined=0,records=None):
    c=dict(is_alive=True,current_alliance=alliance,championship_records=records or [])
    if joined is not None:c['alliance_join_turn']=joined
    return c

def load_ui():
    spec=importlib.util.spec_from_file_location('compact_ui',ROOT/(ROOT.name+'_啟動.py'))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m

class Tests(unittest.TestCase):
    def test_latest_50_and_all_time_records(self):
        rows=[dict(generation=i,peak_power=1000 if i==1 else i,peak_power_year=i,
                   peak_population=2000 if i==2 else i,best_rank=1 if i==3 else 5,
                   end_year=i+1 if i<80 else None) for i in range(1,81)]
        c=dict(country_chronicle=rows)
        self.assertEqual(retention.trim(c),30)
        self.assertEqual([r['generation'] for r in c['country_chronicle']],list(range(31,81)))
        self.assertIsNone(c['country_chronicle'][-1]['end_year'])
        self.assertEqual(c['chronicle_all_time']['peak_power'],1000)
        self.assertEqual(c['chronicle_all_time']['peak_population'],2000)
        self.assertEqual(c['chronicle_all_time']['best_rank'],1)
        old=copy.deepcopy(c);self.assertEqual(retention.trim(c),0);self.assertEqual(c,old)
        c['country_chronicle'].append(dict(generation=81,peak_power=5))
        self.assertEqual(retention.trim(c),1);self.assertEqual(c['chronicle_all_time']['peak_power'],1000)

    def test_count_generations_not_duplicate_rows(self):
        c=dict(country_chronicle=[dict(generation=i,peak_power=i) for i in range(1,55) for _ in range(2)])
        retention.trim(c)
        self.assertEqual(len({e['generation'] for e in c['country_chronicle']}),50)

    def test_member_counts_only_current_stint(self):
        cs={'a':country(joined=750,records=['R1__50__old','R2__50__a','R2__50__duplicate','R3__50__a']),
            'b':country(joined=1200,records=['R2__10__b'])}
        als={'A':['a','b']};meta={'A':dict(created_turn=None,observed_since=750)}
        h.synchronize(cs,als,meta,{},1600,4,1500,500)
        self.assertEqual(cs['a']['alliance_trophies']['count'],2)
        self.assertEqual(cs['b']['alliance_trophies']['count'],0)
        self.assertEqual(meta['A']['honors']['count'],2)
        self.assertFalse(meta['A']['honors']['complete'])

    def test_old_duplicate_round_is_one_alliance_title(self):
        cs={k:country(records=['R1__50__'+k]) for k in ['a','b']};als={'A':['a','b']};meta={'A':dict(created_turn=None)}
        h.synchronize(cs,als,meta,{},600,2,500,500)
        self.assertEqual(meta['A']['honors']['count'],1)
        state=cs['a']['alliance_trophies']
        h.synchronize(cs,als,meta,{},601,2,500,500)
        self.assertIs(cs['a']['alliance_trophies'],state)

    def test_real_award_exact_and_reload_idempotence(self):
        cs={'a':country(joined=1),'b':country(joined=1)};als={'A':['a','b']};meta={'A':dict(created_turn=1)}
        h.synchronize(cs,als,meta,{},1,1,0,500)
        self.assertTrue(meta['A']['honors']['complete'])
        h.record_champion('a',cs,als,meta,{},500,1,0,500)
        cs['a']['championship_records'].append('R1__500__a')
        cs,als,meta=json.loads(json.dumps([cs,als,meta]))
        h.record_champion('a',cs,als,meta,{},500,1,0,500)
        self.assertEqual(cs['a']['alliance_trophies']['count'],1)
        self.assertEqual(meta['A']['honors']['count'],1)

    def test_departure_and_rejoining_preserve_alliance_honor(self):
        cs={'a':country(joined=1),'b':country(joined=1)};als={'A':['a','b']};meta={'A':dict(created_turn=1)}
        h.synchronize(cs,als,meta,{},1,1,0,500)
        h.record_champion('a',cs,als,meta,{},500,1,0,500)
        cs['a']['championship_records']=['R1__500__a']
        als['A'].remove('a');cs['a']['current_alliance']=''
        h.synchronize(cs,als,meta,{},600,2,500,500)
        self.assertEqual(meta['A']['honors']['count'],1)
        cs['a'].update(current_alliance='A',alliance_join_turn=700);als['A'].append('a')
        h.synchronize(cs,als,meta,{},700,2,500,500)
        self.assertEqual(cs['a']['alliance_trophies']['count'],0)
        h.record_champion('a',cs,als,meta,{},1000,2,500,500)
        self.assertEqual(meta['A']['honors']['count'],2)

    def test_unknown_old_membership_and_nonstandard_calendar(self):
        for joined,start in [(None,500),(0,501)]:
            cs={'a':country(joined=joined,records=['R1__500__a'])};meta={'A':dict(created_turn=None)}
            h.synchronize(cs,{'A':['a']},meta,{},600,2,start,500)
            s=cs['a']['alliance_trophies'];self.assertEqual(s['count'],0);self.assertFalse(s['complete'])
            self.assertEqual(h.snapshot('A',['a'],cs,meta['A'],'alliance',600)['championship_text'],'至少 0')

    def test_coalition_and_ordinary_are_separate_entities(self):
        cs={'a':country(joined=1)};als={'A':['a']};meta={'A':dict(created_turn=1)}
        coal={'C':dict(created_turn=1,members=['a'])}
        h.synchronize(cs,als,meta,coal,1,1,0,500)
        h.record_champion('a',cs,als,meta,coal,500,1,0,500)
        self.assertEqual(meta['A']['honors']['count'],1);self.assertEqual(coal['C']['honors']['count'],1)
        self.assertEqual(h.snapshot('C',['a'],cs,coal['C'],'coalition',500)['age_years'],499)

    def test_remove_only_retired_report_directory(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'country_history').mkdir();(p/'country_history'/'annual.jsonl').write_text('x')
            (p/'war_live_countries.json').write_text('keep')
            self.assertTrue(retention.remove_report_data(p))
            self.assertFalse((p/'country_history').exists());self.assertEqual((p/'war_live_countries.json').read_text(),'keep')

    def test_cleanup_does_not_follow_symlink(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);outside=p/'outside';outside.mkdir();(outside/'keep').write_text('x')
            saves=p/'saves';saves.mkdir();(saves/'country_history').symlink_to(outside,target_is_directory=True)
            retention.remove_report_data(saves);self.assertTrue((outside/'keep').exists())

    def test_retired_imports_and_buttons_absent(self):
        self.assertFalse((ROOT/'country_history.py').exists())
        for p in ROOT.glob('*.py'):
            s=p.read_text();self.assertNotIn('import country_history',s);self.assertNotIn('historian.',s)
        self.assertNotIn('open_selected_country_history',(ROOT/(ROOT.name+'_啟動.py')).read_text())

    def test_target_hyperlink_after_added_columns(self):
        ui=load_ui();seen=[]
        tree=SimpleNamespace(identify_row=lambda y:'A',identify_column=lambda x:'#6',
                             item=lambda row,field:('A',100,'2/2',3,'500 年','enemy'))
        fake=SimpleNamespace(tree_alliance=tree,navigate_to_country=seen.append,navigate_to_alliance=seen.append)
        ui.GameInterfaceUI.on_alliance_tree_click(fake,SimpleNamespace(x=1,y=1))
        self.assertEqual(seen,['enemy'])

    def test_sort_ages_and_titles_numerically(self):
        ui=load_ui()
        class Tree:
            def __init__(self):self.ids=['a','b','c'];self.values={'a':'至少 9,574 年','b':'100 年','c':'未知'}
            def get_children(self,*args):return list(self.ids)
            def set(self,k,col):return self.values[k]
            def move(self,k,parent,index):self.ids.remove(k);self.ids.insert(index,k)
        tree=Tree();ui.GameInterfaceUI.apply_sort(None,tree,'age',True)
        self.assertEqual(tree.ids,['a','b','c'])
        tree.values={'a':'至少 8','b':'12','c':'2'}
        ui.GameInterfaceUI.apply_sort(None,tree,'championships',True)
        self.assertEqual(tree.ids,['b','a','c'])

    def test_gui_member_column_and_summary(self):
        ui=load_ui();rows={}
        cs={'a':dict(power=10,pop_total=10,soldiers=1,current_alliance='A',alliance_join_turn=0)}
        details=dict(members=['a'],total_power=10,member_count=1,alive_member_count=1,
                     championship_text='至少 3',member_championships={'a':dict(count=3,complete=True)})
        fake=SimpleNamespace(ally_cb=SimpleNamespace(get=lambda:'A'),raw_countries_data=cs,
            raw_alliances_data={'A':details},raw_turn_counter=100,raw_active_wars={},
            _last_alliance_log_owner='',alliance_summary_tree='summary',alliance_member_tree='members',
            alliance_war_tree='wars',ally_log_text=None,resolve_country_key=lambda k:k,
            _build_rank_map=lambda:{'a':1},_relation_display_name=lambda k,c:k,
            _relation_status=lambda k,c,status:status,_replace_tree_rows=lambda tree,r:rows.update({tree:r}),
            load_specific_logs=lambda *a,**kw:None,_compact_text=lambda s,n:s)
        ui.GameInterfaceUI.on_alliance_selected(fake)
        self.assertEqual(len(rows['members'][0]),9)
        self.assertEqual(rows['members'][0][-2],'3')
        self.assertIn(('累計冠軍','至少 3 次'),rows['summary'])
        # 使用者上傳版已將成員冠軍移到成員表，以上保留該欄驗證。

if __name__=='__main__':unittest.main(verbosity=2)
