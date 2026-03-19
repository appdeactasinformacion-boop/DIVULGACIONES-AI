import streamlit as st
import google.generativeai as genai
from PIL import Image, ImageDraw, ImageFont
import os
import io
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
from dotenv import load_dotenv
import PyPDF2
import docx

# Cargar variables de entorno
load_dotenv()

# Configuración de la API de Gemini
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    st.error("No se encontró la clave de API de Gemini. Configúrala en el archivo .env")
    st.stop()

genai.configure(api_key=GEMINI_API_KEY)

# Lista completa de procesos (proporcionada por el usuario)
PROCESOS = [
    "ADHERENCIA AL TRATAMIENTO", "ADMISIONES", "ALMACÉN", "AMBIENTE FÍSICO",
    "ANESTESIOLOGÍA", "ARCHIVO CLÍNICO", "ATENCION PREHOSPITALARIA (PHE)",
    "AUDITORÍA", "AUDITORÍA CONCURRENTE", "AUDITORÍA DE CUENTAS MÉDICAS",
    "CALIBRACIÓN", "CALL CENTER", "CARTERA", "CENTRAL DE MEZCLAS PARENTERALES",
    "CIRUGÍA", "CLÍNICA ERMITA", "COCINA", "COMPRAS", "CONSULTA EXTERNA",
    "CONTABILIDAD", "CONTRATACIÓN", "CONTROL INTERNO", "CONVENIO", "COSTOS",
    "CUENTA DE ALTO COSTO", "CUMPLIMIENTO", "DIRECCIONAMIENTO",
    "DIRECCIONAMIENTO ESTRATÉGICO", "DPTO. ENFERMERÍA", "ENFERMERIA",
    "ENFOQUE AL CLIENTE", "ESTERILIZACIÓN", "FACTURACIÓN", "FINANCIERA",
    "GASES MEDICINALES", "GESTIÓN ADMINISTRATIVA", "GESTIÓN AMBIENTAL",
    "GESTIÓN DE ACTIVOS FIJOS", "GESTIÓN DE COSTOS", "GESTIÓN DE LA CALIDAD",
    "GESTIÓN DE LA INFORMACIÓN", "GESTIÓN DE MEDIO AMBIENTE",
    "GESTIÓN DE RIESGOS", "GESTIÓN DEL TALENTO HUMANO",
    "GESTIÓN DE TECNOLOGÍA BIOMÉDICA", "GESTIÓN DE TECNOLOGÍA NO PBS",
    "GESTIÓN JURÍDICA", "GESTIÓN MÉDICA", "HEMODINAMIA", "HOSPITALIZACIÓN",
    "IMÁGENES DIAGNÓSTICAS", "INFORMACIÓN AL USUARIO", "INVENTARIOS",
    "JURÍDICA", "LABORATORIO CLÍNICO", "MANTENIMIENTO", "MEDICAR",
    "MERCADEO Y COMUNICACIONES", "NUTRICIÓN Y DIETÉTICA", "OBSTETRICIA",
    "ONCOLOGÍA", "PATOLOGÍA", "PROCESOS", "PROGRAMA CANGURO",
    "REFERENCIA Y CONTRARREFERENCIA", "SEGUIMIENTO Y MEJORA",
    "SEGURIDAD DEL PACIENTE", "SEGURIDAD Y SALUD EN EL TRABAJO",
    "SERVICIO FARMACÉUTICO", "SERVICIO TRANSFUSIONAL", "SERVICIOS GENERALES",
    "SIAU", "SISTEMAS DE INFORMACIÓN", "TALENTO HUMANO",
    "TECNOLOGÍA BIOMÉDICA", "TERAPIA", "TESORERÍA", "UNIDAD DE CUIDADO ADULTO",
    "UNIDAD DE CUIDADO NEONATAL", "UNIDAD TRANSFUSIONAL", "URGENCIAS",
    "VACUNACIÓN", "INVESTIGACIÓN", "VIGILANCIA EPIDEMIOLÓGICA Y SEGURIDAD"
]

# Coordenadas aproximadas para cada campo en la imagen (debes ajustarlas)
# Para obtener coordenadas exactas, puedes usar un editor de imágenes o Paint y anotar las posiciones.
COORDINATES = {
    "proceso": (200, 150),      # Ejemplo: (x, y)
    "version": (200, 220),
    "documento": (200, 290),
    "vigencia": (200, 360),
    "importancia": (200, 430)
}

# Fuente para escribir en la imagen (ajusta ruta si tienes una fuente específica)
FONT_PATH = "arial.ttf"  # En Windows suele estar disponible, en Linux puede necesitar instalarse
FONT_SIZE = 24

