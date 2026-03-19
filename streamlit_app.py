import streamlit as st
from PIL import Image, ImageDraw, ImageFont
import os
import io
import PyPDF2
import docx
import google.generativeai as genai
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.image import MIMEImage
import tempfile

# ------------------------------------------------------------------
# CONFIGURACIÓN DE LA API KEY (Streamlit Secrets o .env local)
# ------------------------------------------------------------------
try:
    # Intenta obtener la clave desde los secrets de Streamlit Cloud
    api_key = st.secrets["GEMINI_API_KEY"]
except:
    # Si no, intenta cargar desde un archivo .env (desarrollo local)
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    st.error("""
        ⚠️ No se encontró la API Key de Gemini.
        - En Streamlit Cloud, configúrala en Settings → Secrets.
        - En local, crea un archivo .env con GEMINI_API_KEY=tu_clave
    """)
    st.stop()

genai.configure(api_key=api_key)

# ------------------------------------------------------------------
# LISTA DE PROCESOS (tal como la proporcionaste)
# ------------------------------------------------------------------
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
    "GESTIÓN DE LA INFORMACIÓN", "GESTIÓN DE MEDIO AMBIENTE", "GESTIÓN DE RIESGOS",
    "GESTIÓN DEL TALENTO HUMANO", "GESTIÓN DE TECNOLOGÍA BIOMÉDICA",
    "GESTIÓN DE TECNOLOGÍA NO PBS", "GESTIÓN JURÍDICA", "GESTIÓN MÉDICA",
    "HEMODINAMIA", "HOSPITALIZACIÓN", "IMÁGENES DIAGNÓSTICAS",
    "INFORMACIÓN AL USUARIO", "INVENTARIOS", "JURÍDICA", "LABORATORIO CLÍNICO",
    "MANTENIMIENTO", "MEDICARDIO", "MERCADEO Y COMUNICACIONES", "NUTRICIÓN Y DIETÉTICA",
    "OBSTETRICIA", "ONCOLOGÍA", "PATOLOGÍA", "PROCESOS", "PROGRAMA CANGURO",
    "REFERENCIA Y CONTRARREFERENCIA", "SEGUIMIENTO Y MEJORA", "SEGURIDAD DEL PACIENTE",
    "SEGURIDAD Y SALUD EN EL TRABAJO", "SERVICIO FARMACÉUTICO", "SERVICIO TRANSFUSIONAL",
    "SERVICIOS GENERALES", "SIAU", "SISTEMAS DE INFORMACIÓN", "TALENTO HUMANO",
    "TECNOLOGÍA BIOMÉDICA", "TERAPIA", "TESORERÍA", "UNIDAD DE CUIDADO ADULTO",
    "UNIDAD DE CUIDADO NEONATAL", "UNIDAD TRANSFUSIONAL", "URGENCIAS", "VACUNACIÓN",
    "INVESTIGACIÓN", "VIGILANCIA EPIDEMIOLÓGICA Y SEGURIDAD"
]

# ------------------------------------------------------------------
# COORDENADAS DE LOS CAMPOS EN LA PLANTILLA (DEBES AJUSTARLAS)
# ------------------------------------------------------------------
# Mide en píxeles la posición de cada recuadro en tu plantilla.
# Ejemplo: (x, y) esquina superior izquierda donde empezar a escribir.
COORDENADAS = {
    "proceso": (220, 140),    # Ajusta según tu imagen
    "version": (220, 200),
    "documento": (220, 260),
    "vigencia": (220, 320),
    "importancia": (220, 380)
}

# ------------------------------------------------------------------
# FUNCIONES AUXILIARES
# ------------------------------------------------------------------
def extraer_texto_de_pdf(archivo):
    """Extrae texto de un archivo PDF subido."""
    texto = ""
    pdf_reader = PyPDF2.PdfReader(archivo)
    for pagina in pdf_reader.pages:
        texto += pagina.extract_text() or ""
    return texto

def extraer_texto_de_docx(archivo):
    """Extrae texto de un archivo Word subido."""
    doc = docx.Document(archivo)
    texto = "\n".join([parrafo.text for parrafo in doc.paragraphs])
    return texto

