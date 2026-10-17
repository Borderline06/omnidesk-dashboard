import streamlit as st
import sqlite3
import pandas as pd
import os
import secrets
from pathlib import Path
import streamlit_authenticator as stauth
from dotenv import load_dotenv
from components.metricas import render_iot_dashboard
from components.chat_tecnico import (
    cerrar_ticket,
    inicializar_asignaciones,
    mostrar_mensajes,
    render_chat_tecnico,
    responder_ticket,
    tomar_ticket,
)
from components.usuarios_dashboard import (
    crear_usuario_tecnico,
    inicializar_usuarios_dashboard,
    obtener_credenciales_dashboard,
    obtener_usuarios_dashboard,
)

st.set_page_config(page_title="OmniDesk AI", layout="wide")
APP_DIR = Path(__file__).resolve().parent
load_dotenv(APP_DIR / ".env")
DB_PATH = str(APP_DIR.parent / "omnidesk-backend" / "omnidesk.db")
inicializar_usuarios_dashboard(DB_PATH)
inicializar_asignaciones(DB_PATH)

# --- 1. SISTEMA DE AUTENTICACIÓN
def obtener_clave_cookie():
    clave = os.getenv("OMNIDESK_COOKIE_SECRET")
    if clave:
        return clave

    archivo_clave = APP_DIR / ".streamlit" / ".auth_cookie_secret"
    archivo_clave.parent.mkdir(parents=True, exist_ok=True)
    if not archivo_clave.exists():
        archivo_clave.write_text(secrets.token_urlsafe(48), encoding="utf-8")
    return archivo_clave.read_text(encoding="utf-8").strip()


autenticador = stauth.Authenticate(
    credentials=obtener_credenciales_dashboard(
        DB_PATH,
        os.getenv("OMNIDESK_ADMIN_PASSWORD", "admin123"),
    ),
    cookie_name="omnidesk_dashboard_session",
    cookie_key=obtener_clave_cookie(),
    cookie_expiry_days=7,
)

if not st.session_state.get("authentication_status"):
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.title("🔒 Acceso Restringido")
        st.markdown("Portal exclusivo para personal técnico autorizado.")
        autenticador.login(
            location="main",
            fields={
                "Form name": "Iniciar Sesión",
                "Username": "Usuario",
                "Password": "Contraseña",
                "Login": "Iniciar Sesión",
            },
            key="omnidesk_login",
        )

if not st.session_state.get("authentication_status"):
    st.stop() # Bloquea la renderización del resto de la app si no hay login

# --- 2. BASE DE DATOS ---
def get_connection():
    return sqlite3.connect(DB_PATH)

def cargar_tickets():
    conn = get_connection()
    query = "SELECT t.id, t.user_id, t.username as Usuario, t.descripcion as Problema, t.categoria as Categoría, t.urgencia as Urgencia, t.estado as Estado, t.fecha as Fecha, a.technician_username as assigned_username, COALESCE(a.technician_name, 'Sin asignar') as 'Técnico asignado' FROM tickets t LEFT JOIN ticket_assignments a ON a.ticket_id = t.id ORDER BY t.id DESC"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

ESTADOS_ACTIVOS = ['Esperando decisión', 'Esperando detalles', 'Abierto', 'Esperando técnico', 'En atención']
ESTADOS_CHAT = ['Esperando técnico', 'En atención']  # estados en los que el técnico puede tomar/responder

def _id_seleccionado(evento, df_vista):
    filas = evento.selection.rows
    return int(df_vista.iloc[filas[0]]['id']) if filas else None

# --- 3. INTERFAZ PRINCIPAL ---
usuario_actual = st.session_state.get("username", "")
es_admin = usuario_actual.lower() == "admin"
nombre_actual = st.session_state.get("name") or usuario_actual

st.sidebar.title("⚙️ OmniDesk Control")
st.sidebar.markdown(f"**{ 'Administrador' if es_admin else 'Técnico' }:** {nombre_actual}")
modulos = ["Gestión de Tickets", "Chat con usuarios", "Monitoreo IoT"]
if es_admin:
    modulos.append("Administrar técnicos")
menu = st.sidebar.radio("Módulos", modulos)

autenticador.logout("Cerrar Sesión", location="sidebar", key="omnidesk_logout")

