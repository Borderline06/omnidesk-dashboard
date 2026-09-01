import requests
import streamlit as st


# URL de la API del backend que proporciona los datos del sensor IoT
API_URL = "http://127.0.0.1:8000/api/iot"


# Obtiene los datos actuales del sensor mediante la API
def obtener_datos_iot():
    try:
        respuesta = requests.get(API_URL, timeout=5)
        respuesta.raise_for_status()
        return respuesta.json()

    except requests.RequestException:
        st.error("No se pudo conectar con la API del backend.")
        return None


# Actualiza la sección de IoT automáticamente cada 4 segundos
@st.fragment(run_every=4)
def mostrar_iot():
    st.title("Telemetría IoT")

    datos = obtener_datos_iot()

    if datos is None:
        return

    # Extrae la información recibida desde la API
    temperatura = datos.get("temperatura")
    estado = datos.get("estado")
    servidor = datos.get("servidor")
    historial = datos.get("historial", [])

    # Muestra la temperatura y el estado actual
    col1, col2 = st.columns(2)

    with col1:
        st.metric(
            "Temperatura actual",
            f"{temperatura} °C"
        )

    with col2:
        st.metric(
            "Estado",
            estado
        )

    st.write(f"Servidor: {servidor}")

    # Muestra una alerta según el umbral de temperatura
    if temperatura > 65:
        st.error(
            f"ALERTA CRÍTICA: temperatura de {temperatura} °C"
        )
    else:
        st.success(
            f"Temperatura normal: {temperatura} °C"
        )

    # Muestra el historial de temperaturas en un gráfico
    st.subheader("Historial de temperatura")

    if historial:
        st.line_chart(historial)