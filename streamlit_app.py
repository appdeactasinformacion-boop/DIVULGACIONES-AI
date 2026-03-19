import streamlit as st
from PIL import Image
import os

st.set_page_config(page_title="Divulgaciones AI", layout="centered")
st.title("📢 Automatización de Divulgaciones - Clínica La Ermita")

st.write("Bienvenido. Esta herramienta permitirá cargar documentos y generar divulgaciones automáticamente.")

uploaded_file = st.file_uploader("Cargar documento (PDF o Word)", type=["pdf", "docx"])

if uploaded_file is not None:
    st.success("Documento cargado. Aquí se procesará con IA.")
else:
    st.info("Esperando documento...")

# Mostrar la plantilla si existe en la carpeta images
if os.path.exists("images/plantilla_ermita.png"):
    st.image("images/plantilla_ermita.png", caption="Vista previa de la plantilla", use_column_width=True)
else:
    st.warning("No se encontró la plantilla. Coloca 'plantilla_ermita.png' en la carpeta 'images'.")
