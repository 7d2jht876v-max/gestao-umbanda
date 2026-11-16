import hashlib,sqlite3,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'notebook'))
from server import Store
from recover_admin import accounts,recover,RecoveryError,open_existing

class RecoveryTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.store=Store(self.temp.name)
  self.owner=self.store.bootstrap({'code':self.store.setup_code,'email':'owner@example.com','password':'original-owner-password'},True)
  with self.store.connect() as c:
   self.medium=self.store.add_user(c,'medium@example.com','original-medium-password')
   self.store.set_value(c,'cadastros',[{'id':'123','nome':'Cadastro preservado','anexo':'f'*10000}])
   c.execute('INSERT INTO radio VALUES(?,?,?,?)',(self.owner['id'],'r','{"id":"r","values":{},"lines":[]}',7))
   c.execute('INSERT INTO sessions VALUES(?,?,?)',('owner-session',self.owner['id'],9999999999))
   c.execute('INSERT INTO sessions VALUES(?,?,?)',('medium-session',self.medium['id'],9999999999))
  with self.store.connect() as c:
   self.before_docs=self.store.doc(c)
   self.before_medium=tuple(c.execute('SELECT * FROM users WHERE id=?',(self.medium['id'],)).fetchone())
 def tearDown(self):self.temp.cleanup()
 @patch('recover_admin.server_running',return_value=False)
 def test_recovers_identity_preserving_data_and_other_accounts(self,_):
  admins,count=accounts(self.store.path);self.assertEqual(count,2);self.assertEqual(admins,[{'id':self.owner['id'],'email':'owner@example.com'}])
  result=recover(self.store.path,self.owner['id'],'new-exclusive-owner-password')
  self.assertEqual(result['email'],'owner@example.com');self.assertTrue(Path(result['backup']).exists())
  with self.store.connect() as c:
   self.assertEqual(self.store.doc(c),self.before_docs)
   self.assertEqual(tuple(c.execute('SELECT * FROM users WHERE id=?',(self.medium['id'],)).fetchone()),self.before_medium)
   self.assertEqual([r[0] for r in c.execute('SELECT token FROM sessions')],['medium-session'])
   self.assertEqual(c.execute('SELECT revision FROM radio').fetchone()[0],7)
  with sqlite3.connect(result['backup']) as c:self.assertEqual(c.execute('SELECT count(*) FROM users').fetchone()[0],2)
  self.store.login({'email':'owner@example.com','password':'new-exclusive-owner-password'},'127.0.0.1')
  with self.assertRaises(Exception):self.store.login({'email':'owner@example.com','password':'original-owner-password'},'127.0.0.1')
 @patch('recover_admin.server_running',return_value=False)
 def test_will_not_promote_medium_or_create_duplicate_admin(self,_):
  with self.assertRaises(RecoveryError):recover(self.store.path,self.medium['id'],'new-password-for-medium')
  with self.assertRaises(RecoveryError):recover(self.store.path,None,'new-password-for-admin',first_email='new@example.com')
  with self.store.connect() as c:self.assertEqual(c.execute('SELECT count(*) FROM users').fetchone()[0],2)
 @patch('recover_admin.server_running',return_value=True)
 def test_rejects_running_server(self,_):
  with self.assertRaises(RecoveryError):recover(self.store.path,self.owner['id'],'new-exclusive-owner-password')
 def test_rejects_missing_database_without_creating_one(self):
  target=Path(self.temp.name)/'missing.sqlite3'
  with self.assertRaises(RecoveryError):open_existing(target)
  self.assertFalse(target.exists())
 @patch('recover_admin.server_running',return_value=False)
 def test_first_admin_only_if_no_accounts(self,_):
  with tempfile.TemporaryDirectory() as t:
   store=Store(t);result=recover(store.path,None,'exclusive-first-password',first_email='first@example.com')
   self.assertTrue(result['created']);self.assertEqual(accounts(store.path)[0][0]['email'],'first@example.com')
 def test_password_validation(self):
  for password in ['short',' valid-password-long ', 'e\u0301-long-enough-password']:
   with self.assertRaises(RecoveryError):recover(self.store.path,self.owner['id'],password)
 def test_bat_payload_matches_tested_python(self):
  root=Path(__file__).resolve().parents[1]
  lines=(root/'notebook/RECUPERAR-ADMIN.bat').read_text().splitlines()
  code='\n'.join(lines[lines.index('#===PYTHON===')+1:])+'\n'
  self.assertEqual(code,(root/'notebook/recover_admin.py').read_text())
  compile(code,'recovery-payload','exec')

if __name__=='__main__':unittest.main()
