import requests
import streamlit as st


API_IOT = "http://127.0.0.1:8000/api/iot"
API_TICKETS = "http://127.0.0.1:8000/api/tickets"


def obtener_datos_iot():
    try:
        respuesta = requests.get(API_IOT, timeout=5)
        respuesta.raise_for_status()
        return respuesta.json()

    except requests.RequestException:
        return None


def obtener_tickets():
    try:
        respuesta = requests.get(API_TICKETS, timeout=5)
        respuesta.raise_for_status()
        return respuesta.json()

    except requests.RequestException:
        return []


@st.fragment(run_every=4)
def mostrar_metricas():

    datos_iot = obtener_datos_iot()
    tickets = obtener_tickets()

    # Contar tickets según su estado
    tickets_abiertos = sum(
        1 for ticket in tickets
        if ticket.get("Estado") == "Abierto"
    )

    # Contar tickets críticos
    tickets_criticos = sum(
        1 for ticket in tickets
        if ticket.get("Nivel_Gravedad") == "Alta"
    )

    # Mostrar métricas
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            label="Tickets abiertos",
            value=tickets_abiertos
        )

    with col2:
        st.metric(
            label="Tickets críticos",
            value=tickets_criticos
        )

    with col3:
        if datos_iot:
            temperatura = datos_iot.get("temperatura", 0)
            estado = datos_iot.get("estado", "NORMAL")

            st.metric(
                label="Temperatura actual",
                value=f"{temperatura} °C"
            )

            # Mostrar estado debajo de la temperatura
            if estado == "CRITICO":
                st.error("Temperatura crítica")
            else:
                st.success("Temperatura normal")

        else:
            st.metric(
                label="Temperatura actual",
                value="Sin conexión"
            )