# Configuración de correo
SMTP_SERVER = os.getenv("SMTP_SERVER")
SMTP_PORT = int(os.getenv("SMTP_PORT", 587))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD")

# Cuerpo del correo (el mismo que proporcionaste)
EMAIL_BODY = """
Buen día.

Cordial saludo.

El formato está disponible en la plataforma IT SOLUTION y pueden consultarse siguiendo esta ruta:
Gestión Documental → Consultar Documentos → (Seleccionar empresa) → Filtrar por nombre o código.

Para acceder, puede ingresar a través del siguiente enlace:
http://190.131.206.250:8085/ItSolution/index.jsp

Cordialmente,
"""

# ------------------ Funciones auxiliares ------------------

def extraer_texto_de_pdf(archivo):
    """Extrae texto de un archivo PDF subido."""
    texto = ""
    try:
        pdf_reader = PyPDF2.PdfReader(archivo)
        for pagina in pdf_reader.pages:
            texto += pagina.extract_text()
    except Exception as e:
        st.error(f"Error al leer PDF: {e}")
    return texto

def extraer_texto_de_docx(archivo):
    """Extrae texto de un archivo Word subido."""
    texto = ""
    try:
        doc = docx.Document(archivo)
        for parrafo in doc.paragraphs:
            texto += parrafo.text + "\n"
    except Exception as e:
        st.error(f"Error al leer DOCX: {e}")
    return texto

def call_gemini_api(texto_documento):
    """
    Envía el texto extraído a Gemini y recibe un JSON con los campos.
    El prompt está diseñado para seguir las instrucciones del usuario.
    """
    # Crear el prompt
    prompt = f"""
    A continuación se proporciona el texto de un documento de la clínica. Debes extraer la siguiente información y devolverla ÚNICAMENTE en formato JSON válido, sin explicaciones adicionales:

    - proceso: Debe coincidir exactamente con uno de los siguientes procesos (elige el más adecuado): {', '.join(PROCESOS)}. Si no coincide con ninguno, elige el más cercano o "OTRO".
    - version: La versión del documento (por ejemplo, "01", "02", etc.). Si el documento es un manual de funciones, debe tener el formato "consecutivo: XX" (donde XX es el número).
    - documento: El nombre completo del documento.
    - vigencia: La fecha de vigencia (formato DD/MM/AAAA). Si es un manual de funciones, debe ser "No aplica".
    - importancia: Un párrafo de máximo 15 palabras que resuma la importancia del documento.
    - es_manual: true si es un manual de funciones, false en caso contrario.

    Texto del documento:
    {texto_documento[:10000]}  # Limitar a 10000 caracteres para no exceder tokens

    Devuelve SOLO el JSON.
    """
    
    try:
        model = genai.GenerativeModel('gemini-1.5-flash')  # o 'gemini-1.5-pro'
        response = model.generate_content(prompt)
        # Limpiar la respuesta (a veces Gemini devuelve markdown con ```json)
        texto_respuesta = response.text
        # Extraer JSON si está entre ```json y ```
        json_match = re.search(r'```json\s*(\{.*?\})\s*```', texto_respuesta, re.DOTALL)
        if json_match:
            texto_respuesta = json_match.group(1)
        else:
            # Intentar encontrar cualquier objeto JSON en la respuesta
            json_match = re.search(r'(\{.*\})', texto_respuesta, re.DOTALL)
            if json_match:
                texto_respuesta = json_match.group(1)
        # Convertir a diccionario
        import json
        data = json.loads(texto_respuesta)
        return data
    except Exception as e:
        st.error(f"Error al llamar a Gemini: {e}")
        return None

def generar_imagen_con_texto(datos):
    """
    Abre la plantilla, escribe los textos en las coordenadas y retorna la imagen PIL.
    """
    template_path = "images/plantilla_ermita.png"
    if not os.path.exists(template_path):
        st.error("No se encontró la plantilla en images/plantilla_ermita.png")
        return None

    img = Image.open(template_path)
    draw = ImageDraw.Draw(img)

    # Cargar fuente
    try:
        font = ImageFont.truetype(FONT_PATH, FONT_SIZE)
    except:
        font = ImageFont.load_default()
        st.warning("No se pudo cargar la fuente arial.ttf, se usará la fuente por defecto.")

    # Escribir cada campo
    for campo, (x, y) in COORDINATES.items():
        texto = str(datos.get(campo, ""))
        if campo == "importancia":
            # Dibujar texto con ajuste de línea (wrap)
            draw_text_wrapped(draw, texto, x, y, font, max_width=300, line_spacing=5)
        else:
            draw.text((x, y), texto, fill="black", font=font)

    return img