def analizar_documento_con_gemini(texto_documento):
    """
    Envía el texto del documento a Gemini y pide un JSON estructurado.
    """
    # Construir el prompt con la lista de procesos y las instrucciones
    prompt = f"""
    Eres un asistente que extrae información de documentos internos de una clínica.
    Debes devolver UNICAMENTE un objeto JSON válido con las siguientes claves:
    - "proceso": el proceso responsable (debe coincidir EXACTAMENTE con uno de la lista proporcionada).
    - "version": la versión del documento (formato XX, ej. 01, 02, etc.). Si es un manual de funciones, debe decir "consecutivo: XX".
    - "documento": el nombre completo del documento.
    - "vigencia": la fecha desde que aplica (formato DD/MM/AAAA). Si es manual de funciones, debe decir "No aplica".
    - "importancia": un resumen de máximo 15 palabras explicando la importancia del documento.
    - "es_manual": true si es un manual de funciones, false en caso contrario.

    Lista de procesos válidos:
    {', '.join(PROCESOS)}

    Texto del documento:
    {texto_documento}
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        response = model.generate_content(prompt)
        # Limpiar la respuesta para obtener solo el JSON
        texto_respuesta = response.text
        # Buscar el primer '{' y el último '}' para extraer el JSON
        inicio = texto_respuesta.find('{')
        fin = texto_respuesta.rfind('}') + 1
        if inicio != -1 and fin != 0:
            json_str = texto_respuesta[inicio:fin]
            import json
            datos = json.loads(json_str)
            return datos
        else:
            st.error("No se pudo extraer un JSON válido de la respuesta de Gemini.")
            return None
    except Exception as e:
        st.error(f"Error al llamar a Gemini: {e}")
        return None

def dibujar_texto_con_ajuste(draw, texto, x, y, font, max_ancho, color="black"):
    """
    Dibuja texto ajustándolo a un ancho máximo (para el párrafo de importancia).
    """
    palabras = texto.split()
    lineas = []
    linea_actual = ""
    for palabra in palabras:
        prueba = linea_actual + " " + palabra if linea_actual else palabra
        # Calcula el ancho del texto con la fuente (aproximado)
        bbox = draw.textbbox((0, 0), prueba, font=font)
        ancho = bbox[2] - bbox[0]
        if ancho <= max_ancho:
            linea_actual = prueba
        else:
            if linea_actual:
                lineas.append(linea_actual)
            linea_actual = palabra
    if linea_actual:
        lineas.append(linea_actual)

    # Dibujar cada línea
    y_offset = 0
    for linea in lineas:
        draw.text((x, y + y_offset), linea, fill=color, font=font)
        # Altura aproximada de línea (podrías calcularla con textbbox)
        y_offset += 25  # Ajusta según tamaño de fuente

def generar_imagen_divulgacion(datos):
    """
    Toma la plantilla y escribe los datos extraídos en las coordenadas.
    """
    ruta_plantilla = "images/plantilla_ermita.png"
    if not os.path.exists(ruta_plantilla):
        st.error("No se encuentra la plantilla en images/plantilla_ermita.png")
        return None

    img = Image.open(ruta_plantilla)
    draw = ImageDraw.Draw(img)

    # Cargar fuente (si no existe arial.ttf, usa una por defecto)
    try:
        font = ImageFont.truetype("arial.ttf", 24)
        font_pequena = ImageFont.truetype("arial.ttf", 20)
    except:
        font = ImageFont.load_default()
        font_pequena = ImageFont.load_default()

    # Escribir cada campo
    draw.text(COORDENADAS["proceso"], datos.get("proceso", ""), fill="black", font=font)
    draw.text(COORDENADAS["version"], datos.get("version", ""), fill="black", font=font)
    draw.text(COORDENADAS["documento"], datos.get("documento", ""), fill="black", font=font)
    draw.text(COORDENADAS["vigencia"], datos.get("vigencia", ""), fill="black", font=font)

    # Para la importancia, usamos ajuste de línea
    importancia = datos.get("importancia", "")
    dibujar_texto_con_ajuste(draw, importancia, COORDENADAS["importancia"][0],
                             COORDENADAS["importancia"][1], font_pequena, max_ancho=300)

    return img

def enviar_correo(destinatarios, asunto, cuerpo, imagen, servidor_smtp="smtp.gmail.com", puerto=587, usuario="", password=""):
    """
    Envía un correo con la imagen adjunta. Requiere configuración SMTP.
    Por ahora está comentado; descomenta y completa con tus datos.
    """
    # msg = MIMEMultipart()
    # msg["From"] = usuario
    # msg["To"] = ", ".join(destinatarios) if isinstance(destinatarios, list) else destinatarios
    # msg["Subject"] = asunto
    #
    # msg.attach(MIMEText(cuerpo, "plain"))
    #
    # # Adjuntar imagen
    # img_bytes = io.BytesIO()
    # imagen.save(img_bytes, format="PNG")
    # img_bytes.seek(0)
    # adjunto = MIMEImage(img_bytes.read(), name="divulgacion.png")
    # msg.attach(adjunto)
    #
    # try:
    #     server = smtplib.SMTP(servidor_smtp, puerto)
    #     server.starttls()
    #     server.login(usuario, password)
    #     server.send_message(msg)
    #     server.quit()
    #     return True
    # except Exception as e:
    #     st.error(f"Error al enviar correo: {e}")
    #     return False
    st.info("Funcionalidad de envío de correo desactivada. Configura SMTP en el código.")
    return True  # Simula éxito para pruebas

# ------------------------------------------------------------------
# INTERFAZ DE STREAMLIT
# ------------------------------------------------------------------
st.set_page_config(page_title="Divulgaciones AI - Clínica La Ermita", layout="centered")
st.title("📢 Automatización de Divulgaciones")
st.markdown("Sube un documento (PDF o Word) para generar automáticamente la imagen de divulgación.")

archivo = st.file_uploader("Selecciona el documento", type=["pdf", "docx"])

if archivo is not None:
    # Mostrar nombre del archivo
    st.write(f"**Archivo cargado:** {archivo.name}")

    # Botón para procesar
    if st.button("🔍 Analizar documento con IA"):
        with st.spinner("Extrayendo texto del documento..."):
            if archivo.type == "application/pdf":
                texto = extraer_texto_de_pdf(archivo)
            else:
                texto = extraer_texto_de_docx(archivo)

        if not texto.strip():
            st.warning("No se pudo extraer texto del documento. Verifica que no esté escaneado o protegido.")
        else:
            with st.spinner("Enviando a Gemini para extraer datos..."):
                datos_extraidos = analizar_documento_con_gemini(texto)

            if datos_extraidos:
                st.success("✅ Datos extraídos correctamente")
                st.json(datos_extraidos)

                # Guardar en session_state para usarlos después
                st.session_state["datos"] = datos_extraidos

                # Generar imagen
                with st.spinner("Generando imagen de divulgación..."):
                    imagen_generada = generar_imagen_divulgacion(datos_extraidos)
                    if imagen_generada:
                        st.session_state["imagen"] = imagen_generada
                        st.image(imagen_generada, caption="Vista previa de la divulgación", use_column_width=True)
                    else:
                        st.error("No se pudo generar la imagen. Revisa la ruta de la plantilla.")

# Mostrar la imagen y el botón de envío si ya se generó
if "imagen" in st.session_state:
    st.divider()
    st.subheader("📧 Enviar divulgación por correo")

    # Aquí podrías añadir un selector de destinatarios basado en el proceso
    proceso = st.session_state["datos"].get("proceso", "")
    st.write(f"**Proceso detectado:** {proceso}")

    # Campo para ingresar correos (puedes mejorarlo con un diccionario predefinido)
    destinatarios = st.text_input("Correos destinatarios (separados por coma)", value="ejemplo@clinica.com")

    if st.button("📨 Enviar correo"):
        asunto = f"Actualización de Documento - {st.session_state['datos'].get('documento', 'Sin título')}"
        cuerpo = f"""
        Buen día,

        Cordial saludo.

        El formato está disponible en la plataforma IT SOLUTION y pueden consultarse siguiendo esta ruta:
        Gestión Documental → Consultar Documentos → (Seleccionar empresa) → Filtrar por nombre o código.

        Para acceder, puede ingresar a través del siguiente enlace:
        http://190.131.206.250:8085/ItSolution/index.jsp

        Cordialmente,
        """
        # Aquí llamas a la función de envío (necesitas configurar credenciales)
        # Por ahora simulamos el envío
        # enviar_correo(destinatarios.split(","), asunto, cuerpo, st.session_state["imagen"])
        st.success("✅ Correo enviado (simulado). Para envío real, configura SMTP en el código.")
