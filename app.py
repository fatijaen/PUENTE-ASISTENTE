import streamlit as st
import os
from openai import OpenAI
from pydantic import BaseModel, Field
import json

# Configuración de la página web
st.set_page_config(page_title="PUENTE - Tu asistente de ayuda", layout="wide", page_icon="🤝")

# Cargar el contenido editable sin tocar el diseño ni la lógica principal.
RUTA_CONTENIDO = os.path.join(os.path.dirname(__file__), "respuestas.json")


def cargar_contenido():
    """Lee las respuestas y textos editables desde respuestas.json."""
    try:
        with open(RUTA_CONTENIDO, "r", encoding="utf-8") as archivo:
            return json.load(archivo)
    except (FileNotFoundError, json.JSONDecodeError):
        return {
            "identidad": {
                "nombre": "PUENTE",
                "subtitulo": "Tu asistente de ayuda",
                "mensaje_bienvenida": "Hola, soy PUENTE. Estoy aquí para ayudarte con tus dudas y trámites.",
                "mensaje_espera": "Estoy preparando una respuesta sencilla para ti..."
            },
            "instrucciones": {"tono": "Cercano y sencillo.", "lectura_facil": []},
            "opciones_iniciales": [],
            "temas": {}
        }


CONTENIDO = cargar_contenido()
IDENTIDAD = CONTENIDO["identidad"]

# Inicializar la API de OpenAI desde los Secrets de Streamlit
API_KEY = st.secrets.get("OPENAI_API_KEY", os.getenv("OPENAI_API_KEY", "TU_OPENAI_API_KEY_AQUI"))
client = OpenAI(api_key=API_KEY)


# 1. ESTRUCTURA DEL FORMULARIO DE CITA
class FormularioCita(BaseModel):
    motivo_consulta: str = Field(default="", description="Síntoma o motivo en palabras simples.")
    especialidad: str = Field(default="", description="Medicina General, Pediatría o Enfermería.")
    preferencia_horario: str = Field(default="", description="Mañana, tarde o lo antes posible.")
    datos_completos: bool = Field(default=False, description="¿Están todos los datos listos?")


if "formulario" not in st.session_state:
    st.session_state.formulario = {
        "motivo_consulta": "",
        "especialidad": "",
        "preferencia_horario": "",
        "datos_completos": False
    }
if "historial_chat" not in st.session_state:
    st.session_state.historial_chat = [
        {"role": "assistant", "content": IDENTIDAD["mensaje_bienvenida"]}
    ]
if "audio_generado" not in st.session_state:
    st.session_state.audio_generado = None


# FUNCIONES RELEVANTES DE IA
def procesar_con_ia(texto_usuario):
    """Actualiza el formulario y genera una respuesta según el contenido editable."""
    instrucciones = CONTENIDO.get("instrucciones", {})
    temas = CONTENIDO.get("temas", {})
    opciones = CONTENIDO.get("opciones_iniciales", [])

    prompt_sistema = f"""
    Eres PUENTE, {IDENTIDAD.get('subtitulo', 'Tu asistente de ayuda')} para personas que necesitan apoyo.

    Responde en el mismo idioma que use la persona.
    Tu tono debe ser: {instrucciones.get('tono', 'cercano, respetuoso y sencillo')}.

    REGLAS DE LECTURA FÁCIL:
    {json.dumps(instrucciones.get('lectura_facil', []), ensure_ascii=False, indent=2)}

    ESTRUCTURA OBLIGATORIA:
    {json.dumps(instrucciones.get('estructura_respuesta', []), ensure_ascii=False, indent=2)}

    CONTENIDO EDITABLE DE REFERENCIA:
    {json.dumps(temas, ensure_ascii=False, indent=2)}

    OPCIONES QUE PUEDES OFRECER:
    {json.dumps(opciones, ensure_ascii=False, indent=2)}

    ESTADO ACTUAL DEL FORMULARIO:
    {st.session_state.formulario}

    No inventes información. Si no conoces un dato, dilo y recomienda consultar una fuente oficial o una persona profesional.
    Devuelve primero una respuesta breve. Si la persona pide más detalle, explica los pasos de forma numerada.
    """

    class RespuestaSistema(BaseModel):
        respuesta_lectura_facil: str
        formulario_actualizado: FormularioCita

    response = client.beta.chat.completions.parse(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": texto_usuario}
        ],
        response_format=RespuestaSistema
    )

    mensaje = response.choices[0].message
    resultado = mensaje.parsed
    return {
        "respuesta_lectura_facil": resultado.respuesta_lectura_facil,
        "formulario_actualizado": resultado.formulario_actualizado.model_dump()
    }


