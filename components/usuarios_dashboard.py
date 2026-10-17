import sqlite3
from contextlib import contextmanager

import streamlit_authenticator as stauth


@contextmanager
def conexion_dashboard(db_path):
    conn = sqlite3.connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def inicializar_usuarios_dashboard(db_path):
    with conexion_dashboard(db_path) as conn:
        conn.execute(
            '''CREATE TABLE IF NOT EXISTS dashboard_users (
                   username TEXT PRIMARY KEY COLLATE NOCASE,
                   display_name TEXT NOT NULL,
                   password_hash TEXT NOT NULL,
                   role TEXT NOT NULL DEFAULT 'tecnico',
                   created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
               )'''
        )


def obtener_credenciales_dashboard(db_path, password_admin):
    with conexion_dashboard(db_path) as conn:
        rows = conn.execute(
            "SELECT username, display_name, password_hash FROM dashboard_users ORDER BY username COLLATE NOCASE"
        ).fetchall()

    usernames = {
        "admin": {
            "email": "admin@omnidesk.local",
            "name": "Admin_01",
            "password": password_admin,
            "roles": ["admin"],
        }
    }
    for username, display_name, password_hash in rows:
        usernames[username] = {
            "email": f"{username}@omnidesk.local",
            "name": display_name,
            "password": password_hash,
            "roles": ["tecnico"],
        }
    return {"usernames": usernames}


def crear_usuario_tecnico(db_path, username, display_name, password):
    username = username.strip().lower()
    display_name = display_name.strip()
    if not username or not display_name or not password:
        raise ValueError("Completa el usuario, el nombre y la contraseña.")
    if username == "admin":
        raise ValueError("Ese nombre de usuario está reservado.")
    if len(username) > 32 or not all(c.isalnum() or c in "._-" for c in username):
        raise ValueError("El usuario solo puede tener letras, números, puntos, guiones o guiones bajos.")
    if len(password) < 8:
        raise ValueError("La contraseña debe tener al menos 8 caracteres.")

    password_hash = stauth.Hasher.hash(password)
    try:
        with conexion_dashboard(db_path) as conn:
            conn.execute(
                "INSERT INTO dashboard_users (username, display_name, password_hash, role) VALUES (?, ?, ?, 'tecnico')",
                (username, display_name, password_hash),
            )
    except sqlite3.IntegrityError as exc:
        raise ValueError("Ya existe una cuenta con ese usuario.") from exc


def obtener_usuarios_dashboard(db_path):
    with conexion_dashboard(db_path) as conn:
        return conn.execute(
            "SELECT username AS Usuario, display_name AS Nombre, role AS Rol, created_at AS 'Creado el' "
            "FROM dashboard_users ORDER BY username COLLATE NOCASE"
        ).fetchall()