if menu == "Gestión de Tickets":
    st.title("🖥️ Centro de Soporte Nivel 1")

    try:
        df = cargar_tickets()

        # --- MÉTRICAS GERENCIALES (KPIs) ---
        total_tickets = len(df)
        abiertos = len(df[df['Estado'].isin(ESTADOS_ACTIVOS)])
        resueltos = len(df[df['Estado'] == 'Resuelto'])

        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total de Incidentes", total_tickets)
        kpi2.metric("Casos Pendientes", abiertos)
        kpi3.metric("Casos Resueltos", resueltos)
        st.markdown("---")

        # --- FILTROS ---
        f1, f2, f3, f4, f5 = st.columns([3, 2, 2, 2, 1], vertical_alignment="bottom")
        busqueda = f1.text_input("Buscar", placeholder="Usuario, problema o #ID", key="filtro_busqueda")
        filtro_estado = f2.multiselect("Estado", sorted(df['Estado'].dropna().unique()), key="filtro_estado")
        filtro_urgencia = f3.multiselect("Urgencia", sorted(df['Urgencia'].dropna().unique()), key="filtro_urgencia")
        filtro_tecnico = f4.selectbox(
            "Técnico", ["Todos", "Sin asignar"] + sorted(df['Técnico asignado'].loc[df['assigned_username'].notna()].unique()),
            key="filtro_tecnico",
        )
        if f5.button("🔄", help="Refrescar panel", use_container_width=True):
            st.rerun()

        df_filtrado = df
        if busqueda.strip():
            patron = busqueda.strip().lstrip("#")
            df_filtrado = df_filtrado[
                df_filtrado['Usuario'].fillna('').str.contains(patron, case=False, regex=False)
                | df_filtrado['Problema'].fillna('').str.contains(patron, case=False, regex=False)
                | (df_filtrado['id'].astype(str) == patron)
            ]
        if filtro_estado:
            df_filtrado = df_filtrado[df_filtrado['Estado'].isin(filtro_estado)]
        if filtro_urgencia:
            df_filtrado = df_filtrado[df_filtrado['Urgencia'].isin(filtro_urgencia)]
        if filtro_tecnico == "Sin asignar":
            df_filtrado = df_filtrado[df_filtrado['assigned_username'].isna()]
        elif filtro_tecnico != "Todos":
            df_filtrado = df_filtrado[df_filtrado['Técnico asignado'] == filtro_tecnico]

        columnas_vista = ['id', 'Usuario', 'Problema', 'Categoría', 'Urgencia', 'Estado', 'Fecha', 'Técnico asignado']
        df_activos = df_filtrado[df_filtrado['Estado'].isin(ESTADOS_ACTIVOS)][columnas_vista].reset_index(drop=True)
        df_resueltos = df_filtrado[df_filtrado['Estado'] == 'Resuelto'][columnas_vista].reset_index(drop=True)

        # --- TABLAS CON SELECCIÓN DE FILA ---
        tab_activos, tab_historial = st.tabs([
            f"📥 Bandeja de Entrada ({len(df_activos)})",
            f"🗄️ Historial de Resoluciones ({len(df_resueltos)})",
        ])
        with tab_activos:
            if df_activos.empty:
                st.success("🎉 No hay tickets pendientes. Bandeja limpia.")
                sel_activos = None
            else:
                evento_activos = st.dataframe(
                    df_activos, use_container_width=True, hide_index=True, height=320,
                    on_select="rerun", selection_mode="single-row", key="tabla_activos",
                )
                sel_activos = _id_seleccionado(evento_activos, df_activos)
        with tab_historial:
            if df_resueltos.empty:
                st.info("No hay tickets resueltos que coincidan con los filtros.")
                sel_historial = None
            else:
                evento_historial = st.dataframe(
                    df_resueltos, use_container_width=True, hide_index=True, height=320,
                    on_select="rerun", selection_mode="single-row", key="tabla_historial",
                )
                sel_historial = _id_seleccionado(evento_historial, df_resueltos)

        # Si cambió la selección en alguna tabla, esa pasa a ser la del detalle
        previas = st.session_state.get("_sel_tablas", (None, None))
        ticket_detalle = st.session_state.get("ticket_detalle")
        if sel_activos is not None and sel_activos != previas[0]:
            ticket_detalle = sel_activos
        if sel_historial is not None and sel_historial != previas[1]:
            ticket_detalle = sel_historial
        if ticket_detalle not in (sel_activos, sel_historial):
            ticket_detalle = sel_activos if sel_activos is not None else sel_historial
        st.session_state["_sel_tablas"] = (sel_activos, sel_historial)
        st.session_state["ticket_detalle"] = ticket_detalle

        st.markdown("---")
        if ticket_detalle is None:
            st.info("Selecciona un ticket en la bandeja o en el historial para ver la conversación y gestionar la respuesta.")
        else:
            fila = df.loc[df['id'] == ticket_detalle].iloc[0]
            estado = fila['Estado']
            activo = estado in ESTADOS_ACTIVOS
            atendible = estado in ESTADOS_CHAT
            asignado_username = None if pd.isna(fila['assigned_username']) else fila['assigned_username']
            es_asignado_actual = bool(asignado_username) and asignado_username.lower() == usuario_actual.lower()
            puede_resolver = activo and (not asignado_username or es_asignado_actual)

            st.subheader(f"🎫 Ticket #{ticket_detalle} · {fila['Usuario']}")
            st.caption(
                f"Estado: {estado} · Urgencia: {fila['Urgencia']} · Categoría: {fila['Categoría']} · "
                f"Técnico: {fila['Técnico asignado']} · {fila['Fecha']}"
            )
            with st.container(border=True):
                st.markdown("**📝 Problema reportado**")
                st.write(fila['Problema'])

            col_hilo, col_acciones = st.columns([5, 2])
            with col_hilo:
                mostrar_mensajes(DB_PATH, int(ticket_detalle), str(fila['Usuario']))
            with col_acciones:
                st.subheader("Acciones Técnicas")
                if not activo:
                    st.info("Caso resuelto. Conversación disponible solo para consulta.")
                elif atendible and not asignado_username:
                    st.info("Ticket sin asignar. Tómalo para poder responder al usuario.")
                    if st.button("🙋 Tomar ticket", key=f"tomar_{ticket_detalle}", use_container_width=True):
                        tomado, mensaje = tomar_ticket(DB_PATH, int(ticket_detalle), usuario_actual, nombre_actual)
                        (st.success if tomado else st.warning)(mensaje)
                        if tomado:
                            st.rerun()
                elif asignado_username and not es_asignado_actual:
                    st.caption(f"Lo atiende {fila['Técnico asignado']}. Solo esa persona puede responder o resolver.")
                elif not atendible:
                    st.caption("El usuario aún no ha sido transferido a un técnico; puedes cerrarlo si ya está resuelto.")

                if activo and atendible and es_asignado_actual:
                    with st.form(f"responder_{ticket_detalle}", clear_on_submit=True):
                        respuesta = st.text_area("Respuesta al usuario (se envía por Telegram)", height=140)
                        enviar = st.form_submit_button("📨 Enviar respuesta", use_container_width=True)
                    if enviar:
                        if not respuesta.strip():
                            st.warning("Escribe una respuesta antes de enviar.")
                        else:
                            try:
                                responder_ticket(DB_PATH, int(ticket_detalle), fila['user_id'], usuario_actual, respuesta.strip())
                                st.rerun()
                            except Exception as e:
                                st.error(f"No se pudo enviar la respuesta: {e}")

                if activo:
                    if st.button("✅ Marcar como Resuelto", key=f"resolver_{ticket_detalle}",
                                 use_container_width=True, disabled=not puede_resolver):
                        try:
                            cerrar_ticket(DB_PATH, int(ticket_detalle), fila['user_id'], usuario_actual)
                            st.success(f"Ticket #{ticket_detalle} cerrado y usuario notificado.")
                            st.rerun()
                        except Exception as e:
                            st.error(f"No se pudo cerrar el ticket: {e}")
    except Exception as e:
        st.error(f"Error de conexión con SQLite: {e}")

