import json
import os
import sqlite3
import urllib.error
import urllib.request
from contextlib import closing
from pathlib import Path

import pandas as pd
import streamlit as st


def _token_telegram():
    token = os.getenv('TELEGRAM_TOKEN')
    if token:
        return token

    env_path = Path(__file__).resolve().parents[2] / 'omnidesk-backend' / '.env'
    if not env_path.exists():
        return None

    for linea in env_path.read_text(encoding='utf-8').splitlines():
        linea = linea.strip()
        if linea.startswith('TELEGRAM_TOKEN='):
            return linea.split('=', 1)[1].strip().strip('"').strip("'")
    return None


def _enviar_telegram(user_id, texto):
    token = _token_telegram()
    if not token:
        raise RuntimeError('No se encontró TELEGRAM_TOKEN en el entorno ni en omnidesk-backend/.env.')

    url = f'https://api.telegram.org/bot{token}/sendMessage'
    payload = json.dumps({'chat_id': str(user_id), 'text': texto}).encode('utf-8')
    request = urllib.request.Request(url, data=payload, headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            resultado = json.loads(response.read().decode('utf-8'))
    except urllib.error.HTTPError as error:
        detalle = error.read().decode('utf-8', errors='replace')
        raise RuntimeError(f'Telegram rechazó el mensaje: {detalle}') from error
    except urllib.error.URLError as error:
        raise RuntimeError(f'No se pudo conectar con Telegram: {error.reason}') from error

    if not resultado.get('ok'):
        raise RuntimeError(resultado.get('description', 'Telegram no pudo enviar el mensaje.'))


def inicializar_asignaciones(db_path):
    with closing(sqlite3.connect(db_path)) as conn:
        conn.execute('''
            CREATE TABLE IF NOT EXISTS ticket_assignments (
                ticket_id INTEGER PRIMARY KEY,
                technician_username TEXT NOT NULL,
                technician_name TEXT NOT NULL,
                assigned_at TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
                FOREIGN KEY (ticket_id) REFERENCES tickets(id)
            )
        ''')
        conn.commit()


def _registrar_evento(conn, ticket_id, contenido):
    conn.execute(
        'INSERT INTO ticket_messages (ticket_id, sender, contenido, fecha) VALUES (?, ?, ?, datetime(\'now\', \'localtime\'))',
        (int(ticket_id), 'sistema', contenido),
    )


def tomar_ticket(db_path, ticket_id, tecnico_username, tecnico_nombre):
    """Asigna atómicamente un ticket activo al primer técnico que lo tome."""
    conn = sqlite3.connect(db_path, timeout=15)
    try:
        conn.execute('BEGIN IMMEDIATE')
        ticket = conn.execute('SELECT estado FROM tickets WHERE id = ?', (int(ticket_id),)).fetchone()
        if not ticket or ticket[0] not in ('Esperando técnico', 'En atención'):
            conn.rollback()
            return False, 'El ticket ya no está activo.'

        asignacion = conn.execute(
            'SELECT technician_username, technician_name FROM ticket_assignments WHERE ticket_id = ?',
            (int(ticket_id),),
        ).fetchone()
        if asignacion:
            conn.rollback()
            if asignacion[0].lower() == tecnico_username.lower():
                return True, 'Este ticket ya está asignado a tu cuenta.'
            return False, f'Este ticket ya lo está atendiendo {asignacion[1]}.'

        conn.execute(
            'INSERT INTO ticket_assignments (ticket_id, technician_username, technician_name) VALUES (?, ?, ?)',
            (int(ticket_id), tecnico_username, tecnico_nombre),
        )
        conn.execute("UPDATE tickets SET estado = 'En atención' WHERE id = ?", (int(ticket_id),))
        _registrar_evento(conn, ticket_id, f'{tecnico_nombre} tomó el ticket y continuará la atención por este chat.')
        conn.commit()
        return True, 'Ticket asignado.'
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _listar_tecnicos(db_path, excluir_username):
    with closing(sqlite3.connect(db_path)) as conn:
        tecnicos = conn.execute(
            "SELECT username, display_name FROM dashboard_users WHERE role = 'tecnico' ORDER BY display_name COLLATE NOCASE"
        ).fetchall()
    tecnicos.insert(0, ('admin', 'Admin_01'))
    return [tecnico for tecnico in tecnicos if tecnico[0].lower() != excluir_username.lower()]


def transferir_ticket(db_path, ticket_id, user_id, tecnico_actual, nombre_actual,
                      tecnico_destino, motivo=''):
    conn = sqlite3.connect(db_path, timeout=15)
    try:
        conn.execute('BEGIN IMMEDIATE')
        asignacion = conn.execute(
            'SELECT technician_username, technician_name FROM ticket_assignments WHERE ticket_id = ?',
            (int(ticket_id),),
        ).fetchone()
        if not asignacion or asignacion[0].lower() != tecnico_actual.lower():
            conn.rollback()
            return False, 'El ticket ya no está asignado a tu cuenta. Actualiza la página.'
        _verificar_ticket_activo(conn, ticket_id)

        if tecnico_destino == 'admin':
            nombre_destino = 'Admin_01'
        else:
            destino = conn.execute(
                "SELECT display_name FROM dashboard_users WHERE username = ? COLLATE NOCASE AND role = 'tecnico'",
                (tecnico_destino,),
            ).fetchone()
            if not destino:
                conn.rollback()
                return False, 'No se encontró la cuenta del técnico seleccionado.'
            nombre_destino = destino[0]

        aviso = (
            f'🧑‍💻 El técnico {nombre_actual} pasó tu ticket #{ticket_id} a {nombre_destino}, '
            'quien continuará atendiéndote por este chat.'
        )
        _enviar_telegram(user_id, aviso)
        conn.execute(
            'UPDATE ticket_assignments SET technician_username = ?, technician_name = ?, '
            "assigned_at = datetime('now', 'localtime') WHERE ticket_id = ?",
            (tecnico_destino, nombre_destino, int(ticket_id)),
        )
        detalle = f'{nombre_actual} transfirió el ticket a {nombre_destino}.'
        if motivo.strip():
            detalle += f' Motivo: {motivo.strip()}'
        _registrar_evento(conn, ticket_id, detalle)
        conn.commit()
        return True, f'Ticket transferido a {nombre_destino}.'
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def responder_ticket(db_path, ticket_id, user_id, tecnico_username, texto):
    """Envía la respuesta del técnico asignado al usuario por Telegram y la guarda en el hilo."""
    conn = sqlite3.connect(db_path, timeout=15)
    try:
        conn.execute('BEGIN IMMEDIATE')
        _verificar_ticket_activo(conn, ticket_id)
        _verificar_tecnico_asignado(conn, ticket_id, tecnico_username)
        _enviar_telegram(user_id, texto)
        conn.execute(
            'INSERT INTO ticket_messages (ticket_id, sender, contenido, fecha) VALUES (?, ?, ?, datetime(\'now\', \'localtime\'))',
            (int(ticket_id), f'tecnico:{tecnico_username}', texto),
        )
        conn.execute("UPDATE tickets SET estado = 'En atención' WHERE id = ?", (int(ticket_id),))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _verificar_tecnico_asignado(conn, ticket_id, tecnico_username):
    asignacion = conn.execute(
        'SELECT technician_username FROM ticket_assignments WHERE ticket_id = ?',
        (int(ticket_id),),
    ).fetchone()
    if not asignacion or asignacion[0].lower() != tecnico_username.lower():
        raise RuntimeError('Este ticket está sin asignar o lo está atendiendo otro técnico.')


def _verificar_ticket_activo(conn, ticket_id, estados=('Esperando técnico', 'En atención')):
    ticket = conn.execute('SELECT estado FROM tickets WHERE id = ?', (int(ticket_id),)).fetchone()
    if not ticket or ticket[0] not in estados:
        raise RuntimeError('Este ticket ya está cerrado o no está disponible para atención.')


def cerrar_ticket(db_path, ticket_id, user_id, tecnico_username=None):
    aviso = (
        f'✅ El técnico ha cerrado el ticket #{ticket_id}. '
        'Para iniciar una nueva consulta, envía /start y luego describe tu problema.'
    )
    conn = sqlite3.connect(db_path, timeout=15)
    try:
        conn.execute('BEGIN IMMEDIATE')
        _verificar_ticket_activo(
            conn, ticket_id,
            estados=('Esperando decisión', 'Esperando detalles', 'Abierto', 'Esperando técnico', 'En atención'),
        )
        if tecnico_username:
            asignacion = conn.execute(
                'SELECT technician_username FROM ticket_assignments WHERE ticket_id = ?',
                (int(ticket_id),),
            ).fetchone()
            if asignacion:
                _verificar_tecnico_asignado(conn, ticket_id, tecnico_username)
        _enviar_telegram(user_id, aviso)
        _registrar_evento(conn, ticket_id, aviso)
        conn.execute("UPDATE tickets SET estado = 'Resuelto' WHERE id = ?", (int(ticket_id),))
        conn.execute('''
            CREATE TABLE IF NOT EXISTS bot_user_state (
                user_id TEXT PRIMARY KEY,
                requires_start INTEGER NOT NULL DEFAULT 0
            )
        ''')
        conn.execute(
            'INSERT INTO bot_user_state (user_id, requires_start) VALUES (?, 1) '
            'ON CONFLICT(user_id) DO UPDATE SET requires_start = 1',
            (str(user_id),),
        )
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _listar_tickets(db_path):
    inicializar_asignaciones(db_path)
    with closing(sqlite3.connect(db_path)) as conn:
        return pd.read_sql_query(
            "SELECT t.id, t.user_id, t.username, t.descripcion, t.estado, t.fecha, "
            "a.technician_username AS asignado_username, a.technician_name AS asignado_nombre "
            "FROM tickets t LEFT JOIN ticket_assignments a ON a.ticket_id = t.id "
            "WHERE t.estado IN ('Esperando técnico', 'En atención', 'Resuelto') "
            "AND EXISTS (SELECT 1 FROM ticket_messages m WHERE m.ticket_id = t.id) "
            "ORDER BY CASE WHEN t.estado IN ('Esperando técnico', 'En atención') THEN 0 ELSE 1 END, t.id DESC",
            conn,
        )


def render_chat_tecnico(db_path, tecnico_username='admin', tecnico_nombre='Admin_01'):
    try:
        tickets = _listar_tickets(db_path)
    except Exception as error:
        st.subheader('💬 Chat con usuarios de Telegram')
        st.error(f'No se pudieron cargar las conversaciones: {error}')
        return

    if tickets.empty:
        st.subheader('💬 Chat con usuarios de Telegram')
        st.info('Todavía no hay conversaciones transferidas a un técnico.')
        return

    opciones = tickets['id'].tolist()
    id_guardado = st.session_state.get('chat_ticket_seleccionado')
    if id_guardado not in opciones:
        id_guardado = opciones[0]
    indice_inicial = opciones.index(id_guardado)

    col_titulo, col_selector, col_actualizar, col_cierre = st.columns([3.0, 3.3, 1.0, 1.5], vertical_alignment='center')
    with col_titulo:
        st.subheader('💬 Chat con usuarios de Telegram')
    with col_selector:
        ticket_id = st.selectbox(
            'Conversación', opciones, index=indice_inicial,
            format_func=lambda ident: _etiqueta_ticket(tickets, ident),
            key='chat_ticket_seleccionado',
        )
    with col_actualizar:
        if st.button('🔄', key='actualizar_lista_tickets', help='Actualizar asignaciones y tickets', use_container_width=True):
            st.rerun()

    ticket = tickets.loc[tickets['id'] == ticket_id].iloc[0]
    activo = ticket['estado'] in ('Esperando técnico', 'En atención')
    asignado_username = ticket['asignado_username']
    asignado_nombre = ticket['asignado_nombre']
    if pd.isna(asignado_username):
        asignado_username = None
    if pd.isna(asignado_nombre):
        asignado_nombre = None
    es_asignado_actual = bool(asignado_username) and asignado_username.lower() == tecnico_username.lower()
    with col_cierre:
        if st.button(
            '✅ Resolver', key=f'cerrar_ticket_{ticket_id}',
            disabled=not (activo and es_asignado_actual), use_container_width=True,
        ):
            try:
                cerrar_ticket(db_path, ticket_id, ticket['user_id'], tecnico_username)
                st.rerun()
            except Exception as error:
                st.error(f'No se pudo cerrar el caso: {error}')

    st.caption(f"{ticket['username']} · Ticket #{ticket_id} · Estado: {ticket['estado']}")
    with st.container(border=True):
        st.markdown('**📝 Problema reportado por el usuario**')
        partes_descripcion = str(ticket['descripcion'] or '').splitlines()
        problema_inicial = []
        detalles_usuario = []
        for parte in partes_descripcion:
            if parte.startswith('Detalle del usuario:'):
                detalles_usuario.append(parte.partition(':')[2].strip())
            else:
                problema_inicial.append(parte)
        st.write('\n'.join(problema_inicial).strip())
        if detalles_usuario:
            st.markdown('**Detalles adicionales:**')
            for detalle in detalles_usuario:
                st.write(f'• {detalle}')

    if activo and not asignado_username:
        st.info('Este ticket está sin asignar. Tómalo para iniciar la atención; los demás técnicos verán quién lo atiende.')
        if st.button('🙋 Tomar ticket', key=f'tomar_ticket_{ticket_id}'):
            try:
                tomado, mensaje = tomar_ticket(db_path, ticket_id, tecnico_username, tecnico_nombre)
                (st.success if tomado else st.warning)(mensaje)
                if tomado:
                    st.rerun()
            except Exception as error:
                st.error(f'No se pudo tomar el ticket: {error}')
    elif activo and not es_asignado_actual:
        st.info(f'Este caso lo está atendiendo {asignado_nombre}. Puedes consultar los mensajes; solo esa persona puede responder o transferirlo.')
    elif activo:
        st.success(f'Lo estás atendiendo tú · {tecnico_nombre}')
        tecnicos_disponibles = _listar_tecnicos(db_path, tecnico_username)
        if tecnicos_disponibles:
            with st.expander('Transferir a otro técnico'):
                with st.form(f'transferir_ticket_{ticket_id}'):
                    tecnico_destino = st.selectbox(
                        'Técnico que continuará el caso',
                        tecnicos_disponibles,
                        format_func=lambda tecnico: f'{tecnico[1]} (@{tecnico[0]})',
                    )
                    motivo = st.text_area('Nota para el equipo (opcional)')
                    confirmar_transferencia = st.form_submit_button('Transferir ticket')
                if confirmar_transferencia:
                    try:
                        transferido, mensaje = transferir_ticket(
                            db_path, ticket_id, ticket['user_id'], tecnico_username,
                            tecnico_nombre, tecnico_destino[0], motivo,
                        )
                        (st.success if transferido else st.warning)(mensaje)
                        if transferido:
                            st.rerun()
                    except Exception as error:
                        st.error(f'No se pudo transferir el ticket: {error}')
        else:
            st.caption('No hay otro técnico disponible para recibir la transferencia.')

    mostrar_mensajes(db_path, int(ticket_id), str(ticket['username']))

    if activo and es_asignado_actual:
        texto = st.chat_input('Escribe tu respuesta al usuario…', key=f'respuesta_ticket_{ticket_id}')
        if texto:
            try:
                responder_ticket(db_path, ticket_id, ticket['user_id'], tecnico_username, texto)
                st.rerun()
            except Exception as error:
                st.error(f'No se pudo enviar la respuesta: {error}')
    elif not activo:
        st.info('Caso resuelto. Conversación disponible para consulta del equipo técnico.')


def _etiqueta_ticket(tickets, ticket_id):
    ticket = tickets.loc[tickets['id'] == ticket_id].iloc[0]
    asignado = ticket['asignado_nombre']
    if pd.isna(asignado) or not asignado:
        asignado = 'Sin asignar'
    return f"Ticket #{ticket_id} · {ticket['username']} · {ticket['estado']} · {asignado}"


@st.fragment(run_every=3)
def mostrar_mensajes(db_path, ticket_id, nombre_usuario):
    try:
        with closing(sqlite3.connect(db_path)) as conn:
            mensajes = pd.read_sql_query(
                'SELECT sender, contenido, fecha FROM ticket_messages WHERE ticket_id = ? ORDER BY id',
                conn, params=(ticket_id,),
            )
            tecnicos = dict(conn.execute(
                "SELECT username, display_name FROM dashboard_users"
            ).fetchall())
    except Exception as error:
        st.error(f'No se pudieron cargar los mensajes: {error}')
        return

    with st.container(height=480, border=True):
        for _, mensaje in mensajes.iterrows():
            sender = mensaje['sender']
            rol = 'user' if sender == 'usuario' else 'assistant'
            etiquetas = {
                'usuario': nombre_usuario,
                'tecnico': 'Técnico',
                'bot': 'OmniDesk AI',
                'sistema': 'OmniDesk',
            }
            if sender.startswith('tecnico:'):
                usuario_tecnico = sender.split(':', 1)[1]
                etiqueta = 'Admin_01' if usuario_tecnico == 'admin' else tecnicos.get(usuario_tecnico, usuario_tecnico)
            else:
                etiqueta = etiquetas.get(sender, str(sender).capitalize())
            with st.chat_message(rol):
                st.markdown(f"**{etiqueta}** · {mensaje['fecha']}")
                st.write(mensaje['contenido'])
