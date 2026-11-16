import base64,importlib.util,json,ssl,sys,tempfile,threading,unittest,urllib.request,urllib.error,uuid
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'notebook'))
from server import Store,ApiError,PART,Server,Handler,local_index
from certificates import generate

class NotebookTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.store=Store(self.tmp.name)
  self.admin=self.store.bootstrap({'code':self.store.setup_code,'email':'admin@example.com','password':'exclusive-admin-123'},True)
  with self.store.connect() as c:
   self.medium=self.store.add_user(c,'medium@example.com','exclusive-medium-123')
   self.other=self.store.add_user(c,'other@example.com','exclusive-other-123')
 def tearDown(self): self.tmp.cleanup()
 def upload(self,patch,expected=None,uid=None,finish=True):
  raw=json.dumps(patch,ensure_ascii=False).encode();total=(len(raw)+PART-1)//PART;uid=uid or str(uuid.uuid4())
  for n in range(total):
   self.store.rpc(self.admin,'enviar_gestao_bloco',dict(upload_id=uid,numero=n,total=total,bytes=len(raw),payload=base64.b64encode(raw[n*PART:(n+1)*PART]).decode(),versao_esperada=expected))
  return self.store.rpc(self.admin,'concluir_gestao_delta',{'upload_id':uid}) if finish else uid
 def test_setup_and_auth(self):
  with self.assertRaises(ApiError): self.store.bootstrap({'code':self.store.setup_code,'email':'a@b.c','password':'123456789012'},False)
  with self.assertRaises(ApiError): self.store.login({'email':'admin@example.com','password':'wrong'},'127.0.0.1')
  user,token=self.store.login({'email':'admin@example.com','password':'exclusive-admin-123'},'127.0.0.1')
  self.assertEqual(self.store.user(token),user)
  self.assertIsNone(self.store.user('invalid'))
 def test_incremental_chunk_resume_and_conflict(self):
  first={'sets':{'👥 Médiuns':[{'id':'1','nome':'João','foto':'x'*300000},{'id':'2','nome':'Maria'}]},'rows':{}}
  uid=self.upload(first,finish=False)
  v1=self.store.rpc(self.admin,'concluir_gestao_delta',{'upload_id':uid})
  self.assertEqual(v1,self.store.rpc(self.admin,'concluir_gestao_delta',{'upload_id':uid}))
  with self.store.connect() as c: known=self.store.index(c)
  v2=self.upload({'sets':{},'rows':{'👥 Médiuns':[{'id':'2','nome':'Maria atualizada'}]}},v1)
  part=self.store.rpc(self.admin,'ler_gestao_delta',dict(conhecido=known,numero=0,versao_esperada=v2))
  patch=json.loads(base64.b64decode(part['payload']))
  self.assertEqual(patch,{'sets':{},'rows':{'👥 Médiuns':[{'id':'2','nome':'Maria atualizada'}]}})
  self.assertLess(part['bytes'],250)
  with self.assertRaises(ApiError): self.upload({'sets':{'bad':1},'rows':{}},v1)
  with self.store.connect() as c: self.assertNotIn('bad',self.store.doc(c))
  no_changes=self.store.rpc(self.admin,'ler_gestao_delta',dict(conhecido=part['indice'],numero=0,versao_esperada=v2))
  self.assertEqual(json.loads(base64.b64decode(no_changes['payload'])),{'sets':{},'rows':{}})
 def test_incomplete_invalid_delta_and_deletion(self):
  uid=str(uuid.uuid4());raw=b'x'*(PART+1)
  self.store.rpc(self.admin,'enviar_gestao_bloco',dict(upload_id=uid,numero=0,total=2,bytes=len(raw),payload=base64.b64encode(raw[:PART]).decode(),versao_esperada=None))
  with self.assertRaises(ApiError): self.store.rpc(self.admin,'concluir_gestao_delta',{'upload_id':uid})
  v=self.upload({'sets':{'list':[{'id':'1'},{'id':'2'}]},'rows':{}})
  v=self.upload({'sets':{'_deleted':{'list':{'1':True}}},'rows':{}},v)
  with self.store.connect() as c: self.assertEqual(self.store.doc(c)['list'],[{'id':'2'}])
 def test_role_boundaries(self):
  self.store.table(self.admin,dict(table='portal_mediuns',action='upsert',values={'email':self.medium['email'],'dados':{'medium':{'nome':'Médium'}}}))
  self.store.table(self.admin,dict(table='portal_mediuns',action='upsert',values={'email':self.other['email'],'dados':{'medium':{'nome':'Outro'}}}))
  own=self.store.table(self.medium,dict(table='portal_mediuns'))
  self.assertEqual([x['email'] for x in own],[self.medium['email']])
  self.assertEqual(self.store.table(self.medium,dict(table='portal_mediuns',filters={'email':self.other['email']})),[])
  for table in ['gestao_dados','radiestesia_fichas']:
   with self.assertRaises(ApiError): self.store.table(self.medium,dict(table=table))
  with self.assertRaises(ApiError): self.store.rpc(self.medium,'ler_gestao_delta',{})
  with self.assertRaises(ApiError): self.store.table(self.medium,dict(table='agenda_pessoal_mediuns',action='upsert',values={'user_id':self.other['id'],'entry_id':'x','dados':{}}))
 def test_radio_and_provision(self):
  record={'id':'r','values':{'nome':'Teste'},'lines':[]}
  self.assertEqual(self.store.rpc(self.admin,'salvar_ficha_radiestesia',{'record':record,'expected_revision':0}),1)
  with self.assertRaises(ApiError): self.store.rpc(self.admin,'salvar_ficha_radiestesia',{'record':record,'expected_revision':0})
  self.assertEqual(len(self.store.table(self.admin,dict(table='radiestesia_fichas',filters={'owner':self.admin['id']},columns='payload,revision'))),1)
  for email in ['new@example.com',self.medium['email']]:
   self.store.table(self.admin,dict(table='portal_mediuns',action='upsert',values={'email':email,'dados':{}}))
  result=self.store.provision(self.admin)
  self.assertEqual((result['created'],result['skipped']),(1,1));self.assertGreaterEqual(len(result['credentials'][0]['password']),12)
  self.assertEqual(self.store.provision(self.admin)['created'],0)
 def test_import_preserves_and_backup(self):
  first={'records':{'list':[{'id':'1','v':'original'}]},'radio':[]}
  self.store.import_data(self.admin,first)
  self.store.import_data(self.admin,{'records':{'list':[{'id':'1','v':'different'},{'id':'2'}]},'radio':[]})
  data=self.store.export(self.admin)['records']['list']
  self.assertEqual(len(data),3);self.assertIn({'id':'1','v':'original'},data)
  self.assertTrue(list((Path(self.tmp.name)/'backups').glob('*.sqlite3')))
  with self.assertRaises(ApiError): self.store.import_data(self.medium,first)
  self.assertNotIn('password',json.dumps(self.store.export(self.admin)))
 def test_sqlite_durability(self):
  self.upload({'sets':{'value':{'name':'durable'}},'rows':{}})
  reloaded=Store(self.tmp.name)
  with reloaded.connect() as c: self.assertEqual(reloaded.doc(c)['value']['name'],'durable')
 def test_read_parts_stable_and_only_new(self):
  v=self.upload({'sets':{'big':[{'id':'1','photo':'p'*600000}]},'rows':{}})
  first=self.store.rpc(self.admin,'ler_gestao_delta',dict(conhecido={},numero=0,versao_esperada=v))
  raw=b''.join(base64.b64decode(self.store.rpc(self.admin,'ler_gestao_delta',dict(conhecido={},numero=n,versao_esperada=v))['payload']) for n in range(first['partes']))
  self.assertEqual(len(raw),first['bytes']);self.assertEqual(len(json.loads(raw)['sets']['big'][0]['photo']),600000)
 def test_local_html_transformation(self):
  html=local_index((ROOT/'index.html').read_text())
  self.assertNotIn('supabase.min.js',html);self.assertNotIn('supabase-config.js',html)
  self.assertIn('/notebook-client.js',html);self.assertIn('removeItem(key)',html)

