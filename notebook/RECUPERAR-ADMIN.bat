@echo off
setlocal
set "GESTAO_RECOVERY_FILE=%~f0"
echo Recuperacao local do administrador - Gestao Umbanda
echo A janela de recuperacao abrira em instantes.
echo Feche o servidor INICIAR.bat antes de salvar a nova senha.
py -3 -X utf8 -c "import os,pathlib; __file__=os.environ['GESTAO_RECOVERY_FILE']; lines=pathlib.Path(os.environ['GESTAO_RECOVERY_FILE']).read_text(encoding='utf-8').splitlines(); exec(compile(chr(10).join(lines[lines.index('#===PYTHON===')+1:]),os.environ['GESTAO_RECOVERY_FILE'],'exec'))"
if errorlevel 1 (
 echo.
 echo Nao foi possivel abrir a janela. Fotografe a mensagem acima para obter ajuda.
 pause
)
exit /b
#===PYTHON===
"""Local recovery for the notebook edition. Does not contact any cloud service."""
from pathlib import Path
import datetime as dt
import hashlib
import hmac
import secrets
import socket
import sqlite3
import unicodedata
import uuid

class RecoveryError(Exception):
    pass

def open_existing(path):
    path = Path(path).expanduser().resolve()
    if not path.is_file():
        raise RecoveryError('O banco não foi encontrado. Selecione o arquivo templo.sqlite3 dentro da pasta dados do aplicativo.')
    conn = sqlite3.connect(path.as_uri() + '?mode=rw', uri=True, timeout=5)
    conn.row_factory = sqlite3.Row
    try:
        users = {r['name'] for r in conn.execute('PRAGMA table_info(users)')}
        sessions = {r['name'] for r in conn.execute('PRAGMA table_info(sessions)')}
        if not {'id','email','role','salt','password'} <= users or not {'token','user_id','expires'} <= sessions:
            raise RecoveryError('Este arquivo não é o banco da versão Notebook 1.0. Nenhum dado foi alterado.')
    except Exception:
        conn.close()
        raise
    return conn

def accounts(path):
    conn = open_existing(path)
    try:
        admins = [dict(row) for row in conn.execute("SELECT id,email FROM users WHERE role='admin' ORDER BY email")]
        return admins, conn.execute('SELECT count(*) FROM users').fetchone()[0]
    finally:
        conn.close()

def server_running():
    try:
        with socket.create_connection(('127.0.0.1', 8787), timeout=0.5):
            return True
    except OSError:
        return False

