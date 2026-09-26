import streamlit as st
import google.generativeai as genai
import os
import tempfile
from dotenv import load_dotenv

# Forzar la sobrescritura de cualquier variable basura en la memoria de Windows
load_dotenv(override=True)

llave_real = os.getenv("GEMINI_API_KEY")

if llave_real:
    # Inyectar la llave limpia y configurar el modelo
    os.environ["GOOGLE_API_KEY"] = llave_real
    genai.configure(api_key=llave_real)
else:
    # Bloqueo de seguridad si el .env no existe en esta carpeta
    st.error("⚠️ No se encontró la variable GEMINI_API_KEY. Revisa tu archivo .env.")

st.title("🤖 Asistente OmniDesk & Transcripción")
st.markdown("Interactúa con la IA técnica o sube un audio para transcribir el problema.")

# --- SECCIÓN 1: TRANSCRIPCIÓN DE AUDIO ---
st.subheader("🎙️ Transcripción de Audio")
archivo_audio = st.file_uploader("Sube un mensaje de voz", type=['mp3', 'wav', 'ogg'])

if archivo_audio is not None:
    if st.button("Transcribir Audio"):
        with st.spinner("Procesando audio directamente en memoria..."):
            try:
                # 1. Leemos los bytes puros sin guardarlos en el disco
                audio_bytes = archivo_audio.read()
                
                # 2. Preparamos el payload con la estructura directa
                datos_audio = {
                    "mime_type": archivo_audio.type,
                    "data": audio_bytes
                }
                
                # 3. Procesamos (puedes cambiar 'gemini-1.5-pro' por el modelo que te funcionó arriba)
                modelo_audio = genai.GenerativeModel('gemini-3.6-flash')
                respuesta_audio = modelo_audio.generate_content([
                    "Transcribe literalmente el contenido de este audio, sin agregar resúmenes.", 
                    datos_audio
                ])
                
                st.success("Transcripción completada:")
                st.info(respuesta_audio.text)

                # Instanciamos un modelo localmente para resolver el problema transcrito
                modelo_resolucion = genai.GenerativeModel('gemini-3.6-flash')
                solucion = modelo_resolucion.generate_content(
                    f"Eres un técnico de soporte TI. Resuelve de forma breve este problema: {respuesta_audio.text}"
                )
                st.success("Sugerencia Técnica de OmniDesk AI:")
                st.write(solucion.text)
                                
            except Exception as e:
                st.error(f"Error procesando el audio: {e}")

st.divider()
# --- SECCIÓN 2: CHATBOT INTERACTIVO ---
st.subheader("💬 Chat de Soporte Técnico")

# Inicializar historial de chat en la memoria de la sesión
if "mensajes_chat" not in st.session_state:
    st.session_state.mensajes_chat = []

# Mostrar historial
for mensaje in st.session_state.mensajes_chat:
    with st.chat_message(mensaje["rol"]):
        st.markdown(mensaje["contenido"])

# Caja de texto para el usuario
texto_usuario = st.chat_input("Escribe tu problema técnico aquí...")

if texto_usuario:
    # 1. Mostrar mensaje del usuario
    with st.chat_message("user"):
        st.markdown(texto_usuario)
    st.session_state.mensajes_chat.append({"rol": "user", "contenido": texto_usuario})

    # 2. Obtener respuesta de Gemini
    with st.chat_message("assistant"):
        with st.spinner("Analizando..."):
            try:
                modelo_chat = genai.GenerativeModel('gemini-3.6-flash')
                respuesta = modelo_chat.generate_content(
                    f"Eres un técnico de soporte Nivel 1. Responde de forma breve y técnica a este problema: {texto_usuario}"
                )
                texto_respuesta = respuesta.text
                st.markdown(texto_respuesta)
                st.session_state.mensajes_chat.append({"rol": "assistant", "contenido": texto_respuesta})
            except Exception as e:
                st.error(f"Error de conexión con la IA: {e}")