class HttpsTests(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.tmp=tempfile.TemporaryDirectory();cls.store=Store(cls.tmp.name);root=generate(cls.tmp.name)
  ctx=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);ctx.load_cert_chain(root/'server.pem',root/'server-key.pem')
  cls.server=Server(('127.0.0.1',0),Handler);cls.server.socket=ctx.wrap_socket(cls.server.socket,server_side=True);cls.server.store=cls.store;cls.server.allowed_hosts={'localhost','127.0.0.1'}
  cls.port=cls.server.server_address[1];cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
  cls.context=ssl.create_default_context(cafile=str(root/'ca.pem'))
 @classmethod
 def tearDownClass(cls): cls.server.shutdown();cls.server.server_close();cls.tmp.cleanup()
 def request(self,path,body=None,headers=None):
  req=urllib.request.Request('https://localhost:'+str(self.port)+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-Notebook':'1',**(headers or {})})
  return urllib.request.urlopen(req,context=self.context,timeout=5)
 def test_https_and_private_paths(self):
  self.assertTrue(json.load(self.request('/api/status'))['local'])
  for path in ['/dados/templo.sqlite3','/notebook/dados/certificados/ca-key.pem','/../server.py','/.git/config']:
   with self.assertRaises(urllib.error.HTTPError): self.request(path)
  with self.assertRaises(urllib.error.HTTPError): self.request('/api/export',{})
  with self.assertRaises(urllib.error.HTTPError): self.request('/api/setup',{'code':self.store.setup_code,'email':'admin@x.com','password':'a-long-enough-password'},{'Origin':'https://evil.example'})
 def test_cookie_and_administrator(self):
  self.request('/api/setup',{'code':self.store.setup_code,'email':'admin@x.com','password':'a-long-enough-password'}).close()
  result=self.request('/api/login',{'email':'admin@x.com','password':'a-long-enough-password'})
  cookie=result.headers['Set-Cookie'];self.assertIn('HttpOnly',cookie);self.assertIn('Secure',cookie);self.assertIn('SameSite=Strict',cookie);result.close()
  session=json.load(self.request('/api/session',headers={'Cookie':cookie.split(';')[0]}))
  self.assertEqual(session['data']['session']['user']['role'],'admin')
  result=self.request('/');html=result.read().decode();self.assertIn('/notebook-client.js',html);result.close()

if __name__=='__main__':unittest.main()
