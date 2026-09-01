import streamlit as st


def mostrar_sidebar():
    # Estilos del menú lateral
    st.markdown("""
    <style>
    [data-testid="stSidebar"] {
        background-color: #111827;
    }

    [data-testid="stSidebar"] h1 {
        color: white;
        font-size: 24px;
        padding: 10px 8px 25px;
    }

    [data-testid="stSidebar"] .stButton button {
        width: 100%;
        border: none;
        border-radius: 8px;
        background-color: transparent;
        color: #9ca3af;
        text-align: left;
        padding: 12px 15px;
        margin: 3px 0;
    }

    [data-testid="stSidebar"] .stButton button:hover {
        background-color: #1f2937;
        color: white;
    }

    [data-testid="stSidebar"] .stButton button:focus {
        background-color: #374151;
        color: white;
        border: none;
    }
    </style>
    """, unsafe_allow_html=True)

    # Título del menú
    st.sidebar.title("OmniDesk")

    # Inicializa la página por defecto
    if "pagina" not in st.session_state:
        st.session_state.pagina = "Dashboard"

    # Opciones de navegación
    if st.sidebar.button("Dashboard", use_container_width=True):
        st.session_state.pagina = "Dashboard"

    if st.sidebar.button("Soporte Telegram", use_container_width=True):
        st.session_state.pagina = "Soporte Telegram"

    if st.sidebar.button("Telemetría IoT", use_container_width=True):
        st.session_state.pagina = "Telemetría IoT"

    if st.sidebar.button("Configuración IA", use_container_width=True):
        st.session_state.pagina = "Configuración IA"

    # Devuelve la página seleccionada
    return st.session_state.pagina