import streamlit as st

def mostrar_sidebar():
    st.sidebar.title("OmniDesk AI")
    st.sidebar.caption("Panel de Control Omnicanal")
    st.sidebar.divider()

    if "pagina" not in st.session_state:
        st.session_state.pagina = "Dashboard"

    opciones = {
        "Dashboard": "Dashboard Principal",
        "Soporte Telegram": "Soporte Telegram",
        "Telemetría IoT": "Telemetría IoT",
        "Configuración IA": "Configuración del Asistente"
    }

    for clave, etiqueta in opciones.items():
        if st.sidebar.button(etiqueta, use_container_width=True):
            st.session_state.pagina = clave

    st.sidebar.divider()
    if st.sidebar.button("Actualizar Datos", use_container_width=True):
        st.rerun()

    return st.session_state.pagina