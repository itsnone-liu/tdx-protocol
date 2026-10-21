"""Offline invariants for independent CLI adjustment and identity protection."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parent))
from cli import adjust,symbol,Session,parse_capital_batch,run_hosts,atomic_json
import tempfile,json
import struct
from unittest.mock import patch
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
 def test_snapshot_turnover_units(self):
  s=object.__new__(Session)
  s.quotes=lambda stocks:dict(rows=[dict(market=2,code='920002',vol=100,price=11,last_close=10)],complete=True,missing=[],unexpected=[])
  s.finance=lambda m,c:dict(liutongguben=1000000,updated_date=20260804)
  row=s.snapshot([(2,'920002')])['rows'][0]
  self.assertAlmostEqual(row['turnover_pct'],1.0);self.assertAlmostEqual(row['pct_change'],10.)
 def test_snapshot_missing_float(self):
  s=object.__new__(Session)
  s.quotes=lambda stocks:dict(rows=[dict(market=1,code='600125',vol=100,price=0,last_close=10)],complete=True)
  s.finance=lambda m,c:dict(liutongguben=0)
  row=s.snapshot([(1,'600125')])['rows'][0]
  self.assertIsNone(row['turnover_pct']);self.assertIsNone(row['pct_change'])
 def capital_body(self,code='920002'):
  r=bytearray(143);r[0]=2;r[1:7]=code.encode();struct.pack_into('<f',r,7,100.);struct.pack_into('<II',r,15,20260804,20240530);struct.pack_into('<f',r,23,200.)
  return struct.pack('<H',1)+r
 def test_capital_units(self):
  r=parse_capital_batch(self.capital_body(),[(2,'920002')])[0]
  self.assertEqual(r['float_shares'],1000000);self.assertEqual(r['total_shares'],2000000);self.assertEqual(r['data_date'],20260804)
 def test_capital_truncated(self):
  with self.assertRaises(ValueError):parse_capital_batch(self.capital_body()[:-1],[(2,'920002')])
 def test_capital_wrong_identity(self):
  with self.assertRaises(ValueError):parse_capital_batch(self.capital_body('920003'),[(2,'920002')])
 def test_capital_missing(self):
  with self.assertRaises(ValueError):parse_capital_batch(b'\x00\x00',[(2,'920002')])
 def test_capital_duplicate(self):
  b=self.capital_body();b=struct.pack('<H',2)+b[2:]+b[2:]
  with self.assertRaises(ValueError):parse_capital_batch(b,[(2,'920002')])
 def test_batch_snapshot(self):
  s=object.__new__(Session);s.quotes=lambda stocks:dict(rows=[dict(market=2,code='920002',vol=100,price=11,last_close=10)],complete=True)
  s.capital_batch=lambda stocks:[dict(market=2,code='920002',float_shares=1000000,data_date=20260804)]
  r=s.snapshot([(2,'920002')],use_batch=True)['rows'][0]
  self.assertEqual(r['capital_source'],'op16');self.assertEqual(r['turnover_pct'],1.)
 def names_responses(self,bad_length=False):
  h1=bytearray(16);struct.pack_into('<H',h1,10,0x044e)
  h2=bytearray(16);struct.pack_into('<H',h2,10,0x044d)
  record=bytearray(37);record[:6]=b'920002';struct.pack_into('<H',record,6,100);name='万达轴承'.encode('gbk');record[8:8+len(name)]=name
  body=struct.pack('<H',1)+record
  return [(h1,b'\x01\x00'),(h2,body[:-1] if bad_length else body)]
 def test_names_bj_record(self):
  class Sock:
   def sendall(self,b):pass
  s=object.__new__(Session);s.sock=Sock()
  with patch('cli.recv',side_effect=self.names_responses()):r=s.names(2,20261021)
  self.assertEqual(r['total'],1);self.assertEqual(r['rows'][0]['name'],'万达轴承');self.assertTrue(r['rows'][0]['name_decode_ok'])
 def test_names_truncated(self):
  class Sock:
   def sendall(self,b):pass
  s=object.__new__(Session);s.sock=Sock()
  with patch('cli.recv',side_effect=self.names_responses(True)):
   with self.assertRaises(ValueError):s.names(2,20261021)
 def test_qfq_daily_special_fails(self):
  s=object.__new__(Session);s.daily=lambda *args:[dict(date='2006-04-01',open=10,high=11,low=9,close=10)]
  s.xdxr=lambda *args:[dict(year=2006,month=4,day=10,category=12)]
  with self.assertRaises(ValueError):s.qfq_daily(1,'600339',10,'2006-05-01')
 def test_qfq_daily_old_special_outside_window(self):
  s=object.__new__(Session);s.daily=lambda *args:[dict(date='2026-01-01',open=10,high=11,low=9,close=10)]
  s.xdxr=lambda *args:[dict(year=2006,month=4,day=10,category=12),self.e('2026-02-01',fh=1)]
  r=s.qfq_daily(1,'600339',10,'2026-03-01');self.assertAlmostEqual(r['rows'][0]['close'],9.9);self.assertFalse(r['complete_history'])
 def test_qfq_daily_empty_fails(self):
  s=object.__new__(Session);s.daily=lambda *args:[]
  with self.assertRaises(ValueError):s.qfq_daily(1,'601198',10,'2026-03-01')
 def test_response_sequence_mismatch(self):
  class Sock:
   def sendall(self,b):pass
  class Cmd:
   send_pkg=bytearray(12)
   def parseResponse(self,b):raise AssertionError('must not parse mismatched response')
  s=object.__new__(Session);s.sock=Sock();h=bytearray(16);h[5]=99
  with patch('cli.recv',return_value=(h,b'')):
   with self.assertRaises(ValueError):s.call(Cmd())
 def test_unknown_category_refused(self):
  s=object.__new__(Session);s.daily=lambda *args:[dict(date='2026-01-01',open=10,high=11,low=9,close=10)]
  s.xdxr=lambda *args:[dict(year=2026,month=2,day=1,category=99)]
  with self.assertRaises(ValueError):s.qfq_daily(1,'600125',10,'2026-03-01')
 def test_host_port_override(self):
  class S:
   def close(self):pass
  log=[]
  with patch('cli.Session',side_effect=[ConnectionRefusedError('test'),S()]) as factory:
   r=run_hosts(['127.0.0.1','example:7709'],59999,'template',lambda s:42,log)
  self.assertEqual(r,42);self.assertEqual(factory.call_args_list[1].args[:2],('example',7709));self.assertEqual(log[0]['port'],59999)
 def test_semantic_error_not_retried(self):
  class S:
   def close(self):pass
  def invalid(s):raise ValueError('wrong identity')
  with patch('cli.Session',return_value=S()) as factory:
   with self.assertRaises(ValueError):run_hosts(['a','b'],7709,'template',invalid,[])
  self.assertEqual(factory.call_count,1)
 def test_atomic_reject_nan_preserves_old(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'out.json';p.write_text('old',encoding='utf8')
   with self.assertRaises(ValueError):atomic_json(p,dict(x=float('nan')))
   self.assertEqual(p.read_text(encoding='utf8'),'old');self.assertEqual(len(list(Path(d).iterdir())),1)
 def test_atomic_replace(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'out.json';p.write_text('old',encoding='utf8');atomic_json(p,dict(ok=True))
   self.assertTrue(json.loads(p.read_text(encoding='utf8'))['ok']);self.assertEqual(len(list(Path(d).iterdir())),1)
if __name__=='__main__':unittest.main()
