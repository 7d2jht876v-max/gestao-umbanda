"""Gestão Umbanda: servidor HTTPS local, SQLite e sincronização incremental.
Python 3.11+. Nenhum dado é enviado a serviços externos.
"""
from __future__ import annotations
import argparse, base64, datetime as dt, hashlib, hmac, http.cookies, ipaddress
import json, mimetypes, os, secrets, socket, sqlite3, ssl, threading, time, uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit

PART = 196608
MAX_BYTES = 52428800
HERE = Path(__file__).resolve().parent
WEB = HERE / 'web' if (HERE / 'web').exists() else HERE.parent

def dump(x):
    return json.dumps(x, ensure_ascii=False, separators=(',', ':'), allow_nan=False)

def stamp():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='microseconds')

def database_text(x):
    if isinstance(x, dict):
        keys = sorted(x, key=lambda k: (len(k.encode()), k.encode()))
        return '{' + ', '.join(dump(k) + ': ' + database_text(x[k]) for k in keys) + '}'
    if isinstance(x, list):
        return '[' + ', '.join(map(database_text, x)) + ']'
    if isinstance(x, float) and x.is_integer():
        return str(int(x))
    return dump(x)

def digest(x):
    return hashlib.sha256(database_text(x).encode()).hexdigest()

def keyed(x):
    return isinstance(x, list) and all(isinstance(r, dict) and r.get('id') not in (None, '') for r in x) and len({str(r['id']) for r in x}) == len(x)

class ApiError(Exception):
    def __init__(self, message, code='22023', status=400):
        self.message, self.code, self.status = message, code, status