def recover(path, account_id, password, *, first_email=None):
    if not isinstance(password, str) or len(password) < 12:
        raise RecoveryError('A nova senha precisa ter pelo menos 12 caracteres.')
    if password != unicodedata.normalize('NFC', password).strip():
        raise RecoveryError('Não use espaços no começo ou no fim da senha. Digite novamente os caracteres acentuados, se houver.')
    if server_running():
        raise RecoveryError('Feche o servidor antes de continuar: na janela preta do INICIAR.bat, pressione Ctrl+C. Depois volte aqui e tente novamente.')
    path = Path(path).resolve()
    conn = open_existing(path)
    backup = None
    try:
        if conn.execute('PRAGMA quick_check').fetchone()[0] != 'ok':
            raise RecoveryError('O banco precisa de uma verificação antes da recuperação. Nenhum dado foi alterado.')
        admins = conn.execute("SELECT id,email FROM users WHERE role='admin'").fetchall()
        creating = account_id is None
        email = str(first_email or '').strip().lower()
        if creating:
            if conn.execute('SELECT count(*) FROM users').fetchone()[0] != 0:
                raise RecoveryError('Já existem contas neste banco. Selecione um administrador existente; nenhuma conta será promovida automaticamente.')
            if '@' not in email or len(email) > 254:
                raise RecoveryError('Informe seu e-mail para criar o primeiro administrador.')
        elif not any(r['id'] == account_id for r in admins):
            raise RecoveryError('Selecione uma conta de administrador existente.')
        folder = path.parent / 'backups'
        folder.mkdir(exist_ok=True)
        backup = folder / ('antes-recuperar-admin-' + dt.datetime.now().strftime('%Y%m%d-%H%M%S-%f') + '.sqlite3')
        with sqlite3.connect(backup) as target:
            conn.backup(target)
        try:
            backup.chmod(0o600)
        except OSError:
            pass
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac('sha256', password.encode(), bytes.fromhex(salt), 600000).hex()
        conn.execute('BEGIN IMMEDIATE')
        if creating:
            if conn.execute('SELECT count(*) FROM users').fetchone()[0] != 0:
                raise RecoveryError('O banco mudou durante a recuperação. Nenhuma conta foi criada.')
            account_id = str(uuid.uuid4())
            conn.execute('INSERT INTO users(id,email,role,salt,password) VALUES(?,?,?,?,?)', (account_id,email,'admin',salt,hashed))
        else:
            changed = conn.execute("UPDATE users SET salt=?,password=? WHERE id=? AND role='admin'", (salt,hashed,account_id)).rowcount
            if changed != 1:
                raise RecoveryError('A conta mudou durante a recuperação. Nenhuma senha foi alterada.')
            email = conn.execute('SELECT email FROM users WHERE id=?', (account_id,)).fetchone()[0]
        conn.execute('DELETE FROM sessions WHERE user_id=?', (account_id,))
        saved = conn.execute('SELECT password FROM users WHERE id=?', (account_id,)).fetchone()[0]
        if not hmac.compare_digest(saved, hashed):
            raise RecoveryError('Não foi possível confirmar a alteração. A operação foi cancelada.')
        conn.commit()
        return {'email':email, 'backup':str(backup), 'created':creating}
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()

