import streamlit as st
import sqlite3
import pandas as pd
from components.metricas import render_iot_dashboard

st.set_page_config(page_title="OmniDesk AI", layout="wide")
DB_PATH = "../omnidesk-backend/omnidesk.db"

# --- 1. SISTEMA DE AUTENTICACIÓN
def check_password():
    if "autenticado" not in st.session_state:
        st.session_state["autenticado"] = False

    if not st.session_state["autenticado"]:
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.title("🔒 Acceso Restringido")
            st.markdown("Portal exclusivo para personal técnico autorizado.")
            pwd = st.text_input("Contraseña de Administrador", type="password")
            if st.button("Iniciar Sesión", use_container_width=True):
                # Contraseña temporal
                if pwd == "admin123": 
                    st.session_state["autenticado"] = True
                    st.rerun()
                else:
                    st.error("Credenciales incorrectas. Intento registrado en auditoría.")
        return False
    return True

if not check_password():
    st.stop() # Bloquea la renderización del resto de la app si no hay login

# --- 2. BASE DE DATOS ---
def get_connection():
    return sqlite3.connect(DB_PATH)

def cargar_tickets():
    conn = get_connection()
    query = "SELECT id, user_id, username as Usuario, descripcion as Problema, categoria as Categoría, urgencia as Urgencia, estado as Estado, fecha as Fecha FROM tickets ORDER BY id DESC"
    df = pd.read_sql(query, conn)
    conn.close()
    return df

def actualizar_estado(ticket_id, user_id, nuevo_estado):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE tickets SET estado = ? WHERE id = ?", (nuevo_estado, ticket_id))
    if nuevo_estado == 'Resuelto':
        cursor.execute("CREATE TABLE IF NOT EXISTS liberaciones (user_id TEXT PRIMARY KEY)")
        cursor.execute("INSERT OR IGNORE INTO liberaciones (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

# --- 3. INTERFAZ PRINCIPAL ---
st.sidebar.title("⚙️ OmniDesk Control")
st.sidebar.markdown("**Técnico Activo:** Admin_01")
menu = st.sidebar.radio("Módulos", ["Gestión de Tickets", "Monitoreo IoT"])

if st.sidebar.button("Cerrar Sesión"):
    st.session_state["autenticado"] = False
    st.rerun()

if menu == "Gestión de Tickets":
    st.title("🖥️ Centro de Soporte Nivel 1")
    
    try:
        df = cargar_tickets()
        
        # --- MÉTRICAS GERENCIALES (KPIs) ---
        total_tickets = len(df)
        abiertos = len(df[df['Estado'] == 'Abierto'])
        resueltos = len(df[df['Estado'] == 'Resuelto'])
        
        kpi1, kpi2, kpi3 = st.columns(3)
        kpi1.metric("Total de Incidentes", total_tickets)
        kpi2.metric("Casos Pendientes", abiertos)
        kpi3.metric("Casos Resueltos", resueltos)
        st.markdown("---")

        col1, col2 = st.columns([5, 2])
        
        with col1:
            st.subheader("📥 Bandeja de Entrada (Activos)")
            df_activos = df[df['Estado'] == 'Abierto'].drop(columns=['user_id'])
            if not df_activos.empty:
                st.dataframe(df_activos, use_container_width=True, hide_index=True)
            else:
                st.success("🎉 No hay tickets pendientes. Bandeja limpia.")
                
            # --- TRAZABILIDAD Y AUDITORÍA ---
            st.subheader("🗄️ Historial de Resoluciones")
            df_resueltos = df[df['Estado'] == 'Resuelto'].drop(columns=['user_id'])
            if not df_resueltos.empty:
                # Mostramos los resueltos en gris para diferenciarlos visualmente
                st.dataframe(df_resueltos, use_container_width=True, hide_index=True)
            else:
                st.info("Aún no hay tickets resueltos en el historial.")
                
        with col2:
            st.subheader("Acciones Técnicas")
            if not df_activos.empty:
                ticket_seleccionado = st.selectbox("Seleccione ID del Ticket", df_activos['id'].tolist())
                if st.button("✅ Marcar como Resuelto", use_container_width=True):
                    user_id = df.loc[df['id'] == ticket_seleccionado, 'user_id'].values[0]
                    actualizar_estado(ticket_seleccionado, user_id, "Resuelto")
                    st.success(f"Ticket #{ticket_seleccionado} cerrado exitosamente.")
                    st.rerun()
                    
            if st.button("🔄 Refrescar Panel", use_container_width=True):
                st.rerun()
    except Exception as e:
        st.error(f"Error de conexión con SQLite: {e}")

elif menu == "Monitoreo IoT":
    render_iot_dashboard(DB_PATH)