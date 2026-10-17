import streamlit as st
import sqlite3
import pandas as pd
import os
import secrets
from pathlib import Path
import streamlit_authenticator as stauth
from dotenv import load_dotenv
from components.metricas import render_iot_dashboard
from components.chat_tecnico import cerrar_ticket, inicializar_asignaciones, render_chat_tecnico
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
        abiertos = len(df[df['Estado'].isin(['Esperando decisión', 'Esperando detalles', 'Abierto', 'Esperando técnico', 'En atención'])])
        resueltos = len(df[df['Estado'] == 'Resuelto'])
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total de Incidentes", total_tickets)
        kpi2.metric("Casos Pendientes", abiertos)
        kpi3.metric("Casos Resueltos", resueltos)
        st.markdown("---")

        col1, col2 = st.columns([5, 2])
        
        with col1:
            st.subheader("📥 Bandeja de Entrada (Activos)")
            df_activos = df[df['Estado'].isin(['Esperando decisión', 'Esperando detalles', 'Abierto', 'Esperando técnico', 'En atención'])].drop(columns=['user_id', 'assigned_username'])
            if not df_activos.empty:
                st.dataframe(df_activos, use_container_width=True, hide_index=True)
            else:
                st.success("🎉 No hay tickets pendientes. Bandeja limpia.")
                
            # --- TRAZABILIDAD Y AUDITORÍA ---
            st.subheader("🗄️ Historial de Resoluciones")
            df_resueltos = df[df['Estado'] == 'Resuelto'].drop(columns=['user_id', 'assigned_username'])
            if not df_resueltos.empty:
                # Mostramos los resueltos en gris para diferenciarlos visualmente
                st.dataframe(df_resueltos, use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay tickets resueltos en el historial.")
                
        with col2:
            st.subheader("Acciones Técnicas")
            if not df_activos.empty:
                ticket_seleccionado = st.selectbox("Seleccione ID del Ticket", df_activos['id'].tolist())
                fila_seleccionada = df.loc[df['id'] == ticket_seleccionado].iloc[0]
                asignado_username = fila_seleccionada['assigned_username']
                puede_resolver = pd.isna(asignado_username) or asignado_username == usuario_actual
                if not puede_resolver:
                    st.caption(f"Técnico asignado: {fila_seleccionada['Técnico asignado']}. Toma el ticket desde el chat para atenderlo.")
                if st.button("✅ Marcar como Resuelto", use_container_width=True, disabled=not puede_resolver):
                    user_id = df.loc[df['id'] == ticket_seleccionado, 'user_id'].values[0]
                    try:
                        cerrar_ticket(DB_PATH, ticket_seleccionado, user_id, usuario_actual)
                        st.success(f"Ticket #{ticket_seleccionado} cerrado y usuario notificado.")
                        st.rerun()
                    except Exception as e:
                        st.error(f"No se pudo cerrar el ticket: {e}")
                    
            if st.button("🔄 Refrescar Panel", use_container_width=True):
                st.rerun()
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
