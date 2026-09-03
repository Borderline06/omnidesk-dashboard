import requests
import streamlit as st

API_IOT = "http://127.0.0.1:8000/api/iot"
API_TICKETS = "http://127.0.0.1:8000/api/tickets"

def obtener_datos():
    try:
        iot = requests.get(API_IOT, timeout=5).json()
        tickets = requests.get(API_TICKETS, timeout=5).json()
        return iot, tickets
    except requests.RequestException:
        return None, []

@st.fragment(run_every=4)
def mostrar_metricas():
    datos_iot, tickets = obtener_datos()

    tickets_abiertos = sum(1 for t in tickets if t.get("Estado") == "Abierto")
    tickets_criticos = sum(1 for t in tickets if t.get("Nivel_Gravedad") in ["Alta", "CRITICO"])

    st.subheader("Estado General del Sistema")
    
    with st.container(border=True):
        col1, col2, col3 = st.columns(3)
        col1.metric("Tickets Abiertos", tickets_abiertos)
        col2.metric("Tickets Críticos", tickets_criticos)

        if datos_iot:
            temp = datos_iot.get("temperatura", 0)
            estado = datos_iot.get("estado", "NORMAL")
            delta_val = "Alerta Térmica" if temp > 65.0 else "Estable"
            col3.metric("Temperatura Server 01", f"{temp} °C", delta=delta_val, delta_color="inverse" if temp > 65 else "normal")
        else:
            col3.metric("Temperatura Server 01", "Sin datos")