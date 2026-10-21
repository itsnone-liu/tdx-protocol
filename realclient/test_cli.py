"""Offline invariants for independent CLI adjustment and identity protection."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cli import adjust,symbol,Session
class Tests(unittest.TestCase):
 def e(self,date,fh=0,sz=0,pg=0,pj=0):
  y,m,d=map(int,date.split('-'));return dict(year=y,month=m,day=d,category=1,fenhong=fh,songzhuangu=sz,peigu=pg,peigujia=pj)
 def test_dividend(self):
  self.assertAlmostEqual(adjust([('2026-01-01',10)], [self.e('2026-02-01',fh=1)],'2026-03-01')[0][1],9.9)
 def test_split_then_new_dividend(self):
  ev=[self.e('2026-02-01',sz=10),self.e('2026-03-01',fh=1)]
  self.assertAlmostEqual(adjust([('2026-01-01',10)],ev,'2026-04-01')[0][1],4.9)
 def test_rights_sign(self):
  self.assertAlmostEqual(adjust([('2026-01-01',10)],[self.e('2026-02-01',pg=10,pj=4)],'2026-04-01')[0][1],7)
 def test_future_event_excluded(self):
  self.assertEqual(adjust([('2026-01-01',10)],[self.e('2027-01-01',fh=1)],'2026-04-01')[0][1],10)
 def test_event_day_not_adjusted(self):
  self.assertEqual(adjust([('2026-02-01',10)],[self.e('2026-02-01',fh=1)],'2026-04-01')[0][1],10)
 def test_duplicate_event_fails(self):
  with self.assertRaises(ValueError):adjust([('2026-01-01',10)],[self.e('2026-02-01'),self.e('2026-02-01')],'2026-04-01')
 def test_symbol(self):
  self.assertEqual(symbol('bj920002'),(2,'920002'))
  with self.assertRaises(ValueError):symbol('920002')
 def test_unexpected_quote_not_accepted(self):
  s=object.__new__(Session);s.sock=None;s.call=lambda cmd:[dict(market=1,code='600839')]
  r=s.quotes([(0,'000004')]);self.assertFalse(r['complete']);self.assertEqual(r['rows'],[])
if __name__=='__main__':unittest.main()
