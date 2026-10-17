import os
import sqlite3
from contextlib import closing
from datetime import datetime

import pandas as pd
import streamlit as st

TEMP_ALERTA = float(os.getenv("TEMP_ALERTA", "32.0"))  # mismo umbral que el backend
SEGUNDOS_DATOS_OBSOLETOS = 120
VENTANAS = [50, 100, 200, 500]


def _conectar_lectura(db_path):
    # Solo lectura: este panel nunca debe escribir en la BD compartida con el bot
    return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, timeout=15)


@st.fragment(run_every=2)
def render_iot_dashboard(db_path):
    st.title("🌡️ Telemetría de Servidores (IoT)")
    st.caption("Panel interno de respaldo a Grafana · actualización automática cada 2 s")

    try:
        with closing(_conectar_lectura(db_path)) as conn:
            existe = conn.execute(
                "SELECT count(name) FROM sqlite_master WHERE type='table' AND name='iot_metrics'"
            ).fetchone()[0]
            servidores = (
                [fila[0] for fila in conn.execute("SELECT DISTINCT servidor FROM iot_metrics ORDER BY servidor")]
                if existe else []
            )

            if not servidores:
                st.warning(
                    "No hay datos del simulador IoT. En el backend ejecuta `python -m core.iot_simulator` "
                    "junto con el suscriptor MQTT (`python -m bot.main`), o levanta los servicios con Docker."
                )
                return

            col_servidor, col_ventana = st.columns(2)
            servidor = col_servidor.selectbox("Servidor", servidores, key="iot_servidor")
            ventana = col_ventana.selectbox("Muestras a mostrar", VENTANAS, index=1, key="iot_ventana")

            df_iot = pd.read_sql_query(
                "SELECT servidor, temperatura, alerta, fecha FROM iot_metrics "
                "WHERE servidor = ? ORDER BY id DESC LIMIT ?",
                conn, params=(servidor, int(ventana)),
            )
    except Exception as e:
        st.error(f"Error al cargar datos IoT: {e}")
        return

    df_iot["fecha"] = pd.to_datetime(df_iot["fecha"], errors="coerce")
    df_iot = df_iot.dropna(subset=["fecha"]).sort_values("fecha")  # cronológico: la consulta viene en orden inverso
    if df_iot.empty:
        st.info("No hay lecturas válidas para este servidor.")
        return

    ultima = df_iot.iloc[-1]
    previa = df_iot.iloc[-2]["temperatura"] if len(df_iot) > 1 else None
    antiguedad = (datetime.now() - ultima["fecha"]).total_seconds()
    if antiguedad > SEGUNDOS_DATOS_OBSOLETOS:
        st.warning(
            f"⚠️ Sin datos recientes: la última lectura de {servidor} es de {ultima['fecha']:%Y-%m-%d %H:%M:%S}. "
            "Verifica que el simulador y el suscriptor MQTT estén en ejecución."
        )

    kpi1, kpi2, kpi3, kpi4 = st.columns(4)
    kpi1.metric(
        "Última lectura", f"{ultima['temperatura']:.1f} °C",
        None if previa is None else f"{ultima['temperatura'] - previa:+.1f} °C",
        delta_color="inverse",
    )
    kpi2.metric("Promedio", f"{df_iot['temperatura'].mean():.1f} °C")
    kpi3.metric("Máximo", f"{df_iot['temperatura'].max():.1f} °C")
    kpi4.metric("Alertas en la ventana", int(df_iot["alerta"].astype(bool).sum()))

    if ultima["temperatura"] > TEMP_ALERTA:
        st.error(f"🔥 {servidor} supera el umbral de alerta ({TEMP_ALERTA:.1f} °C).")

    st.subheader(f"Gráfico de Temperatura ({servidor})")
    grafico = df_iot.set_index("fecha")[["temperatura"]].rename(columns={"temperatura": "Temperatura (°C)"})
    grafico["Umbral de alerta"] = TEMP_ALERTA
    st.line_chart(grafico)

    with st.expander("Registro de Datos"):
        st.dataframe(df_iot.sort_values("fecha", ascending=False), use_container_width=True, hide_index=True)
