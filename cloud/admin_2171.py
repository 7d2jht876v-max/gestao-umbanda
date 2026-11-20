#!/usr/bin/env python3
"""Gestão Umbanda 217.1: provisionar/recuperar administrador na nuvem.
Executar apenas no terminal SSH do servidor. Não apaga cadastros ou financeiro.
"""
import argparse
import getpass
import hashlib
import secrets
import sqlite3
import uuid
from pathlib import Path
from datetime import datetime, timezone

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--database", default="/opt/gestao-umbanda/dados/templo.sqlite3")
    parser.add_argument("--email", required=True)
    args = parser.parse_args()
    email = args.email.strip().lower()
    if "@" not in email or len(email) > 254:
        raise SystemExit("E-mail inválido.")
    path = Path(args.database)
    if not path.is_file():
        raise SystemExit("Banco não encontrado. Nenhum arquivo foi criado.")
    pw = getpass.getpass("Nova senha de administrador (mínimo 12 caracteres): ")
    confirm = getpass.getpass("Confirme a senha: ")
    if len(pw) < 12 or pw != confirm:
        raise SystemExit("Senha inválida ou confirmação diferente. Nenhuma alteração.")
    with sqlite3.connect(path, timeout=20) as db:
        check = db.execute("PRAGMA integrity_check").fetchone()[0]
        if check != "ok":
            raise SystemExit("Integridade do banco falhou; nenhuma alteração.")
        existing = db.execute("SELECT id,role FROM users WHERE lower(email)=?", (email,)).fetchone()
        if existing and existing[1] != "admin":
            raise SystemExit("E-mail já pertence a um médium. Nenhuma alteração.")
        other_admins = db.execute("SELECT count(*) FROM users WHERE role='admin'").fetchone()[0]
        if not existing and other_admins:
            raise SystemExit("Já existe outro administrador. Nenhuma alteração; faça recuperação autorizada da conta existente.")
        folder = path.parent / "backups"
        folder.mkdir(parents=True, exist_ok=True)
        dest = folder / ("antes-admin-2171-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".sqlite3")
        with sqlite3.connect(dest) as backup:
            db.backup(backup)
        dest.chmod(0o600)
        print("Backup SQLite criado:", dest)
        salt = secrets.token_hex(16)
        hashed = hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 600000).hex()
        with db:
            if existing:
                db.execute("UPDATE users SET salt=?,password=? WHERE id=?", (salt,hashed,existing[0]))
                db.execute("DELETE FROM sessions WHERE user_id=?", (existing[0],))
            else:
                db.execute("INSERT INTO users(id,email,role,salt,password) VALUES(?,?,?,?,?)",
                           (str(uuid.uuid4()),email,"admin",salt,hashed))
        print("Administrador configurado. Outros dados preservados.")

if __name__ == "__main__":
    main()