class Store:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.path = self.folder / 'templo.sqlite3'
        self.lock = threading.RLock()
        self.setup_code = secrets.token_urlsafe(24)
        self.failures = {}
        with self.connect() as c:
            c.executescript('''
            PRAGMA journal_mode=WAL;
            CREATE TABLE IF NOT EXISTS users(id TEXT PRIMARY KEY,email TEXT UNIQUE NOT NULL,role TEXT NOT NULL,salt TEXT NOT NULL,password TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS sessions(token TEXT PRIMARY KEY,user_id TEXT NOT NULL,expires REAL NOT NULL);
            CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY,v TEXT);
            CREATE TABLE IF NOT EXISTS values_data(tab TEXT NOT NULL,id TEXT NOT NULL,pos INTEGER NOT NULL,payload TEXT NOT NULL,hash TEXT NOT NULL,PRIMARY KEY(tab,id));
            CREATE TABLE IF NOT EXISTS tab_types(tab TEXT PRIMARY KEY,kind TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS portals(email TEXT PRIMARY KEY,payload TEXT NOT NULL,updated TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS agenda(owner TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,PRIMARY KEY(owner,id));
            CREATE TABLE IF NOT EXISTS radio(owner TEXT NOT NULL,id TEXT NOT NULL,payload TEXT NOT NULL,revision INTEGER NOT NULL,PRIMARY KEY(owner,id));
            CREATE TABLE IF NOT EXISTS uploads(id TEXT PRIMARY KEY,owner TEXT NOT NULL,expected TEXT,total INTEGER NOT NULL,bytes INTEGER NOT NULL,complete TEXT,created REAL NOT NULL);
            ''')
        (self.folder / 'uploads').mkdir(exist_ok=True)
        (self.folder / 'backups').mkdir(exist_ok=True)
        try:
            self.folder.chmod(0o700)
            self.path.chmod(0o600)
        except OSError:
            pass

    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        return c

    def backup(self, force=False):
        day = dt.date.today().isoformat()
        target = self.folder / 'backups' / ('templo-' + (stamp().replace(':', '-') if force else day) + '.sqlite3')
        with self.lock:
            if not target.exists():
                with self.connect() as src, sqlite3.connect(target) as dst:
                    src.backup(dst)
        return target

    def admin(self, user):
        if not user or user['role'] != 'admin':
            raise ApiError('Acesso exclusivo do administrador.', '42501', 403)

    def add_user(self, c, email, password, role='medium'):
        email = str(email).strip().lower()
        if '@' not in email or len(email) > 254 or not isinstance(password, str) or len(password) < 12:
            raise ApiError('Informe e-mail e senha com pelo menos 12 caracteres.')
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
        user = dict(id=str(uuid.uuid4()), email=email, role=role)
        c.execute('INSERT INTO users VALUES(?,?,?,?,?)', (user['id'], email, role, salt, hashed))
        return user

    def bootstrap(self, args, local):
        if not local or not hmac.compare_digest(str(args.get('code', '')), self.setup_code):
            raise ApiError('A configuração inicial deve ser feita no próprio notebook com o código da janela do servidor.', '42501', 403)
        with self.lock, self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            if c.execute('SELECT 1 FROM users LIMIT 1').fetchone():
                raise ApiError('Administrador já configurado.', '42501', 403)
            user = self.add_user(c, args.get('email'), args.get('password'), 'admin')
        return user

    def login(self, args, ip):
        email = str(args.get('email', '')).strip().lower()
        key = ('source', ip, email)
        account_key = ('account', email)
        now = time.time()
        with self.lock:
            attempts = [t for t in self.failures.get(key, []) if t > now - 600]
            account_attempts = [t for t in self.failures.get(account_key, []) if t > now - 600]
            if len(attempts) >= 5 or len(account_attempts) >= 5:
                raise ApiError('Muitas tentativas. Aguarde 10 minutos.', '429', 429)
            self.failures[key] = attempts + [now]
            self.failures[account_key] = account_attempts + [now]
            if len(self.failures) > 1000:
                self.failures = {k: v for k, v in self.failures.items() if v[-1] > now - 600}
        with self.connect() as c:
            row = c.execute('SELECT * FROM users WHERE email=?', (key[1],)).fetchone()
            salt = row['salt'] if row else '00' * 16
            check = hashlib.pbkdf2_hmac('sha256', str(args.get('password', '')).encode(), bytes.fromhex(salt), 600000).hex()
            if not row or not hmac.compare_digest(check, row['password']):
                raise ApiError('E-mail ou senha incorretos.', '401', 401)
            token = secrets.token_urlsafe(32)
            c.execute('DELETE FROM sessions WHERE expires<?', (now,))
            c.execute('INSERT INTO sessions VALUES(?,?,?)', (hashlib.sha256(token.encode()).hexdigest(), row['id'], now + 28800))
        with self.lock:
            self.failures.pop(key, None)
            self.failures.pop(account_key, None)
        return dict(id=row['id'], email=row['email'], role=row['role']), token

    def user(self, token):
        with self.connect() as c:
            row = c.execute('SELECT u.id,u.email,u.role FROM sessions s JOIN users u ON u.id=s.user_id WHERE s.token=? AND s.expires>?', (hashlib.sha256(token.encode()).hexdigest(), time.time())).fetchone()
            return dict(row) if row else None

    def index(self, c):
        result = {}
        for tab in c.execute('SELECT * FROM tab_types'):
            rows = c.execute('SELECT id,hash FROM values_data WHERE tab=? ORDER BY pos', (tab['tab'],)).fetchall()
            result[tab['tab']] = {'rows': {r['id']: r['hash'] for r in rows}} if tab['kind'] == 'rows' else {'hash': rows[0]['hash']}
        return result

    def doc(self, c):
        result = {}
        for tab in c.execute('SELECT * FROM tab_types'):
            rows = c.execute('SELECT payload FROM values_data WHERE tab=? ORDER BY pos', (tab['tab'],)).fetchall()
            result[tab['tab']] = [json.loads(r[0]) for r in rows] if tab['kind'] == 'rows' else json.loads(rows[0][0])
        return result

    def version(self, c):
        row = c.execute("SELECT v FROM meta WHERE k='version'").fetchone()
        return row[0] if row else None

    def set_value(self, c, tab, value):
        kind = 'rows' if keyed(value) else 'value'
        c.execute('INSERT OR REPLACE INTO tab_types VALUES(?,?)', (tab, kind))
        c.execute('DELETE FROM values_data WHERE tab=?', (tab,))
        values = value if kind == 'rows' else [value]
        for pos, val in enumerate(values):
            c.execute('INSERT INTO values_data VALUES(?,?,?,?,?)', (tab, str(val['id']) if kind == 'rows' else '', pos, dump(val), digest(val)))

    def patch(self, c, patch):
        if not isinstance(patch, dict) or not isinstance(patch.get('sets'), dict) or not isinstance(patch.get('rows'), dict):
            raise ApiError('Alterações inválidas.')
        for tab, value in patch['sets'].items():
            if not isinstance(tab, str): raise ApiError('Categoria inválida.')
            self.set_value(c, tab, value)
        for tab, rows in patch['rows'].items():
            if not keyed(rows): raise ApiError('Registros inválidos ou repetidos.')
            kind = c.execute('SELECT kind FROM tab_types WHERE tab=?', (tab,)).fetchone()
            if kind and kind[0] != 'rows': raise ApiError('Formato da categoria mudou; atualize antes de enviar.', '40001', 409)
            c.execute("INSERT OR IGNORE INTO tab_types VALUES(?,'rows')", (tab,))
            pos = c.execute('SELECT coalesce(max(pos),-1)+1 FROM values_data WHERE tab=?', (tab,)).fetchone()[0]
            for row in rows:
                rid = str(row['id'])
                previous = c.execute('SELECT hash FROM values_data WHERE tab=? AND id=?', (tab, rid)).fetchone()
                hashed = digest(row)
                if previous and previous[0] == hashed: continue
                c.execute('INSERT INTO values_data VALUES(?,?,?,?,?) ON CONFLICT(tab,id) DO UPDATE SET payload=excluded.payload,hash=excluded.hash', (tab, rid, pos, dump(row), hashed))
                pos += 1
        deleted = c.execute("SELECT payload FROM values_data WHERE tab='_deleted' AND id='' ").fetchone()
        if deleted:
            dead = json.loads(deleted[0])
            if not isinstance(dead, dict): raise ApiError('Exclusões inválidas.')
            for tab, ids in dead.items():
                if not isinstance(ids, dict): raise ApiError('Exclusões inválidas.')
                c.executemany('DELETE FROM values_data WHERE tab=? AND id=?', [(tab, str(rid)) for rid in ids])

    def rpc(self, user, name, args):
        if name == 'salvar_ficha_radiestesia':
            self.admin(user)
            self.backup()
            record = args['record']
            if not isinstance(record, dict) or not record.get('id'): raise ApiError('Ficha inválida.')
            with self.lock, self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                prev = c.execute('SELECT revision FROM radio WHERE owner=? AND id=?', (user['id'], record['id'])).fetchone()
                revision = prev[0] if prev else 0
                if revision != args.get('expected_revision', 0): raise ApiError('Ficha alterada em outro aparelho.', '40001', 409)
                c.execute('INSERT OR REPLACE INTO radio VALUES(?,?,?,?)', (user['id'], record['id'], dump(record), revision + 1))
            return revision + 1
        self.admin(user)
        if name == 'indice_notebook':
            with self.connect() as c:
                c.execute('BEGIN')
                if self.version(c) != args.get('versao_esperada'): raise ApiError('Dados alterados em outro aparelho.', '40001', 409)
                return self.index(c)
        if name == 'ler_gestao_delta':
            known, number = args.get('conhecido', {}), args.get('numero', 0)
            if not isinstance(known, dict) or not isinstance(number, int) or not 0 <= number < 400: raise ApiError('Parte inválida.')
            with self.connect() as c:
                c.execute('BEGIN')
                version = self.version(c)
                if version != args.get('versao_esperada'): raise ApiError('Dados alterados em outro aparelho.', '40001', 409)
                index = self.index(c)
                # Cache the immutable read snapshot on disk once per version/index.
                cache_id = hashlib.sha256((user['id'] + dump(known) + str(version)).encode()).hexdigest()
                target = self.folder / 'uploads' / ('read-' + cache_id)
                with self.lock:
                    if not target.exists():
                        patch = {'sets': {}, 'rows': {}}
                        for tab, entry in index.items():
                            if entry == known.get(tab): continue
                            values = c.execute('SELECT id,payload,hash FROM values_data WHERE tab=? ORDER BY pos', (tab,)).fetchall()
                            if 'rows' in entry and isinstance(known.get(tab, {}).get('rows'), dict):
                                patch['rows'][tab] = [json.loads(r['payload']) for r in values if r['hash'] != known[tab]['rows'].get(r['id'])]
                            else:
                                patch['sets'][tab] = [json.loads(r['payload']) for r in values] if 'rows' in entry else json.loads(values[0]['payload'])
                        raw = dump(patch).encode()
                        temp = target.with_suffix('.tmp')
                        temp.write_bytes(raw)
                        temp.replace(target)
            size = target.stat().st_size
            with target.open('rb') as f:
                f.seek(number * PART)
                payload = base64.b64encode(f.read(PART)).decode()
            return dict(versao=version, numero=number, partes=max(1, (size+PART-1)//PART), bytes=size, payload=payload, indice=index if number == 0 else None)
        if name == 'enviar_gestao_bloco':
            upload_id = str(uuid.UUID(args['upload_id']))
            number, total, size = args['numero'], args['total'], args['bytes']
            if not all(type(v) is int for v in (number, total, size)) or not 1 <= size <= MAX_BYTES or total != (size+PART-1)//PART or not 0 <= number < total: raise ApiError('Bloco inválido.')
            raw = base64.b64decode(args['payload'], validate=True)
            if len(raw) != min(PART, size-number*PART): raise ApiError('Tamanho inválido.')
            with self.lock, self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                prev = c.execute('SELECT * FROM uploads WHERE id=?', (upload_id,)).fetchone()
                if prev and (prev['owner'] != user['id'] or prev['total'] != total or prev['bytes'] != size or prev['expected'] != args.get('versao_esperada')): raise ApiError('Envio diferente.')
                if prev and prev['complete']: return True
                if not prev:
                    c.execute('INSERT INTO uploads VALUES(?,?,?,?,?,?,?)', (upload_id, user['id'], args.get('versao_esperada'), total, size, None, time.time()))
                folder = self.folder / 'uploads' / upload_id
                folder.mkdir(exist_ok=True)
                target = folder / str(number)
                temp = target.with_suffix('.tmp')
                temp.write_bytes(raw)
                temp.replace(target)
            return True
        if name == 'concluir_gestao_delta':
            upload_id = str(uuid.UUID(args['upload_id']))
            self.backup()
            with self.lock, self.connect() as c:
                c.execute('BEGIN IMMEDIATE')
                upload = c.execute('SELECT * FROM uploads WHERE id=? AND owner=?', (upload_id, user['id'])).fetchone()
                if not upload: raise ApiError('Envio não encontrado.')
                if upload['complete']: return upload['complete']
                if self.version(c) != upload['expected']: raise ApiError('Dados alterados em outro aparelho.', '40001', 409)
                folder = self.folder / 'uploads' / upload_id
                if any(not (folder / str(n)).exists() for n in range(upload['total'])): raise ApiError('Envio incompleto.')
                raw = b''.join((folder / str(n)).read_bytes() for n in range(upload['total']))
                if len(raw) != upload['bytes']: raise ApiError('Envio incompleto.')
                self.patch(c, json.loads(raw))
                version = stamp()
                c.execute("INSERT OR REPLACE INTO meta VALUES('version',?)", (version,))
                c.execute('UPDATE uploads SET complete=? WHERE id=?', (version, upload_id))
            for part in folder.iterdir(): part.unlink()
            folder.rmdir()
            return version
        raise ApiError('Operação não disponível no servidor do notebook.')

    def table(self, user, args):
        table, action = args.get('table'), args.get('action', 'select')
        filters = args.get('filters', {})
        with self.lock, self.connect() as c:
            if table == 'perfis' and action == 'select':
                rows = [dict(id=user['id'], perfil=user['role'])] if filters.get('id', user['id']) == user['id'] else []
            elif table == 'gestao_dados' and action == 'select':
                self.admin(user)
                version = self.version(c)
                rows = [] if version is None else [dict(atualizado_em=version, id='templo')]
                if rows and 'conteudo' in args.get('columns', ''): rows[0]['conteudo'] = self.doc(c)
            elif table == 'portal_mediuns':
                if action == 'select':
                    email = filters.get('email') if user['role'] == 'admin' else user['email']
                    selected = c.execute('SELECT * FROM portals WHERE email=?', (email,)) if email else c.execute('SELECT * FROM portals')
                    rows = [dict(email=r['email'], dados=json.loads(r['payload']), atualizado_em=r['updated']) for r in selected]
                elif action == 'upsert':
                    self.admin(user)
                    items = args.get('values', [])
                    if not isinstance(items, list): items = [items]
                    if len(items) > 1: raise ApiError('Publique um médium de cada vez.')
                    rows = []
                    for item in items:
                        email = str(item['email']).strip().lower()
                        prev = c.execute('SELECT payload FROM portals WHERE email=?', (email,)).fetchone()
                        payload = dump(item['dados'])
                        if not prev or prev[0] != payload:
                            c.execute('INSERT OR REPLACE INTO portals VALUES(?,?,?)', (email, payload, stamp()))
                        rows.append(item)
                else: raise ApiError('Operação inválida.')
            elif table == 'agenda_pessoal_mediuns':
                if action == 'select':
                    rows = [dict(user_id=user['id'], entry_id=r['id'], dados=json.loads(r['payload'])) for r in c.execute('SELECT * FROM agenda WHERE owner=?', (user['id'],))]
                elif action == 'upsert':
                    item = args['values']
                    if item.get('user_id') != user['id']: raise ApiError('Agenda de outra conta.', '42501', 403)
                    c.execute('INSERT OR REPLACE INTO agenda VALUES(?,?,?)', (user['id'], str(item['entry_id']), dump(item['dados'])))
                    rows = [item]
                else: raise ApiError('Operação inválida.')
            elif table == 'radiestesia_fichas' and action == 'select':
                self.admin(user)
                rows = [dict(owner=user['id'], payload=json.loads(r['payload']), revision=r['revision']) for r in c.execute('SELECT * FROM radio WHERE owner=?', (user['id'],))]
            else: raise ApiError('Acesso não permitido.', '42501', 403)
        rows = [r for r in rows if all(r.get(k) == v for k, v in filters.items())]
        columns = args.get('columns', '*')
        if columns != '*': rows = [{k: r[k] for k in columns.split(',') if k in r} for r in rows]
        if args.get('limit') is not None: rows = rows[:max(0, min(int(args['limit']), 1000))]
        if args.get('single'):
            if not rows and args['single'] == 'maybe': return None
            if len(rows) != 1: raise ApiError('Registro não encontrado.', 'PGRST116', 404)
            return rows[0]
        return rows

    def provision(self, user):
        self.admin(user)
        created, skipped, credentials = 0, 0, []
        with self.lock, self.connect() as c:
            for row in c.execute('SELECT email FROM portals').fetchall():
                if c.execute('SELECT 1 FROM users WHERE email=?', (row['email'],)).fetchone():
                    skipped += 1
                    continue
                password = secrets.token_urlsafe(15)
                self.add_user(c, row['email'], password)
                credentials.append(dict(email=row['email'], password=password))
                created += 1
        return dict(created=created, updated=0, skipped=skipped, credentials=credentials)

    def export(self, user):
        self.admin(user)
        with self.connect() as c:
            return dict(format='gestao-notebook', version=1, exportedAt=stamp(), records=self.doc(c), radio=[json.loads(r[0]) for r in c.execute('SELECT payload FROM radio WHERE owner=?', (user['id'],))])

    def import_data(self, user, body):
        self.admin(user)
        records = body.get('records')
        if not isinstance(records, dict) or not records: raise ApiError('Backup sem registros válidos.')
        radio = body.get('radio', [])
        if not isinstance(radio, list) or any(not isinstance(r, dict) or not r.get('id') or not isinstance(r.get('values'), dict) or not isinstance(r.get('lines'), list) for r in radio): raise ApiError('Fichas inválidas.')
        self.backup(force=True)
        conflicts, added = 0, 0
        with self.lock, self.connect() as c:
            c.execute('BEGIN IMMEDIATE')
            existing = self.doc(c)
            for tab, val in records.items():
                if tab not in existing: self.set_value(c, tab, val); added += len(val) if isinstance(val, list) else 1; continue
                if existing[tab] == val: continue
                if keyed(val) and keyed(existing[tab]):
                    old = {str(r['id']): r for r in existing[tab]}
                    changes = []
                    for row in val:
                        rid = str(row['id'])
                        if rid not in old: changes.append(row); added += 1
                        elif old[rid] != row:
                            copy = dict(row, id=str(uuid.uuid4()), _syncConflict='Cópia preservada da importação')
                            changes.append(copy); conflicts += 1
                    self.patch(c, {'sets': {}, 'rows': {tab: changes}})
                elif isinstance(val, dict) and isinstance(existing[tab], dict):
                    # Preserve current values on collisions; original import is retained verbatim below.
                    merged = dict(val, **existing[tab])
                    conflicts += sum(k in existing[tab] and existing[tab][k] != v for k, v in val.items())
                    self.set_value(c, tab, merged)
                else: conflicts += 1
            for record in radio:
                prior = c.execute('SELECT payload FROM radio WHERE owner=? AND id=?', (user['id'], record['id'])).fetchone()
                if prior and json.loads(prior[0]) == record: continue
                if prior:
                    record = json.loads(dump(record)); record['id'] = str(uuid.uuid4()); conflicts += 1
                c.execute('INSERT INTO radio VALUES(?,?,?,1)', (user['id'], record['id'], dump(record)))
            c.execute("INSERT OR REPLACE INTO meta VALUES('version',?)", (stamp(),))
        target = self.folder / ('importacao-' + stamp().replace(':', '-') + '.json')
        target.write_text(dump(body), encoding='utf-8')
        return dict(added=added, conflicts=conflicts)

class Handler(BaseHTTPRequestHandler):
    server_version = 'GestaoNotebook/1'
    def log_message(self, fmt, *args):
        # No URLs, credentials, patient names or request bodies in logs.
        pass
    def send(self, status, value, content_type='application/json; charset=utf-8', cookie=None):
        raw = value if isinstance(value, bytes) else dump(value).encode()
        self.send_response(status)
        for k, v in {'Content-Type':content_type,'Content-Length':str(len(raw)),'Cache-Control':'no-store','X-Content-Type-Options':'nosniff','Referrer-Policy':'no-referrer','X-Frame-Options':'DENY'}.items(): self.send_header(k,v)
        if cookie: self.send_header('Set-Cookie', cookie)
        self.end_headers(); self.wfile.write(raw)
    def token(self):
        try: return http.cookies.SimpleCookie(self.headers.get('Cookie',''))['notebook_session'].value
        except (KeyError, http.cookies.CookieError): return ''
    def check_host(self):
        host = self.headers.get('Host', '').split(':')[0].lower()
        if host not in self.server.allowed_hosts: raise ApiError('Endereço não autorizado.', '403', 403)
    def public_request(self):
        return self.headers.get('Host', '').split(':')[0].lower() not in self.server.local_hosts
    def body(self):
        if self.headers.get_content_type() != 'application/json' or self.headers.get('X-Notebook') != '1': raise ApiError('Requisição inválida.', '403', 403)
        origin = self.headers.get('Origin')
        if origin != 'https://' + self.headers.get('Host',''):
            raise ApiError('Origem não autorizada.', '403', 403)
        size = int(self.headers.get('Content-Length', '0'))
        limit=MAX_BYTES+1048576 if urlsplit(self.path).path in ('/api/import','/api/table','/api/rpc') else 16384
        if not 1 <= size <= limit: raise ApiError('Requisição excede o tamanho permitido.', '413', 413)
        result = json.loads(self.rfile.read(size))
        if not isinstance(result, dict): raise ApiError('Requisição inválida.')
        return result
    def do_GET(self): self.run_request(False)
    def do_POST(self): self.run_request(True)
    def run_request(self, post):
        try:
            self.connection.settimeout(30)
            self.check_host()
            peer = ipaddress.ip_address(self.client_address[0])
            if not (peer.is_private or peer.is_loopback): raise ApiError('Acesso limitado à rede local.', '403', 403)
            path = urlsplit(self.path).path
            store = self.server.store
            if not post and path in ('/api/status','/auth/v1/health'):
                with store.connect() as c: configured=bool(c.execute('SELECT 1 FROM users LIMIT 1').fetchone())
                return self.send(200,dict(configured=configured,local=peer.is_loopback))
            if self.public_request() and path in ('/gestao-notebook.html', '/configurar', '/api/setup', '/api/provision', '/api/export', '/api/import', '/api/reset-user', '/api/users'):
                raise ApiError('Administração disponível somente no notebook ou na rede local.', '403', 403)
            if post and path == '/api/setup':
                local_setup = peer.is_loopback and self.headers.get('Host', '').split(':')[0].lower() == 'localhost'
                return self.send(200,dict(data=store.bootstrap(self.body(),local_setup),error=None))
            if post and path == '/api/login':
                user, token = store.login(self.body(), self.client_address[0])
                return self.send(200,dict(data=dict(user=user),error=None),cookie='notebook_session='+token+'; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=28800')
            user = store.user(self.token())
            if not post and path == '/api/session': return self.send(200,dict(data=dict(session=dict(user=user) if user else None),error=None))
            if path.startswith('/api/'):
                if not user: raise ApiError('Entre com sua conta do servidor do notebook.', '401', 401)
                if not post: raise ApiError('Método inválido.', '405', 405)
                args = self.body()
                if path == '/api/logout':
                    with store.connect() as c: c.execute('DELETE FROM sessions WHERE token=?',(hashlib.sha256(self.token().encode()).hexdigest(),))
                    return self.send(200,dict(data=None,error=None),cookie='notebook_session=; Path=/; HttpOnly; Secure; SameSite=Strict; Max-Age=0')
                if self.public_request() and user['role'] == 'admin':
                    raise ApiError('Administração disponível somente no notebook ou na rede local.', '403', 403)
                if path == '/api/table': result=store.table(user,args)
                elif path == '/api/rpc': result=store.rpc(user,args['name'],args.get('args',{}))
                elif path == '/api/provision': result=store.provision(user)
                elif path == '/api/export': result=store.export(user)
                elif path == '/api/import': result=store.import_data(user,args)
                elif path == '/api/reset-user':
                    store.admin(user)
                    password=args.get('password','')
                    if not isinstance(password,str) or len(password)<12: raise ApiError('Use uma senha com pelo menos 12 caracteres.')
                    store.backup(force=True)
                    with store.lock, store.connect() as c:
                        target=c.execute('SELECT id FROM users WHERE email=?',(str(args.get('email','')).strip().lower(),)).fetchone()
                        if not target: raise ApiError('E-mail não encontrado.')
                        salt=secrets.token_hex(16)
                        hashed=hashlib.pbkdf2_hmac('sha256',password.encode(),bytes.fromhex(salt),600000).hex()
                        c.execute('UPDATE users SET salt=?,password=? WHERE id=?',(salt,hashed,target[0]))
                        c.execute('DELETE FROM sessions WHERE user_id=?',(target[0],))
                    result=dict(updated=True)
                elif path == '/api/users':
                    store.admin(user)
                    with store.lock, store.connect() as c: result=store.add_user(c,args.get('email'),args.get('password'))
                else: raise ApiError('Operação não disponível.', '404',404)
                return self.send(200,dict(data=result,error=None))
            if post: raise ApiError('Página não encontrada.', '404',404)
            assets={'/':'index.html','/index.html':'index.html','/notebook-client.js':'notebook/notebook-client.js','/gestao-notebook.html':'notebook/manage.html','/manifest.webmanifest':'manifest.webmanifest','/install.js':'install.js','/baralho-cigano.html':'baralho-cigano.html','/configurar':'notebook/manage.html'}
            if path.startswith('/icons/') and Path(path).name in {'icon-192.png','icon-1024.png','icon-512.png','apple-touch-icon.png'}: asset=path[1:]
            elif path in assets: asset=assets[path]
            else: raise ApiError('Página não encontrada.', '404',404)
            raw=(WEB/asset).read_bytes()
            if asset=='index.html': raw=local_index(raw.decode()).encode()
            if asset=='manifest.webmanifest':
                manifest=json.loads(raw);manifest.update(start_url='/',scope='/',id='/');raw=dump(manifest).encode()
            if asset=='install.js': raw=b'/* Local HTTPS server; no remote service worker. */'
            return self.send(200,raw,mimetypes.guess_type(asset)[0] or 'application/octet-stream')
        except ApiError as e: self.send(e.status,dict(data=None,error=dict(message=e.message,code=e.code)))
        except (ValueError,KeyError,TypeError,sqlite3.IntegrityError): self.send(400,dict(data=None,error=dict(message='Dados inválidos ou e-mail já cadastrado.',code='22023')))
        except (ConnectionError,TimeoutError,ssl.SSLError): pass
        except Exception:
            self.send(500,dict(data=None,error=dict(message='Não foi possível concluir. Os dados confirmados foram mantidos.',code='500')))

def local_index(source):
    source=source.replace('<script src="https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2/dist/umd/supabase.min.js"></script>', '<script src="/notebook-client.js"></script>')
    import re
    source=re.sub(r'<script src="\./supabase-config\.js[^\"]*"></script>', '', source)
    # Preserve the public application's visible release number on the notebook.
    # Only the network transport is local; the web interface remains version 217.
    source=source.replace('async flush(){await tail;if(failure)throw failure;}', '''removeItem(key){key=String(key);if(!managed(key)){native.removeItem(key);return;}const previous=cache.get(key);cache.delete(key);tail=tail.catch(()=>{}).then(()=>new Promise((resolve,reject)=>{const tx=db.transaction('values','readwrite');tx.objectStore('values').delete(key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error);})).catch(error=>{if(!cache.has(key)&&previous!==undefined)cache.set(key,previous);failure=error;showError(error);throw error;});tail.catch(()=>{});},
async flush(){await tail;if(failure)throw failure;}''')

    # Keep the server-returned index; regenerate mismatch-free index after confirmed upload via a lightweight RPC.
    source=source.replace('if(push)localStorage.setItem(indexKey,JSON.stringify(await createSyncIndex(merged.data)));', "if(push){const indexed=await notebookAPI('/api/rpc',{name:'indice_notebook',args:{versao_esperada:row?.atualizado_em||null}});if(indexed.error)throw indexed.error;localStorage.setItem(indexKey,JSON.stringify(indexed.data));}")
    source=source.replace("url.searchParams.set('v','217');", "url.searchParams.set('v','notebook-1');")
    source=source.replace('Cadastrar acessos com senha padrão','Criar acessos dos médiuns')
    source=source.replace('Cadastrando acessos dos e-mails publicados…','Criando acessos dos e-mails publicados…')
    source=source.replace('Execute o SQL de configuração: ', 'Servidor do notebook: ')
    source=source.replace('cadastrados no Supabase','do servidor do notebook')
    source=source.replace('Supabase','servidor do notebook')
    source=source.replace('em outra rede (por exemplo, dados móveis)', 'na mesma rede Wi-Fi do notebook')
    source=source.replace('Os médiuns podem entrar com o e-mail cadastrado e a senha padrão.', 'As senhas exclusivas foram apresentadas na janela de acessos.')
    source=source.replace('Abra o app no notebook ou iPhone com a mesma conta e aguarde até 15 segundos.', 'Abra este endereço do notebook no iPhone, na mesma rede Wi-Fi e com a mesma conta.')
    source=source.replace('na nuvem','no notebook').replace('à nuvem','ao notebook').replace('da nuvem','do notebook')
    # A second paragraph inside the CSS grid header overlaps the version label.
    # Keep the server-management link outside the header and always accessible.
    source=source.replace('</header>','</header><div id="notebook-server-link" style="padding:10px 18px;text-align:center;background:#f1e7dd;border-bottom:1px solid #d6bfae"><a href="/gestao-notebook.html" style="color:#54351f;font-weight:700">Servidor: importar dados, backup e acessos</a></div>',1)
    return source

class Server(ThreadingHTTPServer):
    daemon_threads=True
    request_queue_size=16
    def get_request(self):
        conn,addr=super().get_request()
        conn.settimeout(30)
        return conn,addr

def addresses():
    result={'127.0.0.1'}
    try:
        result.update(a[4][0] for a in socket.getaddrinfo(socket.gethostname(),None,socket.AF_INET))
        with socket.socket(socket.AF_INET,socket.SOCK_DGRAM) as s:
            s.connect(('192.0.2.1',80));result.add(s.getsockname()[0])
    except OSError: pass
    return sorted(ip for ip in result if ipaddress.ip_address(ip).is_private or ipaddress.ip_address(ip).is_loopback)

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--data',default=str(HERE/'dados'))
    parser.add_argument('--port',type=int,default=8787)
    args=parser.parse_args()
    store=Store(args.data)
    certs=Path(args.data)/'certificados'
    if not (certs/'server.pem').exists(): raise SystemExit('Execute primeiro: python notebook/certificates.py --data "'+args.data+'"')
    context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.minimum_version=ssl.TLSVersion.TLSv1_2
    context.load_cert_chain(certs/'server.pem',certs/'server-key.pem')
    server=Server(('0.0.0.0',args.port),Handler)
    server.socket=context.wrap_socket(server.socket,server_side=True)
    server.store=store
    server.local_hosts={'localhost',socket.gethostname().lower(),*addresses()}
    public_host=os.environ.get('GESTAO_PUBLIC_HOST', '').strip().lower()
    if public_host and (':' in public_host or '/' in public_host or not public_host.endswith('.ts.net')):
        raise SystemExit('GESTAO_PUBLIC_HOST deve ser somente um hostname .ts.net, sem https:// ou porta.')
    server.allowed_hosts=server.local_hosts | ({public_host} if public_host else set())
    print('\nGESTÃO UMBANDA — SERVIDOR DO NOTEBOOK\nMantenha esta janela aberta. Ctrl+C para encerrar.\n')
    print('No notebook: https://localhost:'+str(args.port)+'/configurar')
    print('Código de configuração inicial: '+store.setup_code)
    for ip in addresses():
        if ip!='127.0.0.1': print('No iPhone (mesmo Wi-Fi): https://'+ip+':'+str(args.port)+'/')
    print('Os dados ficam em: '+str(Path(args.data).resolve()))
    def cleanup():
        while True:
            time.sleep(3600)
            for cached in (store.folder/'uploads').glob('read-*'):
                try:
                    if cached.stat().st_mtime < time.time()-86400: cached.unlink()
                except OSError: pass
    threading.Thread(target=cleanup,daemon=True).start()
    try: server.serve_forever()
    except KeyboardInterrupt: print('\nEncerrando com os dados salvos.')
    finally: server.server_close()

if __name__=='__main__': main()
