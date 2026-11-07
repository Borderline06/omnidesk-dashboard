import os
import sqlite3
import time
from contextlib import closing
from datetime import datetime

import pandas as pd
import streamlit as st

FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
ORIGENES = {"auto": "Automático", "manual": "Manual"}


def _conectar(db_path):
    return sqlite3.connect(db_path, timeout=15)


def inicializar_reportes(db_path):
    """Crea las tablas por si el dashboard arranca antes que el backend."""
    with closing(_conectar(db_path)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS app_config (clave TEXT PRIMARY KEY, valor TEXT NOT NULL)")
        conn.execute(
            "CREATE TABLE IF NOT EXISTS reportes_log (id INTEGER PRIMARY KEY AUTOINCREMENT, fecha TEXT NOT NULL, "
            "origen TEXT NOT NULL, destinatario TEXT, ok INTEGER NOT NULL, detalle TEXT)"
        )
        conn.commit()


def _leer(conn, clave, default):
    fila = conn.execute("SELECT valor FROM app_config WHERE clave = ?", (clave,)).fetchone()
    return fila[0] if fila else default


def _guardar(conn, clave, valor):
    conn.execute(
        "INSERT INTO app_config (clave, valor) VALUES (?, ?) ON CONFLICT(clave) DO UPDATE SET valor = excluded.valor",
        (clave, str(valor)),
    )
    conn.commit()


def _esperar_resultado(db_path, ultimo_id, segundos=60):
    """Espera a que el backend registre el envío manual solicitado."""
    for _ in range(segundos // 2):
        time.sleep(2)
        with closing(_conectar(db_path)) as conn:
            fila = conn.execute(
                "SELECT ok, detalle FROM reportes_log WHERE id > ? AND origen = 'manual' ORDER BY id LIMIT 1",
                (ultimo_id,),
            ).fetchone()
        if fila:
            return fila
    return None


def render_reportes(db_path):
    st.title("📊 Reportes al gerente")
    st.caption(
        "El reporte resume los tickets del día y la telemetría IoT, y se envía por correo con el detalle en CSV. "
        "Lo envía el backend (bot), que debe estar en ejecución."
    )
    gerente = os.getenv("EMAIL_GERENTE")
    if gerente:
        st.caption(f"Destinatario: {gerente}")

    with closing(_conectar(db_path)) as conn:
        auto_activo = _leer(conn, "reporte_auto", "0") == "1"
        hora_txt = _leer(conn, "reporte_hora", os.getenv("REPORTE_HORA", "18:00"))
    try:
        hora_actual = datetime.strptime(hora_txt, "%H:%M").time()
    except ValueError:
        hora_actual = datetime.strptime("18:00", "%H:%M").time()

    col_cfg, col_manual = st.columns(2)

    with col_cfg:
        with st.container(border=True):
            st.subheader("⏰ Envío automático")
            with st.form("config_reporte"):
                auto = st.toggle("Enviar el reporte automáticamente cada día", value=auto_activo)
                hora = st.time_input("Hora de envío", value=hora_actual, step=300)
                if st.form_submit_button("💾 Guardar", use_container_width=True):
                    with closing(_conectar(db_path)) as conn:
                        _guardar(conn, "reporte_auto", "1" if auto else "0")
                        _guardar(conn, "reporte_hora", hora.strftime("%H:%M"))
                    st.toast("Configuración guardada ✅")
                    st.rerun()
            if auto_activo:
                st.info(f"Modo **automático**: se envía todos los días a las {hora_txt}.")
            else:
                st.info("Modo **manual**: solo se envía cuando pulsas el botón.")

    with col_manual:
        with st.container(border=True):
            st.subheader("📤 Envío manual")
            st.write("Envía ahora el reporte del día, sin importar el modo automático.")
            if st.button("📤 Enviar reporte ahora", type="primary", use_container_width=True):
                with closing(_conectar(db_path)) as conn:
                    ultimo_id = conn.execute("SELECT COALESCE(MAX(id), 0) FROM reportes_log").fetchone()[0]
                    _guardar(conn, "reporte_manual_pendiente", datetime.now().strftime(FORMATO_FECHA))
                with st.spinner("Generando y enviando el reporte..."):
                    resultado = _esperar_resultado(db_path, ultimo_id)
                if resultado is None:
                    st.warning("El backend no respondió a tiempo. Verifica que el bot esté en ejecución.")
                elif resultado[0]:
                    st.success(resultado[1])
                else:
                    st.error(resultado[1])

    st.subheader("🗂️ Últimos envíos")
    with closing(_conectar(db_path)) as conn:
        df = pd.read_sql_query(
            "SELECT fecha, origen, destinatario, ok, detalle FROM reportes_log ORDER BY id DESC LIMIT 10", conn
        )
    if df.empty:
        st.info("Todavía no se ha enviado ningún reporte.")
        return
    df["origen"] = df["origen"].map(ORIGENES).fillna(df["origen"])
    df["ok"] = df["ok"].map({1: "✅ Enviado", 0: "❌ Error"})
    df.columns = ["Fecha", "Origen", "Destinatario", "Resultado", "Detalle"]
    st.dataframe(df, use_container_width=True, hide_index=True)
