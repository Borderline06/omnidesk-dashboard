import requests
import streamlit as st

API_URL = "http://127.0.0.1:8000/api/iot"

def obtener_datos_iot():
    try:
        return requests.get(API_URL, timeout=5).json()
    except requests.RequestException:
        return None

@st.fragment(run_every=4)
def mostrar_iot():
    st.title(" Infraestructura (Telemetría IoT)")

    datos = obtener_datos_iot()
    if not datos:
        st.error("No se pudo obtener la telemetría del servidor.")
        return

    temperatura = datos.get("temperatura", 0)
    estado = datos.get("estado", "NORMAL")
    servidor = datos.get("servidor", "Servidor Desconocido")
    historial = datos.get("historial", [])

    # Tarjetas de Métricas Superiores
    with st.container(border=True):
        col1, col2 = st.columns(2)
        col1.metric("Servidor Monitoreado", servidor)
        col2.metric(
            "Temperatura Actual", 
            f"{temperatura} °C", 
            delta="CRÍTICO (>65°C)" if temperatura > 65.0 else "OPERATIVO",
            delta_color="inverse" if temperatura > 65.0 else "normal"
        )

    # Alertas Condicionales
    if temperatura > 65.0:
        st.error(f"ALERTA CRÍTICA: La temperatura de {servidor} ha superado el umbral seguro ({temperatura} °C).")
    else:
        st.success(f"Estado del sistema: Normal ({temperatura} °C).")

    # Gráfica de Líneas Continua
    with st.container(border=True):
        st.subheader("Historial de Temperatura en Tiempo Real")
        if historial:
            st.line_chart(historial)