def main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk
    root = tk.Tk()
    root.title('Gestão Umbanda — Recuperação local do administrador')
    root.geometry('720x620')
    root.minsize(660,570)
    root.configure(bg='#f8f4ef')
    style = ttk.Style(root)
    style.configure('TLabel',font=('Segoe UI',11))
    style.configure('TButton',font=('Segoe UI',11))
    frame = ttk.Frame(root,padding=24)
    frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='Recuperar administrador no notebook',font=('Segoe UI',18,'bold')).pack(anchor='w')
    ttk.Label(frame,text='Os cadastros serão mantidos. Uma cópia do banco será criada antes da alteração.',wraplength=650).pack(anchor='w',pady=(8,14))
    ttk.Label(frame,text='1. Feche a janela do servidor INICIAR.bat com Ctrl+C.\n2. Confira o banco e escolha a conta abaixo.\n3. Digite a nova senha somente nesta janela.',wraplength=650).pack(anchor='w',pady=(0,14))
    default = Path.home()/'Gestao-Umbanda-Notebook'/'dados'/'templo.sqlite3'
    local = Path(__file__).resolve().parent/'dados'/'templo.sqlite3'
    if not default.is_file() and local.is_file():
        default = local
    db_var = tk.StringVar(value=str(default))
    ttk.Label(frame,text='Banco de dados do notebook').pack(anchor='w')
    row = ttk.Frame(frame);row.pack(fill='x',pady=(4,12))
    ttk.Entry(row,textvariable=db_var).pack(side='left',fill='x',expand=True)
    account_rows = []
    count = 0
    account_var = tk.StringVar()
    selected = ttk.Combobox(frame,textvariable=account_var,state='readonly')
    new_email = tk.StringVar()
    email_entry = ttk.Entry(frame,textvariable=new_email)
    status = tk.StringVar(value='')
    def load():
        nonlocal account_rows,count
        try:
            account_rows,count = accounts(db_var.get())
            selected['values'] = [r['email'] for r in account_rows]
            if account_rows:
                selected.current(0);selected.pack(fill='x',before=pass_label,pady=(4,12));email_label.pack_forget();email_entry.pack_forget()
                status.set('Conta encontrada. Confira o e-mail selecionado antes de continuar.')
            elif count == 0:
                selected.pack_forget();email_label.pack(before=pass_label,anchor='w');email_entry.pack(fill='x',before=pass_label,pady=(4,12))
                status.set('Este banco ainda não tem contas. Você poderá criar o primeiro administrador sem o código da janela preta.')
            else:
                selected.set('');selected.pack(fill='x',before=pass_label,pady=(4,12));email_label.pack_forget();email_entry.pack_forget()
                status.set('Há contas, mas nenhum administrador. Nenhuma conta será promovida automaticamente. Solicite ajuda para conferir o banco.')
        except Exception as error:
            account_rows=[];selected.set('');status.set(str(error) if isinstance(error,RecoveryError) else 'Não foi possível ler este banco. Confira o arquivo e feche o servidor.')
    def choose():
        path = filedialog.askopenfilename(title='Escolher dados/templo.sqlite3',initialdir=str(default.parent),filetypes=[('Banco do Gestão Umbanda','templo.sqlite3'),('SQLite','*.sqlite3')])
        if path:
            db_var.set(path);load()
    ttk.Button(row,text='Localizar banco',command=choose).pack(side='right',padx=(8,0))
    ttk.Label(frame,text='Conta de administrador encontrada no banco').pack(anchor='w')
    selected.pack(fill='x',pady=(4,12))
    email_label = ttk.Label(frame,text='Seu e-mail (primeiro administrador)')
    pass_label = ttk.Label(frame,text='Nova senha — pelo menos 12 caracteres')
    pass_label.pack(anchor='w')
    first = ttk.Entry(frame,show='•');first.pack(fill='x',pady=(4,10))
    ttk.Label(frame,text='Digite a mesma senha novamente').pack(anchor='w')
    second = ttk.Entry(frame,show='•');second.pack(fill='x',pady=(4,14))
    def submit():
        if first.get()!=second.get():
            messagebox.showerror('Confira a senha','As duas senhas não coincidem.',parent=root);return
        if account_rows:
            index=selected.current()
            if not 0 <= index < len(account_rows):
                messagebox.showerror('Escolha a conta','Selecione o administrador que deseja recuperar.',parent=root);return
            account_id=account_rows[index]['id']
        else:
            account_id=None
        button.state(['disabled']);root.update_idletasks()
        try:
            result=recover(db_var.get(),account_id,first.get(),first_email=new_email.get())
            first.delete(0,'end');second.delete(0,'end')
            status.set('Acesso atualizado. A cópia de segurança está em dados/backups.\nAbra INICIAR.bat e entre em https://localhost:8787/ com a conta indicada.')
            messagebox.showinfo('Acesso atualizado','Conta: '+result['email']+'\n\nA senha foi definida. Os cadastros foram mantidos.\n\nAgora abra INICIAR.bat e entre no aplicativo com essa conta e a nova senha.',parent=root)
            load()
        except Exception as error:
            messagebox.showerror('Recuperação não concluída',str(error) if isinstance(error,RecoveryError) else 'Não foi possível concluir. Nenhum cadastro foi apagado. Feche o servidor e confira o arquivo do banco.',parent=root)
        finally:
            button.state(['!disabled'])
    button=ttk.Button(frame,text='Salvar nova senha do administrador',command=submit);button.pack(anchor='w',pady=(0,14))
    ttk.Label(frame,textvariable=status,wraplength=650).pack(anchor='w')
    ttk.Label(frame,text='Não envie sua senha por mensagem. Esta ferramenta atua somente neste notebook.',wraplength=650).pack(side='bottom',anchor='w',pady=(10,0))
    load();root.mainloop()

if __name__=='__main__':
    main()
