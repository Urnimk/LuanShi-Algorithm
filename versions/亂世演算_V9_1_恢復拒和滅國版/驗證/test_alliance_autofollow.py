"""Headless checks for the small V9_1_1 UI change."""
import importlib.util
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
spec=importlib.util.spec_from_file_location('autofollow_ui',ROOT/(ROOT.name+'_啟動.py'))
ui=importlib.util.module_from_spec(spec)
spec.loader.exec_module(ui)

class Choice:
    def __init__(self,value):self.value=value
    def get(self):return self.value
    def set(self,value):self.value=value

class AutoFollowTests(unittest.TestCase):
    def make_view(self,selected,alliances):
        v=SimpleNamespace(ally_cb=Choice(selected),raw_alliances_data=alliances,
            _last_alliance_log_owner=selected,alliance_summary_tree='summary',
            alliance_member_tree='members',alliance_war_tree='wars',ally_log_text='log',cleared=[],logs=[])
        v._replace_tree_rows=lambda tree,rows:v.cleared.append((tree,rows))
        v.load_specific_logs=lambda widget,terms,force_top=False:v.logs.append((widget,terms,force_top))
        return v
    def follow(self,v):ui.GameInterfaceUI.follow_watched_alliance(v)
    def test_existing_watched_alliance_is_kept(self):
        v=self.make_view('舊盟',{'舊盟':{'total_power':10},'強盟':{'total_power':500}})
        self.follow(v);self.assertEqual(v.ally_cb.get(),'舊盟');self.assertFalse(v.cleared)
    def test_dissolved_alliance_follows_current_strongest(self):
        v=self.make_view('舊盟',{'弱盟':{'total_power':30},'強盟':{'total_power':500},'中盟':{'total_power':200}})
        self.follow(v);self.assertEqual(v.ally_cb.get(),'強盟');self.assertFalse(v.cleared)
    def test_includes_temporary_coalitions(self):
        v=self.make_view('舊盟',{'普通盟':{'total_power':200},'臨時聯軍':{'total_power':500,'is_coalition':True}})
        self.follow(v);self.assertEqual(v.ally_cb.get(),'臨時聯軍')
    def test_no_alliances_clears_previous_content_then_follows_new_one(self):
        v=self.make_view('舊盟',{});self.follow(v)
        self.assertEqual(v.ally_cb.get(),'');self.assertIsNone(v._last_alliance_log_owner)
        self.assertEqual(v.cleared,[('summary',[]),('members',[]),('wars',[])])
        self.assertEqual(v.logs,[('log',[],True)])
        v.raw_alliances_data={'新盟':{'total_power':100}};self.follow(v);self.assertEqual(v.ally_cb.get(),'新盟')
    def test_equal_power_has_stable_choice(self):
        v=self.make_view('舊盟',{'B':{'total_power':100},'A':{'total_power':100}})
        self.follow(v);self.assertEqual(v.ally_cb.get(),'A')

if __name__=='__main__':unittest.main()
