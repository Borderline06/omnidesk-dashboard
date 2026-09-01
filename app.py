import streamlit as st

from components.sidebar import mostrar_sidebar
from components.metricas import mostrar_metricas
from components.tickets import mostrar_tickets
from components.iot import mostrar_iot

# Configuración general de la aplicación
st.set_page_config(
    page_title="OmniDesk Dashboard",
    layout="wide"
)

# Obtiene la sección seleccionada desde el sidebar
pagina = mostrar_sidebar()


# Contenido de cada sección
if pagina == "Dashboard":
    st.title("Dashboard")
    mostrar_metricas()

elif pagina == "Soporte Telegram":
    mostrar_tickets()

elif pagina == "Telemetría IoT":
    mostrar_iot()

elif pagina == "Configuración IA":
    st.title("Configuración de IA")