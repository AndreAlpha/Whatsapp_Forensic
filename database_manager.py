import sqlite3
import os
from tkinter import messagebox
import re

class DatabaseManager:
    """Gestisce tutte le interazioni con il database SQLite di WhatsApp."""
    def __init__(self, db_path):
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"Il file del database non è stato trovato: {db_path}")
        self.db_path = db_path

    def _connect_db(self):
        try:
            return sqlite3.connect(f"file:{self.db_path}?mode=ro", uri=True)
        except sqlite3.Error as e:
            messagebox.showerror("Errore Database", f"Impossibile connettersi al database:\n{e}")
            return None

    def _fetch_data(self, query, params=None):
        conn = self._connect_db()
        if conn is None: return []
        try:
            cursor = conn.cursor()
            cursor.execute(query, params or [])
            return cursor.fetchall()
        except sqlite3.Error as e:
            messagebox.showerror("Errore Query SQL", f"Errore durante l'esecuzione della query:\n{e}")
            return []
        finally:
            if conn: conn.close()

    def get_messages_for_clustering(self, limit=1000):
        """Recupera messaggi testuali significativi per l'analisi di clustering."""
        query = """
            SELECT
                m.text_data
            FROM message m
            WHERE m.text_data IS NOT NULL
              AND LENGTH(TRIM(m.text_data)) > 25
              AND m.message_type = 0
            LIMIT ?;
        """
        return self._fetch_data(query, (limit,))

    def get_deleted_messages(self, number_filter=None):
        base_query = """
            SELECT
                CASE WHEN chat.subject IS NOT NULL THEN sender_jid.user ELSE chat_jid.user END,
                chat.subject, message.timestamp, message_revoked.revoke_timestamp, message.from_me
            FROM message_revoked
            JOIN message ON message._id = message_revoked.message_row_id
            JOIN chat ON message.chat_row_id = chat._id
            JOIN jid AS chat_jid ON chat.jid_row_id = chat_jid._id
            LEFT JOIN jid AS sender_jid ON message.sender_jid_row_id = sender_jid._id
        """
        params = []
        if number_filter:
            base_query += " WHERE (chat_jid.user LIKE ? OR sender_jid.user LIKE ?)"
            params.extend([f"%{number_filter}%", f"%{number_filter}%"])
        
        # Corretto 'message_timestamp' con 'message.timestamp' che è il nome di colonna valido.
        base_query += " ORDER BY message.timestamp DESC;"
        return self._fetch_data(base_query, tuple(params))

    def get_summary_stats(self):
        query_messages = "SELECT COUNT(*) FROM message;"
        query_chats = "SELECT COUNT(*) FROM chat;"
        query_date_range = "SELECT MIN(timestamp), MAX(timestamp) FROM message WHERE timestamp > 0;"
        total_messages = self._fetch_data(query_messages)[0][0] or 0
        total_chats = self._fetch_data(query_chats)[0][0] or 0
        date_range = self._fetch_data(query_date_range)
        start_ts, end_ts = (None, None)
        if date_range and date_range[0]:
            start_ts, end_ts = date_range[0]
        return {"total_messages": total_messages, "total_chats": total_chats, "start_date": start_ts, "end_date": end_ts}

    def get_active_chats(self, limit=10):
        query = """
            SELECT
                CASE WHEN chat.subject IS NOT NULL THEN chat.subject ELSE jid.user END,
                COUNT(message._id)
            FROM chat
            JOIN jid ON chat.jid_row_id = jid._id
            JOIN message ON chat._id = message.chat_row_id
            GROUP BY 1 ORDER BY 2 DESC LIMIT ?;
        """
        return self._fetch_data(query, (limit,))

    def get_recent_chats(self, limit=20):
        query = """
            SELECT CASE WHEN c.subject IS NOT NULL THEN c.subject ELSE j.user END, MAX(m.timestamp)
            FROM chat c JOIN jid j ON c.jid_row_id = j._id JOIN message m ON c._id = m.chat_row_id
            GROUP BY 1 ORDER BY 2 DESC LIMIT ?;
        """
        return self._fetch_data(query, (limit,))

    def get_ephemeral_chats(self):
        query = """
            SELECT j.user, c.subject, c.ephemeral_expiration
            FROM chat c JOIN jid j ON c.jid_row_id = j._id WHERE c.ephemeral_expiration > 0
        """
        return self._fetch_data(query)

    def get_all_text_messages(self):
        query = "SELECT text_data FROM message WHERE text_data IS NOT NULL;"
        return self._fetch_data(query)

    def get_text_for_sentiment(self):
        query = """
            SELECT text_data FROM message
            WHERE message_type = 0 AND LENGTH(TRIM(text_data)) > 10 AND text_data NOT LIKE '%<omit%'
        """
        return self._fetch_data(query)

    def search_messages_by_word(self, word):
        query = """
            SELECT m.text_data, m.timestamp, m.from_me, s.user, r.user, c.subject
            FROM message AS m
            LEFT JOIN chat c ON m.chat_row_id = c._id
            LEFT JOIN jid s ON m.sender_jid_row_id = s._id
            LEFT JOIN jid r ON c.jid_row_id = r._id
            WHERE m.text_data LIKE ? ORDER BY m.timestamp DESC LIMIT 100;
        """
        return self._fetch_data(query, (f"%{word}%",))

    def search_onetime_messages(self, number):
        query = """
            SELECT
                CASE WHEN c.subject IS NOT NULL THEN s.user ELSE r.user END, c.subject,
                m.received_timestamp, m.text_data, m.message_type, m.from_me
            FROM message m
            JOIN chat c ON m.chat_row_id = c._id
            JOIN jid r ON c.jid_row_id = r._id
            LEFT JOIN jid s ON m.sender_jid_row_id = s._id
            WHERE (r.user LIKE ? OR s.user LIKE ?) AND m.message_type IN (42, 43, 82)
            ORDER BY m.received_timestamp DESC;
        """
        return self._fetch_data(query, (f"%{number}%", f"%{number}%"))

    def search_locations_by_number(self, number):
        query = """
            SELECT j.user, ml.place_name, ml.place_address, ml.latitude, ml.longitude, m.timestamp
            FROM message m
            JOIN message_location ml ON m._id = ml.message_row_id
            JOIN jid j ON m.sender_jid_row_id = j._id
            WHERE j.user LIKE ? ORDER BY m.timestamp DESC LIMIT 100;
        """
        return self._fetch_data(query, (f"%{number}%",))
        
    def search_latest_messages(self, search_key):
        is_phone = re.compile(r'^\+?\d{6,15}$').match(search_key)
        query = """
            SELECT
                CASE WHEN c.subject IS NOT NULL THEN s.user ELSE r.user END, c.subject,
                m.timestamp, m.text_data, m.from_me
            FROM message m
            JOIN chat c ON m.chat_row_id = c._id
            JOIN jid r ON c.jid_row_id = r._id
            LEFT JOIN jid s ON m.sender_jid_row_id = s._id
        """
        params = []
        if is_phone:
            query += " WHERE (r.user = ? OR s.user = ?)"
            params.extend([search_key, search_key])
        else:
            query += " WHERE c.subject LIKE ?"
            params.append(f"%{search_key}%")
        query += " ORDER BY m.timestamp DESC LIMIT 100"
        return self._fetch_data(query, tuple(params))

    def get_media_analysis_data(self):
        query = """
            SELECT mime_type, ROUND(AVG(CASE WHEN media_duration > 0 THEN media_duration END), 2), COUNT(*)
            FROM message_media WHERE mime_type IS NOT NULL GROUP BY 1 HAVING COUNT(*) > 5 ORDER BY 3 DESC;
        """
        return self._fetch_data(query)

    def get_message_timestamps(self):
        query = "SELECT timestamp FROM message WHERE timestamp IS NOT NULL"
        return self._fetch_data(query)