def texto_a_voz(texto):
    """Transforma el texto de la IA en un audio hablado."""
    response = client.audio.speech.create(
        model="tts-1",
        voice="shimmer",
        input=texto
    )
    audio_path = "respuesta.mp3"
    response.stream_to_file(audio_path)
    return audio_path


# 2. DISEÑO DE LA INTERFAZ DE USUARIO
st.title(f"🤝 {IDENTIDAD['nombre']}")
st.subheader(IDENTIDAD.get("subtitulo", "Tu asistente de ayuda"))

col1, col2 = st.columns(2, gap="large")

with col1:
    st.markdown("### 📋 Tu información")
    st.caption("PUENTE guarda los datos necesarios para ayudarte con la consulta.")

    st.text_input("¿Qué necesitas?", value=st.session_state.formulario["motivo_consulta"], disabled=True)

    lista_especialidades = ["", "Medicina General", "Pediatría", "Enfermería"]
    idx_esp = lista_especialidades.index(st.session_state.formulario["especialidad"]) if st.session_state.formulario["especialidad"] in lista_especialidades else 0
    st.selectbox("Tipo de atención", lista_especialidades, index=idx_esp, disabled=True)

    st.text_input("Preferencia de horario", value=st.session_state.formulario["preferencia_horario"], disabled=True)

    if st.session_state.formulario["datos_completos"]:
        st.success("✅ Todo listo. Hemos recogido la información necesaria.")
    else:
        st.info("⏳ Cuando me cuentes lo que necesitas, iré completando esta información.")

with col2:
    st.markdown(f"### 💬 {IDENTIDAD['nombre']}")
    st.caption("Estoy disponible para ayudarte paso a paso.")

    for mensaje in st.session_state.historial_chat:
        with st.chat_message(mensaje["role"]):
            st.write(mensaje["content"])

    if st.session_state.audio_generado and os.path.exists(st.session_state.audio_generado):
        st.audio(st.session_state.audio_generado, format="audio/mp3", autoplay=True)

    st.markdown("---")
    st.markdown("**🎙️ Puedes hablar conmigo o escribir tu pregunta:**")

    archivo_audio = st.audio_input("Graba tu voz aquí")
    entrada_texto = st.chat_input("Escribe aquí lo que necesitas...")

    texto_a_procesar = ""

    if archivo_audio is not None:
        with open("audio_usuario.wav", "wb") as f:
            f.write(archivo_audio.read())

        with open("audio_usuario.wav", "rb") as audio_file:
            transcripcion = client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file
            )
        texto_a_procesar = transcripcion.text

    elif entrada_texto:
        texto_a_procesar = entrada_texto

    if texto_a_procesar:
        st.session_state.historial_chat.append({"role": "user", "content": texto_a_procesar})

        with st.spinner(IDENTIDAD.get("mensaje_espera", "Estoy preparando una respuesta sencilla para ti...")):
            resultado_ia = procesar_con_ia(texto_a_procesar)

        st.session_state.formulario = resultado_ia["formulario_actualizado"]
        respuesta_texto = resultado_ia["respuesta_lectura_facil"]

        st.session_state.historial_chat.append({"role": "assistant", "content": respuesta_texto})

        archivo_voz = texto_a_voz(respuesta_texto)
        st.session_state.audio_generado = archivo_voz

        st.rerun()
