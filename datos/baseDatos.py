# datos/baseDatos.py

import logging
import sqlite3

# El logger se define UNA VEZ para todo el archivo.
logger = logging.getLogger(__name__)

# --- FUNCIÓN 1 ---
def setup_database():
    """Configura las tablas de la base de datos si no existen."""
    conn = None
    try:
        # Asumiendo que db.db está en la carpeta raíz 'InfluencerAI'
        # Si está en 'datos', la ruta sería 'datos/db.db'
        conn = sqlite3.connect('db.db')
        cursor = conn.cursor()

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id INTEGER UNIQUE NOT NULL,
                name TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        logger.info("Tabla 'users' verificada/creada con éxito.")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS conversation_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_telegram_id INTEGER NOT NULL,
                sender_type TEXT NOT NULL,
                message_content TEXT NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_telegram_id) REFERENCES users (telegram_id)
            )
        ''')
        logger.info("Tabla 'conversation_history' verificada/creada con éxito.")
        conn.commit()

    except sqlite3.Error as e:
        logger.error(f"Error en la configuración de la base de datos: {e}")
    finally:
        if conn:
            conn.close()


# --- FUNCIÓN 2 ---
# <<< CORRECCIÓN: 'def' debe estar al principio, sin indentación.
def log_database_status():
    """Muestra un resumen del contenido de la base de datos en los logs."""
    conn = None
    logger.info("--- REPORTE DE ESTADO DE LA BASE DE DATOS ---")

    try:
        # La ruta debe ser la misma que en setup_database()
        conn = sqlite3.connect('db.db')
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # Reporte de Usuarios
        cursor.execute("SELECT * FROM users ORDER BY id DESC LIMIT 5")
        users = cursor.fetchall()
        if not users:
            logger.info("-> Tabla 'users': No hay usuarios registrados.")
        else:
            logger.info(f"-> {len(cursor.execute('SELECT id FROM users').fetchall())} usuarios totales. Los 5 más recientes:")
            for user in users:
                logger.info(f"  - ID: {user['telegram_id']}, Nombre: {user['name']}")

        # Reporte de Historial
        cursor.execute("SELECT * FROM conversation_history ORDER BY id DESC LIMIT 10")
        messages = cursor.fetchall()
        if not messages:
            logger.info("-> Tabla 'conversation_history': No hay mensajes registrados.")
        else:
            logger.info(f"-> {len(cursor.execute('SELECT id FROM conversation_history').fetchall())} mensajes totales. Los 10 más recientes:")
            for msg in reversed(messages):
                content_preview = (msg['message_content'][:70] + '...') if len(msg['message_content']) > 70 else msg['message_content']
                logger.info(f"  - [{msg['sender_type']}] para ({msg['user_telegram_id']}): {content_preview}")

    except sqlite3.Error as e:
        logger.error(f"No se pudo leer el estado de la base de datos: {e}")
    finally:
        if conn:
            conn.close()
        logger.info("--- FIN DEL REPORTE ---")