import requests
import streamlit as st


API_URL = "http://127.0.0.1:8000/api/tickets"


def obtener_tickets():
    try:
        respuesta = requests.get(API_URL, timeout=5)
        respuesta.raise_for_status()
        return respuesta.json()

    except requests.RequestException:
        st.error("No se pudo conectar con la API de tickets.")
        return []


def mostrar_tickets():
    st.title("Soporte Técnico")

    tickets = obtener_tickets()

    if not tickets:
        st.info("No hay tickets disponibles.")
        return

    estados = ["Todos", "Abierto", "En Proceso", "Resuelto"]
    gravedades = ["Todas", "Alta", "Media", "Baja"]

    col1, col2 = st.columns(2)

    with col1:
        estado = st.selectbox("Estado", estados)

    with col2:
        gravedad = st.selectbox("Nivel de gravedad", gravedades)

    tickets_filtrados = tickets

    if estado != "Todos":
        tickets_filtrados = [
            ticket
            for ticket in tickets_filtrados
            if ticket["Estado"] == estado
        ]

    if gravedad != "Todas":
        tickets_filtrados = [
            ticket
            for ticket in tickets_filtrados
            if ticket["Nivel_Gravedad"] == gravedad
        ]

    st.write(f"Tickets encontrados: {len(tickets_filtrados)}")

    st.dataframe(
        tickets_filtrados,
        use_container_width=True,
        hide_index=True
    )