def draw_text_wrapped(draw, text, x, y, font, max_width, line_spacing=5):
    """
    Dibuja texto con ajuste de línea (wrap) para que no se salga del cuadro.
    """
    lines = []
    words = text.split()
    if not words:
        return
    current_line = words[0]
    for word in words[1:]:
        # Ancho de la línea si agregamos la palabra
        test_line = current_line + " " + word
        bbox = draw.textbbox((0, 0), test_line, font=font)
        line_width = bbox[2] - bbox[0]
        if line_width <= max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word
    lines.append(current_line)

    # Dibujar cada línea
    current_y = y
    for line in lines:
        draw.text((x, current_y), line, fill="black", font=font)
        # Calcular altura de la línea para la siguiente
        bbox = draw.textbbox((0, 0), line, font=font)
        line_height = bbox[3] - bbox[1]
        current_y += line_height + line_spacing

def enviar_correo(destinatarios, asunto, cuerpo, imagen_pil):
    """
    Envía un correo con la imagen adjunta.
    destinatarios: lista de correos o string con correos separados por coma.
    """
    if not SMTP_SERVER or not SMTP_USER or not SMTP_PASSWORD:
        st.error("Configuración de correo incompleta en el archivo .env")
        return False

    # Convertir destinatarios a lista
    if isinstance(destinatarios, str):
        destinatarios = [d.strip() for d in destinatarios.split(",")]

    # Crear mensaje
    msg = MIMEMultipart()
    msg['From'] = SMTP_USER
    msg['To'] = ", ".join(destinatarios)
    msg['Subject'] = asunto

    # Cuerpo del correo
    msg.attach(MIMEText(cuerpo, 'plain'))

    # Adjuntar imagen
    img_bytes = io.BytesIO()
    imagen_pil.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    image_mime = MIMEImage(img_bytes.read(), name='divulgacion.png')
    msg.attach(image_mime)

    try:
        server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
        server.starttls()
        server.login(SMTP_USER, SMTP_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        st.error(f"Error al enviar correo: {e}")
        return False

def obtener_correos_por_proceso(proceso):
    """
    Función para mapear proceso a lista de correos.
    Por ahora retorna un correo genérico; debes personalizarlo.
    """
    # Esto es un ejemplo. Debes crear un diccionario con los correos reales.
    # Por simplicidad, aquí retornamos un correo fijo.
    correos_por_proceso = {
        "ANESTESIOLOGÍA": "anestesia@clinicaermita.com",
        "ENFERMERIA": "enfermeria@clinicaermita.com",
        # ... agregar todos los procesos
    }
    return correos_por_proceso.get(proceso, "divulgaciones@clinicaermita.com")

# ------------------ Interfaz de Streamlit ------------------

st.set_page_config(page_title="Divulgaciones AI", layout="wide")
st.title("📢 Automatización de Divulgaciones - Clínica La Ermita")
st.markdown("Carga un documento (PDF o Word) para generar automáticamente la imagen de divulgación y enviarla por correo.")

uploaded_file = st.file_uploader("Selecciona un documento", type=["pdf", "docx"])

if uploaded_file is not None:
    # Extraer texto según tipo de archivo
    with st.spinner("Extrayendo texto del documento..."):
        if uploaded_file.type == "application/pdf":
            texto = extraer_texto_de_pdf(uploaded_file)
        elif uploaded_file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            texto = extraer_texto_de_docx(uploaded_file)
        else:
            st.error("Tipo de archivo no soportado")
            st.stop()

    if texto:
        st.success("Texto extraído correctamente.")
        with st.expander("Ver texto extraído (primeros 1000 caracteres)"):
            st.write(texto[:1000] + "...")

        # Llamar a Gemini
        with st.spinner("Analizando documento con IA..."):
            datos_extraidos = call_gemini_api(texto)

        if datos_extraidos:
            st.subheader("Datos extraídos por la IA")
            st.json(datos_extraidos)

            # Generar imagen
            with st.spinner("Generando imagen de divulgación..."):
                imagen = generar_imagen_con_texto(datos_extraidos)

            if imagen:
                st.image(imagen, caption="Vista previa de la divulgación", use_column_width=True)

                # Obtener destinatarios
                proceso = datos_extraidos.get("proceso", "")
                destinatarios = obtener_correos_por_proceso(proceso)

                # Asunto del correo
                nombre_doc = datos_extraidos.get("documento", "Documento")
                asunto = f"Actualización de Documento - {nombre_doc}"

                # Botón para enviar
                if st.button("📧 Enviar divulgación por correo"):
                    with st.spinner("Enviando correo..."):
                        exito = enviar_correo(destinatarios, asunto, EMAIL_BODY, imagen)
                        if exito:
                            st.success("Correo enviado exitosamente.")
                        else:
                            st.error("Error al enviar el correo.")
    else:
        st.error("No se pudo extraer texto del documento.")
