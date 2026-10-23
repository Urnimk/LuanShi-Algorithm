import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import alliance_confidence as c

class RetentionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.path=Path(self.tmp.name)/'history.jsonl';c._journal_state.clear()
 def tearDown(self):self.tmp.cleanup()
 def rows(self):return [json.loads(x) for x in self.path.read_text().splitlines()]
 def write(self,years):self.path.write_text(''.join(json.dumps(dict(year=y,reason='測試'))+'\n' for y in years))
 def test_exact_1000_year_window(self):
  self.write([0,1000,1001,1999,2000,2001]);c.prune_journal(self.path,2000,force=True)
  self.assertEqual([x['year'] for x in self.rows()],[1001,1999,2000])
 def test_append_cleans_old_file(self):
  self.write([1,1000,1001]);c.journal(self.path,dict(year=2000,confidence=70))
  self.assertEqual([x['year'] for x in self.rows()],[1001,2000])
 def test_quiet_year_without_new_events_still_expires_rows(self):
  self.write([1000,1005]);c.prune_journal(self.path,1999);c.prune_journal(self.path,2000)
  self.assertEqual([x['year'] for x in self.rows()],[1005])
 def test_no_repeated_scan_for_each_country_same_year(self):
  c.journal(self.path,dict(year=1000))
  with patch('tempfile.NamedTemporaryFile',side_effect=AssertionError('unexpected full scan')):
   for i in range(100):c.journal(self.path,dict(year=1000,country=str(i)))
   c.prune_journal(self.path,1001)
  self.assertEqual(len(self.rows()),101)
 def test_external_file_change_is_detected(self):
  c.journal(self.path,dict(year=2000));self.write([0,2000]);c.prune_journal(self.path,2000)
  self.assertEqual([x['year'] for x in self.rows()],[2000])
 def test_broken_rows_are_removed(self):
  self.path.write_bytes(b'broken\n{"year":1001}\n{"reason":"unknown"}\n{"year":true}\n')
  c.prune_journal(self.path,2000);self.assertEqual([x['year'] for x in self.rows()],[1001])
 def test_atomic_failure_preserves_original(self):
  self.write([1,2000]);before=self.path.read_bytes()
  with patch('os.replace',side_effect=OSError('test failure')):
   with self.assertRaises(OSError):c.prune_journal(self.path,2000)
  self.assertEqual(self.path.read_bytes(),before);self.assertFalse(list(self.path.parent.glob('.confidence-*.tmp')))
 def test_rollback_does_not_keep_future_history(self):
  self.write([1000,1500,2000]);c.prune_journal(self.path,2000);c.prune_journal(self.path,1500)
  self.assertEqual([x['year'] for x in self.rows()],[1500])
 def test_engine_calls_cleanup_at_load_and_each_year(self):
  s=(ROOT/(ROOT.name+'.py')).read_text();self.assertIn('turn_counter, force=True)',s)
  self.assertGreaterEqual(s.count('confidence.prune_journal('),2)

if __name__=='__main__':unittest.main()
