import streamlit as st
import sqlite3
import pandas as pd
import time

@st.fragment(run_every=2)
def render_iot_dashboard(db_path):
    st.title("🌡️ Telemetría de Servidores (IoT)")
    st.markdown("---")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT count(name) FROM sqlite_master WHERE type='table' AND name='iot_metrics'")
        if cursor.fetchone()[0] == 1:
            df_iot = pd.read_sql("SELECT servidor, temperatura, alerta, fecha FROM iot_metrics ORDER BY id DESC LIMIT 20", conn)
        else:
            df_iot = pd.DataFrame()
        conn.close()

        if not df_iot.empty:
            st.subheader("Gráfico de Temperatura (SRV-01)")
            st.line_chart(df_iot.set_index('fecha')['temperatura'])
            
            st.subheader("Registro de Datos")
            st.dataframe(df_iot, use_container_width=True, hide_index=True)
        else:
            st.warning("No hay datos del simulador IoT. En tu terminal del backend, ejecuta 'py core/iot_simulator.py' por 10 segundos.")
    except Exception as e:
        st.error(f"Error al cargar datos IoT: {e}")