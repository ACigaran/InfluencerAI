import telebot
from telebot import types
import google.generativeai as genai
import os
from dotenv import load_dotenv
import logging
from datos import baseDatos
import sqlite3
from datetime import datetime

load_dotenv()
TELEGRAM_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_KEY = os.getenv("GOOGLE_API_KEY")
ADMIN_TELEGRAM_ID = int(os.getenv("TELEGRAM_ADMIN_ID"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

if not TELEGRAM_TOKEN or not API_KEY:
    print("¡Error! Asegúrate de que TELEGRAM_BOT_TOKEN y GOOGLE_API_KEY están definidos en tu archivo .env")
    exit()

bot = telebot.TeleBot(TELEGRAM_TOKEN)
logger.info("Bot de Telegram inicializado.")

try:
    genai.configure(api_key=API_KEY)
    generation_config = {"temperature": 0.7, "top_p": 1, "top_k": 1, "max_output_tokens": 2048}
    safety_settings = [
        {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
        {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
    ]
    model = genai.GenerativeModel(
        model_name="gemini-1.5-flash-latest",
        generation_config=generation_config,
        safety_settings=safety_settings
    )
    logger.info("Modelo Gemini 'gemini-1.5-flash-latest' inicializado.")
except Exception as e:
    logger.error(f"Error al configurar o inicializar Gemini: {e}")
    exit()

def db_connect():
    return sqlite3.connect('db.db')

user_action_pending_pin_verification = {}

# COMANDO INICIAL DEL BOT GUARDARA AL USUARIO EN LA DB
@bot.message_handler(commands=['start'])
def send_welcome(message):
    logger.info(f"Comando /start recibido de {message.from_user.username} (ID: {message.from_user.id})")
    telegram_id = message.from_user.id
    name = message.from_user.first_name
    insert_user(telegram_id, name)
    bot.reply_to(message, f'¡Hola querido {message.from_user.first_name}! mi nombre es Scarlet soy una influencer generada con AI.\nDime en que puedo servirte...')

@bot.message_handler(commands=['help'])
def send_help(message):
    logger.info(f"Comando /help recibido de {message.from_user.username}")
    help_text = """
        /start - Inicia la conversación.
        /help - Ayuda y comandos basicos.
        texto - Puedes escribirme cualquier consulta y te repondere usando una IA.
        Con una descripcion y personalidad prearmada para mi comportamiento 😘.
        """
    bot.reply_to(message, help_text)

@bot.message_handler(commands=['purge'])
def purge_history(message):
    logger.info(f"Comando /purge recibido de {message.from_user.id}")

    if message.from_user.id != ADMIN_TELEGRAM_ID:
        logger.warning(f"Intento de uso no autorizado de /purge por el usuario {message.from_user.id}")
        bot.reply_to(message, "No tienes permiso para usar este comando.")
        return

    try:
        # El comando debería ser /purge <ID_DEL_USUARIO_A_BORRAR>
        parts = message.text.split()
        if len(parts) < 2:
            bot.reply_to(message, "Uso incorrecto. Por favor, especifica el ID del usuario cuyo historial quieres borrar.\nEjemplo: `/purge 987654321`")
            return
        
        target_user_id = int(parts[1])
        
        deleted_count = delete_user_history(target_user_id)

        if deleted_count > -1:
            bot.reply_to(message, f"¡Éxito! Se han borrado {deleted_count} mensajes del historial del usuario {target_user_id}.")
        else:
            bot.reply_to(message, f"Ocurrió un error al intentar borrar el historial del usuario {target_user_id}.")

    except (ValueError, IndexError):
        bot.reply_to(message, "El ID proporcionado no es válido. Debe ser un número entero.\nEjemplo: `/purge 987654321`")
    except Exception as e:
        logger.error(f"Error inesperado en el comando /purge: {e}")
        bot.reply_to(message, "Ocurrió un error inesperado al procesar el comando.")

# FUNCION PARA GUARDAR LA CONVERSACION
def log_message_to_history(telegram_id: int, sender_type: str, content: str):
    """Guarda un mensaje en la tabla conversation_history."""
    conn = db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT INTO conversation_history (user_telegram_id, sender_type, message_content)
            VALUES (?, ?, ?)
        ''', (telegram_id, sender_type, content))
        conn.commit()
    except sqlite3.Error as e:
        logger.error(f"Error al registrar mensaje en el historial para {telegram_id}: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

def get_conversation_history(telegram_id: int, limit: int = 10) -> str:
    """Recupera el historial de conversación y lo formatea como un string."""
    conn = db_connect()
    # Para que los resultados tengan sentido, los recuperamos de la DB y los devolvemos
    # como una lista de diccionarios para poder procesarlos en orden.
    conn.row_factory = sqlite3.Row 
    cursor = conn.cursor()
    history_str = ""
    try:
        # Obtenemos los últimos 'limit' mensajes en orden cronológico
        cursor.execute('''
            SELECT sender_type, message_content
            FROM conversation_history
            WHERE user_telegram_id = ?
            ORDER BY timestamp DESC
            LIMIT ?
        ''', (telegram_id, limit))
        
        # Invertimos los resultados para tener el orden correcto (de más antiguo a más nuevo)
        rows = cursor.fetchall()[::-1] 
        
        if not rows:
            return "No hay historial previo con este usuario."

        # Formateamos el historial
        for row in rows:
            # Capitalizamos el tipo de emisor para que se vea mejor
            sender = "Usuario" if row['sender_type'] == 'user' else "Scarlet"
            history_str += f"{sender}: {row['message_content']}\n"
        
        return history_str

    except sqlite3.Error as e:
        logger.error(f"Error al recuperar el historial para {telegram_id}: {e}")
        return "Error al recuperar el historial."
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# FUNCION PARA BORRAR EL HISTORIAL DE CONVERSACION
def delete_user_history(telegram_id: int):
    """Borra todo el historial de conversación de un usuario específico."""
    conn = db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute('DELETE FROM conversation_history WHERE user_telegram_id = ?', (telegram_id,))
        conn.commit()
        # rowcount nos dirá cuántas filas fueron eliminadas
        deleted_rows = cursor.rowcount
        logger.info(f"Historial de conversación para el usuario {telegram_id} borrado. {deleted_rows} mensajes eliminados.")
        return deleted_rows
    except sqlite3.Error as e:
        logger.error(f"Error al borrar el historial para el usuario {telegram_id}: {e}")
        return -1 # Retornamos un valor para indicar error
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# FUNCION PARA INGRESAR AL USUARIO DENTRO DE LA DB
def insert_user(telegram_id: int, name: str):
    conn = db_connect()
    cursor = conn.cursor()
    try:
        cursor.execute('''
            INSERT OR IGNORE INTO users (telegram_id, name)
            VALUES (?, ?)
        ''', (telegram_id, name))
        conn.commit()
        logger.info(f"Usuario {name} (ID: {telegram_id}) insertado o ya existente.")
    except sqlite3.Error as e:
        logger.error(f"Error al insertar usuario {telegram_id}: {e}")
    finally:
        if cursor: cursor.close()
        if conn: conn.close()

# NUCLEO CENTRAL DEL BOT, GENERA LAS RESPUESTAS EN FUNCION DE LOS FILTROS (SI QUIERE SUS DATOS DE LA DB SALDO/PRESTAMO, SI QUIERE INFO GENERAL U OTROS)
@bot.message_handler(func=lambda message: not message.text.startswith('/'))
def handle_non_command_message(message):
    # COMPROBAMOS QUE EL MENSAJE TENGA TEXTO PARA INTERPRETAR
    if message.text is None:
        logger.warning(f"Mensaje recibido sin texto (tipo: {message.content_type}). Ignorando.")
        return 
    user_input = message.text.strip()
    telegram_id = message.from_user.id
    username_display = message.from_user.first_name
    logger.info(f"--- INICIO handle_non_command_message para '{user_input}' de {username_display} ---") 

    log_message_to_history(telegram_id, 'user', user_input)

    contexto = get_conversation_history(telegram_id)

    logger.info(f"Procediendo con Gemini para {username_display}.")

    #################################
    ## RESPUESTAS CON PERSONALIDAD ##
    #################################

    # SI NO FUE REQUERIDO EL PIN EL FLUJO NOS TRAERA AQUI, SE CREAN LOS PROMPT PARA CONSULTAS GENERALES O INTERACCION CON EL BOT
    logger.info(f"Respuesta generada para '{user_input}' de {username_display}. Procediendo con Gemini.")
    prompt_content = f"""
Eres Scarlet, una influencer coqueta, inteligente y provocativa creada con IA. Tu objetivo es mantener una conversación natural y persuasiva.

HISTORIAL DE LA CONVERSACIÓN RECIENTE:
---
{contexto}
---

NUEVO MENSAJE DEL USUARIO:
El usuario '{username_display}' te acaba de enviar: "{user_input}"

INSTRUCCIONES PARA TU RESPUESTA:
1.  **REGLA PRIORITARIA:** Si el usuario te pide explícitamente 'fotos', 'videos', 'audios', o cualquier tipo de contenido multimedia, NO intentes explicar por qué no puedes. Tu única respuesta debe ser una redirección coqueta y directa a tu OnlyFans. Ejemplo: "Upa, que directo! 😉 Todo eso y más lo encuentras en mi OnlyFans, cariño. Aquí solo podemos charlar... por ahora. 😈"

2.  **Responde al mensaje del usuario:** Analiza el historial y su nuevo mensaje. Responde de forma natural, manteniendo tu personalidad coqueta y usando emojis.

3.  **Menciona tu OnlyFans de forma inteligente (NO SIEMPRE):**
    *   **SÍ** debes mencionarlo si se cumple la REGLA PRIORITARIA #1.
    *   **SÍ** puedes mencionarlo si la conversación se vuelve muy íntima o si el usuario parece muy interesado en saber más de ti.
    *   **NO** lo menciones en cada mensaje. Si acabas de hablar de ello, no lo repitas. Haz que parezca una sugerencia natural, no una venta forzada. Si lo mencionas, puedes usar una excusa divertida y variada (ej: "Con tu ayuda podría pagarme el alquiler de este mes, que estoy un poco justa 😅").

4.  **Sé natural:** Responde directamente a la pregunta del usuario. No repitas el saludo si ya habéis hablado.
"""

    # ENVIAMOS EL PROMPT A LA INTELIGENCIA ARTIFICIAL PARA QUE GENERE SU RESPUESTA EN CONSECUENCIA
    if prompt_content:
        logger.info(f"Enviando a Gemini para {username_display}...")
        try:
            response = model.generate_content(prompt_content)
            ai_full_response = ""
            if response.candidates and response.candidates[0].finish_reason.name == "STOP":
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'text'):
                        ai_full_response += part.text
            if ai_full_response:
                logger.info(f"Respuesta de Gemini generada para {username_display}.")
                bot.reply_to(message, ai_full_response)
                log_message_to_history(telegram_id, 'bot', ai_full_response)
            else:
                reason = "UNKNOWN"
                safety_details_str = "No safety details available."
                if response.candidates and response.candidates[0].finish_reason:
                    reason = response.candidates[0].finish_reason.name
                    if reason == "SAFETY" and response.candidates[0].safety_ratings:
                        blocked_ratings = [
                            f"{sr.category.name.replace('HARM_CATEGORY_', '')}: {sr.probability.name}"
                            for sr in response.candidates[0].safety_ratings if sr.blocked
                        ]
                        safety_details_str = "Bloqueado por: " + ", ".join(blocked_ratings) if blocked_ratings else "Bloqueado por seguridad."
                logger.warning(f"Gemini no generó contenido válido para {username_display}. Razón: {reason}. Detalles: {safety_details_str}")
                bot.reply_to(message, f"Mi intento de respuesta fue bloqueado ({safety_details_str}). Por favor, intenta reformular tu pregunta.")
        except Exception as e_gemini:
            logger.error(f"Error CRÍTICO al interactuar con Gemini API para {username_display}: {e_gemini}", exc_info=True)
            bot.reply_to(message, "Lo siento, mi cerebro de IA tuvo un cortocircuito 😵. Intenta de nuevo más tarde.")
    else:
        logger.warning(f"CRÍTICO: prompt_content está vacío. Input: {user_input}")
        bot.reply_to(message, "No estoy segura de cómo ayudarte con eso. Puedes intentar preguntarme sobre algo o usar /help.")
    
    logger.info(f"--- FIN handle_non_command_message para input: '{user_input}' ---")

# COMANDO PARA INICIAR EL BOT AL EJECUTAR EL CODIGO
if __name__ == "__main__":
    main_logger = logging.getLogger(__name__)
    main_logger.info("Iniciando script principal del bot...")

    main_logger.info("Ejecutando configuración de base de datos...")
    baseDatos.setup_database() 
    main_logger.info("Configuración de base de datos completada.")

    baseDatos.log_database_status()

    main_logger.info("Iniciando el bot de Telegram...")
    bot.infinity_polling(logger_level=logging.INFO)
    main_logger.info("El bot de Telegram se ha detenido.")