elif menu == "Chat con usuarios":
    render_chat_tecnico(DB_PATH, usuario_actual, nombre_actual)

elif menu == "Monitoreo IoT":
    render_iot_dashboard(DB_PATH)

elif menu == "Administrar técnicos" and es_admin:
    st.title("👥 Administrar técnicos")
    st.subheader("Crear cuenta de técnico")
    with st.form("crear_usuario_tecnico", clear_on_submit=True):
        nuevo_usuario = st.text_input("Usuario", help="Usa letras, números, puntos, guiones o guiones bajos.")
        nombre_tecnico = st.text_input("Nombre del técnico")
        contrasena_tecnico = st.text_input("Contraseña inicial", type="password", help="Mínimo 8 caracteres.")
        confirmar_creacion = st.form_submit_button("Crear técnico", use_container_width=True)

    if confirmar_creacion:
        try:
            crear_usuario_tecnico(DB_PATH, nuevo_usuario, nombre_tecnico, contrasena_tecnico)
            st.success(f"La cuenta de {nombre_tecnico.strip()} fue creada. Ya puede iniciar sesión con su usuario y contraseña.")
        except ValueError as error:
            st.error(str(error))

    st.subheader("Cuentas de técnicos")
    usuarios = obtener_usuarios_dashboard(DB_PATH)
    if usuarios:
        st.dataframe(
            pd.DataFrame(usuarios, columns=["Usuario", "Nombre", "Rol", "Creado el"]),
            use_container_width=True,
            hide_index=True,
        )
    else:
        st.info("Todavía no hay cuentas de técnicos.")
