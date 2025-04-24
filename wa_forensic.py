import sqlite3, datetime, os, webbrowser, folium, re, warnings, argparse
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
import matplotlib.dates as mdates
from collections import Counter
from wordcloud import WordCloud
from tkinter import Tk, Frame, Label
from tkinter import ttk, Toplevel, Listbox, Scrollbar
from textblob import TextBlob
from datetime import datetime
from datetime import timedelta

warnings.filterwarnings("ignore", category=UserWarning)

parser = argparse.ArgumentParser(description='Strumento di analisi forense per database whatsapp android')
parser.add_argument('--db-path', required=True, help='Percorso del database SQLite da analizzare')
args = parser.parse_args()
db_path = args.db_path


# FUNZIONI BASE

# Funzione per connettersi al database (rimane invariata)
def connect_db():
    try:
        return sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        print(f"Errore durante la connessione al database: {e}")
        return None


# Funzione per eseguire query SQL (rimane invariata)
def fetch_data(query, params=None):
    conn = connect_db()
    if conn is None:
        return []
    cursor = conn.cursor()
    try:
        if params:
            cursor.execute(query, params)
        else:
            cursor.execute(query)
        data = cursor.fetchall()
    except sqlite3.Error as e:
        print(f"Errore durante l'esecuzione della query: {e}")
        data = []
    finally:
        conn.close()
    return data


# Funzione per visualizzare il grafico all'interno della GUI
def show_plot(plot_func):
    plt.close('all')  # Chiude tutte le figure precedenti
    fig = plt.figure(figsize=(8, 6))  # Crea UNA figura
    try:
        plot_func(fig)  # Passa la figura alla funzione
        plt.tight_layout()
        plt.show()
    except Exception as e:
        plt.close()
        print(f"Errore durante il plotting: {str(e)}")


# SEZIONE ANALISI CHAT

# Funzione per ottenere le chat più attive con il numero di telefono o nome del gruppo
def get_active_chats():
    query = """
        SELECT 
            CASE 
                WHEN chat.subject IS NOT NULL THEN chat.subject 
                ELSE jid.user 
            END AS chat_identifier, 
            COUNT(message._id) AS message_count
        FROM chat
        JOIN jid ON chat.jid_row_id = jid._id
        JOIN message ON chat._id = message.chat_row_id
        GROUP BY chat_identifier
        ORDER BY message_count DESC
        LIMIT 10;
    """
    data = fetch_data(query)
    chat_identifiers, message_counts = zip(*data) if data else ([], [])
    return chat_identifiers, message_counts

# Funzione per visualizzare le chat più attive
def plot_active_chats():
    def plot(fig):
        chat_ids, message_counts = get_active_chats()
        
        if not chat_ids:
            plt.title("Nessuna chat attiva trovata")
            return
            
        plt.barh(chat_ids, message_counts, color='lightcoral')
        plt.xlabel("Numero di messaggi")
        plt.ylabel("Chat")
        plt.title("Top 10 chat più attive")
    
    plt.close('all')
    fig = plt.figure(figsize=(10, 5))
    plot(fig)
    plt.tight_layout()
    plt.show()


# Funzione per ottenere le 20 chat più recenti
def get_recent_chats(limit=20):
    query = """
        SELECT 
            CASE 
                WHEN chat.subject IS NOT NULL THEN chat.subject 
                ELSE jid.user 
            END AS chat_identifier,
            MAX(message.timestamp) AS last_activity
        FROM chat
        JOIN jid ON chat.jid_row_id = jid._id
        JOIN message ON chat._id = message.chat_row_id
        GROUP BY chat_identifier
        ORDER BY last_activity DESC
        LIMIT ?;
    """
    data = fetch_data(query, (limit,))
    return [row[0] for row in data] if data else []

# Funzione per visualizzare le chat recenti
def show_recent_chats():
    chats = get_recent_chats()
    
    top = Toplevel()
    top.title("Ultime 10 chat attive")
    top.geometry("600x400")
    
    frame = Frame(top)
    frame.pack(fill="both", expand=True, padx=10, pady=10)
    
    Label(frame, text="Chat più recenti (per ultima attività):", font=('Arial', 10, 'bold')).pack(pady=5)
    
    listbox = Listbox(frame, width=80, height=15, font=('Consolas', 9))
    scrollbar = Scrollbar(frame, orient="vertical", command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    for i, chat in enumerate(chats, 1):
        listbox.insert("end", f"{i}. {chat}")
    
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    
# Funzione per ottenere i messaggi cancellati (senza testo)
def get_deleted_messages():
    query = """
        SELECT 
            CASE
                WHEN chat.subject IS NOT NULL 
                THEN sender_jid.user
                ELSE chat_jid.user
            END AS phone_number,  
            chat.subject AS group_name,
            message.timestamp AS message_timestamp,
            message_revoked.revoke_timestamp AS revoked_timestamp,
            message.from_me AS from_me
        FROM message_revoked
        INNER JOIN message 
            ON message._id = message_revoked.message_row_id
        INNER JOIN chat 
            ON message.chat_row_id = chat._id
        INNER JOIN jid AS chat_jid 
            ON chat.jid_row_id = chat_jid._id
        LEFT JOIN jid AS sender_jid 
            ON message.sender_jid_row_id = sender_jid._id
        ORDER BY message_timestamp DESC;
    """
    data = fetch_data(query)
    
    results = []
    for row in data:
        phone_number, group_name, message_timestamp, revoked_timestamp, from_me = row
        
        # Formattazione timestamp
        if isinstance(message_timestamp, (int, float)) and message_timestamp > 0:
            message_timestamp = datetime.fromtimestamp(message_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            message_timestamp = "Data non disponibile"
        if isinstance(revoked_timestamp, (int, float)) and revoked_timestamp > 0:
            revoked_timestamp = datetime.fromtimestamp(revoked_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            revoked_timestamp = "Data non disponibile"
            
        if from_me:
            results.append(
                f"DA: Questo numero | A: {phone_number} | "
                f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                f"DATA INVIO: {message_timestamp} | "
                f"DATA ELIMINAZIONE: {revoked_timestamp}"
            )
        else:
            results.append(
                f"DA: {phone_number} | A: Questo numero | "
                f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                f"DATA INVIO: {message_timestamp} | "
                f"DATA ELIMINAZIONE: {revoked_timestamp}"
            )
    
    return results
    
def show_deleted_messages():
    results = get_deleted_messages()
    
    top = Toplevel()
    top.title(f"Messaggi cancellati")
    top.protocol("WM_DELETE_WINDOW", top.destroy)  # Chiude correttamente la finestra
    
    listbox = Listbox(top, width=120, height=20, font=('Consolas', 8))
    scrollbar = Scrollbar(top, orient="vertical", command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    for result in results:
        listbox.insert("end", result)
    
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")


# Funzione per ottenere le chat con messaggi effimeri attivi
def get_ephemeral_chats():
    query = """
        SELECT
            chat_jid.user AS phone_number,
            chat.subject AS group_name,
            chat.ephemeral_expiration AS expiration
        FROM chat
        INNER JOIN jid AS chat_jid ON chat.jid_row_id = chat_jid._id
        WHERE expiration > 0
    """
    data = fetch_data(query)
    
    results = []
    for row in data:
        phone_number, group_name, expiration = row
        
        # Formattazione timestamp
        expiration = expiration / 60 / 60 / 24
        expiration_str = str(int(expiration))
        
        results.append(
            f"{'GRUPPO: ' + group_name + ' | ' if group_name else 'NUMERO: ' + phone_number + ' | '}"
            f"{'TIMER ELIMINAZIONE: ' + expiration_str + ' giorno' if expiration == 1 else 'TIMER ELIMINAZIONE: ' + expiration_str + ' giorni'}"
        )
    
        """ results.append(
            {phone_number, group_name, expiration}
        ) """
    return results
    
def show_ephemeral_chats():
    results = get_ephemeral_chats()
    
    top = Toplevel()
    top.title(f"Chat Effimere")
    top.protocol("WM_DELETE_WINDOW", top.destroy)  # Chiude correttamente la finestra
    
    listbox = Listbox(top, width=120, height=20, font=('Consolas', 8))
    scrollbar = Scrollbar(top, orient="vertical", command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    for result in results:
        listbox.insert("end", result)
    
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")


# SEZIONE ANALISI TESTUALE

# Funzione per ottenere le parole più usate (top 20)
def get_most_common_words():
    query = """
        SELECT message._id, message.text_data
        FROM message
        WHERE message.text_data IS NOT NULL;
    """
    data = fetch_data(query)
    words = " ".join(row[1] for row in data).split()
    word_counts = Counter(words).most_common(20)
    words, counts = zip(*word_counts) if word_counts else ([], [])
    return words, counts

# Funzione per visualizzare l'istogramma delle parole più usate
def plot_word_histogram():
    def plot(plot):
        words, counts = get_most_common_words()
        plt.barh(words, counts, color='skyblue')
        plt.xlabel("Frequenza")
        plt.ylabel("Parola")
        plt.title("Top 20 parole più utilizzate")
    show_plot(plot)


# Funzione per ottenere le parole più usate con almeno 4 lettere
def get_most_common_words_min_4_letters():
    query = """
        SELECT message._id, message.text_data
        FROM message
        WHERE message.text_data IS NOT NULL;
    """
    data = fetch_data(query)
    words = " ".join(row[1] for row in data).split()
    words = [word for word in words if len(word) >= 4]
    word_counts = Counter(words).most_common(20)
    words, counts = zip(*word_counts) if word_counts else ([], [])
    return words, counts

# Funzione per visualizzare l'istogramma delle parole più usate con almeno 4 lettere
def plot_word_histogram_min_4():
    def plot(plot):
        words, counts = get_most_common_words_min_4_letters()
        plt.barh(words, counts, color='lightgreen')
        plt.xlabel("Frequenza")
        plt.ylabel("Parola")
        plt.title("Top 20 parole più utilizzate (minimo 4 lettere)")
    show_plot(plot)


# Funzione per generare la WordCloud
def generate_wordcloud():
    query = """
        SELECT message._id, message.text_data
        FROM message
        WHERE message.text_data IS NOT NULL;
    """
    data = fetch_data(query)
    text = " ".join(row[1] for row in data)
    
    # Elaborazione del testo per calcolare le frequenze
    words = text.lower().split()
    words = [word.strip('.,!?()[]{}"\'') for word in words]  # Rimuove punteggiatura
    words = [word for word in words if len(word) >= 4]       # Filtra parole brevi
    
    word_counts = Counter(words)
    
    # Genera la WordCloud dalle frequenze
    wordcloud = WordCloud(
        width=800,
        height=400,
        background_color='white',
        relative_scaling=0.6    # Controlla la gradazione delle dimensioni (0-1)
    ).generate_from_frequencies(word_counts)
    
    return wordcloud

# Funzione per visualizzare la WordCloud
def plot_wordcloud():
    wordcloud = generate_wordcloud()
    plt.figure(figsize=(8, 6))
    plt.imshow(wordcloud, interpolation='bilinear')
    plt.axis("off")
    plt.title("WordCloud delle parole più usate")
    plt.show()


# Funzione pulizia testo per sentiment
def clean_text(text):
    try:
        if not text:
            return ''
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\b\w{1,3}\b', '', text)
        text = re.sub(r'[\U0001F600-\U0001F64F]', '', text)
        return text.strip().lower()
    except:
        return ''

# Funzione aggiuntiva per analisi sentiment (esempio)
def plot_sentiment():
    def plot(fig):
        data = fetch_data("""
            SELECT text_data 
            FROM message 
            WHERE 
                message_type = 0 AND
                LENGTH(TRIM(text_data)) > 3 AND
                text_data NOT LIKE '%<omit%'
        """)
        
        if not data:
            plt.title("Nessun testo valido per l'analisi")
            return
        
        sentiments = []
        batch_size = 100  # Analizza in batch per migliorare le prestazioni
        for i in range(0, len(data), batch_size):
            batch = data[i:i+batch_size]
            sentiments += [TextBlob(clean_text(row[0])).sentiment.polarity for row in batch]

        ax = fig.add_subplot(111)
        fig.set_size_inches(8, 4)
        plt.hist(sentiments, bins=20, color='purple', alpha=0.7)
        ax.set_title('Distribuzione Sentiment')
        ax.set_xlabel('Polarità (-1 negativo ~ 1 positivo)')
        ax.set_ylabel('Frequenza')
    
    show_plot(plot)


# SEZIONE RICERCHE

# Funzione per la ricerca messaggi per testo
def search_word_in_messages(word):
    query = """
        SELECT 
            msg.text_data,
            msg.timestamp,
            msg.from_me,
            sender_jid.user AS sender_number,
            receiver_jid.user AS receiver_number,
            chat.subject AS group_name
        FROM message AS msg
        LEFT JOIN chat ON msg.chat_row_id = chat._id
        LEFT JOIN jid AS sender_jid 
            ON (CASE WHEN chat.subject IS NOT NULL 
                    THEN msg.sender_jid_row_id 
                    ELSE chat.jid_row_id END) = sender_jid._id
        LEFT JOIN jid AS receiver_jid ON chat.jid_row_id = receiver_jid._id
        WHERE msg.text_data LIKE ?
        ORDER BY msg.timestamp DESC
        LIMIT 100;
    """
    data = fetch_data(query, (f"%{word}%",))
    
    results = []
    for row in data:
        text_data, timestamp, from_me, sender_number, receiver_number, group_name = row
        
        # Formattazione timestamp
        if isinstance(timestamp, (int, float)) and timestamp > 0:
            timestamp = datetime.fromtimestamp(timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            timestamp = "Data non disponibile"

        # Gestione numeri
        sender_number = sender_number or "Numero sconosciuto"
        receiver_number = receiver_number or "Numero sconosciuto"
        
        if group_name:  # Messaggio di gruppo
            results.append(f"DA: {sender_number} A: {group_name} DATA: {timestamp} MESSAGGIO: {text_data}")
        else:           # Messaggio privato
            if from_me == 1:
                results.append(f"DA: Questo numero A: {receiver_number} DATA: {timestamp} MESSAGGIO: {text_data}")
            else:
                results.append(f"DA: {sender_number} A: Questo numero DATA: {timestamp} MESSAGGIO: {text_data}")
    
    return results

# Funzione per mostrare i risultati della ricerca del testo
def show_search_results(word):
    results = search_word_in_messages(word)
    
    top = Toplevel()
    top.title(f"Risultati ricerca: '{word}'")
    top.protocol("WM_DELETE_WINDOW", top.destroy)  # Chiude correttamente la finestra
    
    listbox = Listbox(top, width=120, height=20, font=('Consolas', 8))
    scrollbar = Scrollbar(top, orient="vertical", command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    for result in results:
        listbox.insert("end", result)
    
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")
    

# Funzione per la ricerca messaggi cancellati per numero
def search_deleted_messages(number):
    query = """
        SELECT 
            CASE
                WHEN chat.subject IS NOT NULL 
                THEN sender_jid.user
                ELSE chat_jid.user
            END AS phone_number,  
            chat.subject AS group_name,
            message.timestamp AS message_timestamp,
            message_revoked.revoke_timestamp AS revoked_timestamp,
            message.from_me AS from_me
        FROM message_revoked
        INNER JOIN message 
            ON message._id = message_revoked.message_row_id
        INNER JOIN chat 
            ON message.chat_row_id = chat._id
        INNER JOIN jid AS chat_jid 
            ON chat.jid_row_id = chat_jid._id
        LEFT JOIN jid AS sender_jid 
            ON message.sender_jid_row_id = sender_jid._id
        WHERE phone_number = ?
        ORDER BY message_timestamp DESC;
    """
    data = fetch_data(query, (f"{number}",))
    
    results_cancellati = []
    for row in data:
        phone_number, group_name, message_timestamp, revoked_timestamp, from_me = row
        
        # Formattazione timestamp
        if isinstance(message_timestamp, (int, float)) and message_timestamp > 0:
            message_timestamp = datetime.fromtimestamp(message_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            message_timestamp = "Data non disponibile"
        if isinstance(revoked_timestamp, (int, float)) and revoked_timestamp > 0:
            revoked_timestamp = datetime.fromtimestamp(revoked_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            revoked_timestamp = "Data non disponibile"
        
        if from_me:
            results_cancellati.append(
                f"DA: Questo numero | A: {phone_number} | "
                f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                f"DATA INVIO: {message_timestamp} | "
                f"DATA ELIMINAZIONE: {revoked_timestamp}"
            )
        else:
            results_cancellati.append(
                f"DA: {phone_number} | A: Questo numero | "
                f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                f"DATA INVIO: {message_timestamp} | "
                f"DATA ELIMINAZIONE: {revoked_timestamp}"
            )
    
    return results_cancellati

# Funzione per mostrare i risultati della ricerca dei messaggi cancellati per numero
def show_search_deleted(number):
    results_cancellati = search_deleted_messages(number)
    
    top = Toplevel()
    top.title(f"Risultati ricerca: '{number}'")
    top.protocol("WM_DELETE_WINDOW", top.destroy)  # Chiude correttamente la finestra
    
    listbox = Listbox(top, width=120, height=20, font=('Consolas', 8))
    scrollbar = Scrollbar(top, orient="vertical", command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    for result in results_cancellati:
        listbox.insert("end", result)
    
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")


# Funzione per la ricerca messaggi visualizzabili solo una volta
def search_onetime_messages(number):
    query = """
        SELECT
            CASE
                WHEN chat.subject IS NOT NULL 
                THEN sender_jid.user
                ELSE chat_jid.user
            END AS number,
            chat.subject AS group_name,
            message.received_timestamp AS message_timestamp, 
            message.text_data AS text_data, 
            message.message_type AS type,
            message.from_me AS from_me
        FROM message 
        INNER JOIN chat ON message.chat_row_id = chat._id
        INNER JOIN jid AS chat_jid ON chat.jid_row_id = chat_jid._id
        LEFT JOIN jid AS sender_jid ON message.sender_jid_row_id = sender_jid._id
        WHERE number = ? AND message.message_type IN (42, 43, 82)
        ORDER BY message.received_timestamp DESC
    """
    data = fetch_data(query, (f"{number}",))
    
    results_onetime = []
    for row in data:
        number, group_name, message_timestamp, text_data, type, from_me = row

        # Formattazione timestamp
        if isinstance(message_timestamp, (int, float)) and message_timestamp > 0:
            message_timestamp = datetime.fromtimestamp(message_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            message_timestamp = "Data non disponibile"
        
        if text_data:
            if type == 42:
                results_onetime.append(
                    f"{'DA: Questo numero | A: ' + number + ' | ' if from_me else 'DA: ' + number + ' | A: Questo numero | '}"
                    f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                    f"DATA INVIO: {message_timestamp} | DIDASCALIA: {text_data} | TIPO: IMMAGINE"
                )
            elif type == 43:
                results_onetime.append(
                    f"{'DA: Questo numero | A: ' + number + ' | ' if from_me else 'DA: ' + number + ' | A: Questo numero | '}"
                    f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                    f"DATA INVIO: {message_timestamp} | DIDASCALIA: {text_data} | TIPO: VIDEO"
                )
            elif type == 82:
                results_onetime.append(
                    f"{'DA: Questo numero | A: ' + number + ' | ' if from_me else 'DA: ' + number + ' | A: Questo numero | '}"
                    f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                    f"DATA INVIO: {message_timestamp} | DIDASCALIA: {text_data} | TIPO: AUDIO"
                )
        else:
            if type == 42:
                results_onetime.append(
                    f"{'DA: Questo numero | A: ' + number + ' | ' if from_me else 'DA: ' + number + ' | A: Questo numero | '}"
                    f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                    f"DATA INVIO: {message_timestamp} | TIPO: IMMAGINE"
                )
            elif type == 43:
                results_onetime.append(
                    f"{'DA: Questo numero | A: ' + number + ' | ' if from_me else 'DA: ' + number + ' | A: Questo numero | '}"
                    f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                    f"DATA INVIO: {message_timestamp} | TIPO: VIDEO"
                )
            elif type == 82:
                results_onetime.append(
                    f"{'DA: Questo numero | A: ' + number + ' | ' if from_me else 'DA: ' + number + ' | A: Questo numero | '}"
                    f"{'GRUPPO: ' + group_name + ' | ' if group_name else ''}"
                    f"DATA INVIO: {message_timestamp} | TIPO: AUDIO"
                )

    return results_onetime

# Funzione per mostrare i risultati della ricerca dei messaggi visualizzabili solo una volta
def show_search_onetime(number):
    results_onetime = search_onetime_messages(number)
    
    top = Toplevel()
    top.title(f"Risultati ricerca: '{number}'")
    top.protocol("WM_DELETE_WINDOW", top.destroy)  # Chiude correttamente la finestra
    
    listbox = Listbox(top, width=120, height=20, font=('Consolas', 8))
    scrollbar = Scrollbar(top, orient="vertical", command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    for result in results_onetime:
        listbox.insert("end", result)
    
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")


# Funzione per la ricerca delle localizzazioni
def search_location_by_number(number):
    query = """
        SELECT
            jid.user AS sender_number, 
            message_location.place_name, 
            message_location.place_address, 
            message_location.latitude, 
            message_location.longitude
        FROM message
        JOIN message_location
            ON message._id = message_location.message_row_id
            OR message.chat_row_id = message_location.chat_row_id 
        JOIN jid ON message.sender_jid_row_id = jid._id
        WHERE jid.user LIKE ?
        ORDER BY message.timestamp DESC
        LIMIT 100;
    """
    data = fetch_data(query, (f"%{number}%",))
    
    results = []
    for row in data:
        sender, name, addr, lat, lon = row

        result = {
            "sender": sender,
            "place": name if name else "Sconosciuto",
            "address": addr if addr else "Sconosciuto",
            "latitude": lat,
            "longitude": lon,
        }
        results.append(result)
    
    return results

# Funzione per mostrare le posizioni sulla mappa
def show_location_map(number):
    data = search_location_by_number(number)

    if not data:
        print("Nessuna posizione trovata per questo numero.")
        return
    
    # Creazione della mappa
    map_ = folium.Map(location=[data[0]["latitude"], data[0]["longitude"]], zoom_start=12)

    # Aggiunta dei marker con la data e ora corretta
    for location in data:
        popup_content = f"""
            <div style="min-width:220px">
                <b>Luogo:</b> {location["place"]}<br>
                <b>Indirizzo:</b> {location["address"]}<br>
                <b>Lat:</b> {location["latitude"]:.6f}<br>
                <b>Lon:</b> {location["longitude"]:.6f}<br>
            </div>
        """
        folium.Marker(
            [location["latitude"], location["longitude"]],
            popup=folium.Popup(popup_content, max_width=250),
            icon=folium.Icon(color="blue", icon="map-marker")
        ).add_to(map_)

    # Salvataggio e apertura della mappa
    map_filename = "mappa_posizioni.html"
    map_.save(map_filename)
    webbrowser.open(f'file://{os.path.realpath(map_filename)}')









# Funzione per la ricerca degli ultimi messaggi
def search_latest_messages(search_key):
    """
    Se `search_key` è un numero di telefono (solo cifre, eventualmente precedute da '+'),
    lo usiamo come filtro su number; altrimenti lo consideriamo group_name.
    """
    # pattern per riconoscere un numero (6–15 cifre, opzionalmente con '+' davanti)
    phone_pattern = re.compile(r'^\d{6,15}$')

    number = search_key if phone_pattern.match(search_key) else None
    group_name = search_key if number is None else None

    # base della query
    query = """
        SELECT
            CASE
                WHEN chat.subject IS NOT NULL THEN sender_jid.user
                ELSE chat_jid.user
            END AS number,
            chat.subject AS group_name,
            message.timestamp AS message_timestamp, 
            message.text_data AS text_data,
            message.from_me AS from_me
        FROM message 
        INNER JOIN chat ON message.chat_row_id = chat._id
        INNER JOIN jid AS chat_jid ON chat.jid_row_id = chat_jid._id
        LEFT JOIN jid AS sender_jid ON message.sender_jid_row_id = sender_jid._id
        WHERE 1=1
    """
    params = []

    # aggiungo il filtro dinamico
    if number:
        query += """
        AND number = ?
        """
        params.append(number)
    else:
        query += " AND chat.subject LIKE ?"
        # aggiungo i wildcard % intorno al group_name
        params.append(f"%{group_name}%")

    query += " ORDER BY message.received_timestamp DESC LIMIT 100"

    # eseguo la query
    data = fetch_data(query, tuple(params))
    
    results_latest = []
    for row in data:
        number, group_name, message_timestamp, text_data, from_me = row

        # Formattazione timestamp
        if isinstance(message_timestamp, (int, float)) and message_timestamp > 0:
            message_timestamp = datetime.fromtimestamp(message_timestamp/1000).strftime('%Y-%m-%d %H:%M:%S')
        else:
            message_timestamp = "Data non disponibile"
        
        if from_me:
            results_latest.append(
                f"DA: Questo numero | "
                f"{'GRUPPO: ' + group_name + ' | ' if group_name else 'A: ' + number + ' | '}"
                f"DATA INVIO: {message_timestamp} | "
                f"TESTO: {text_data}"
            )
        else:
            results_latest.append(
                f"DA: {number} | "
                f"{'GRUPPO: ' + group_name + ' | ' if group_name else 'A: Questo numero | '}"
                f"DATA INVIO: {message_timestamp} | "
                f"TESTO: {text_data}"
            )

    return results_latest

# Funzione per mostrare i risultati della ricerca degli ultimi messaggi
def show_latest_messages(number):
    results_latest = search_latest_messages(number)
    
    top = Toplevel()
    top.title(f"Risultati ricerca: '{number}'")
    top.protocol("WM_DELETE_WINDOW", top.destroy)  # Chiude correttamente la finestra
    
    listbox = Listbox(top, width=120, height=20, font=('Consolas', 8))
    scrollbar = Scrollbar(top, orient="vertical", command=listbox.yview)
    listbox.config(yscrollcommand=scrollbar.set)
    
    for result in results_latest:
        listbox.insert("end", result)
    
    listbox.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")











# SEZIONE ANALISI AVANZATA

# Funzione per analisi multivariata (media type e duration)
def get_media_analysis():
    try:
        query = """
            SELECT 
                mime_type,
                ROUND(AVG(CASE WHEN media_duration > 0 THEN media_duration ELSE NULL END), 2) as avg_duration,
                COUNT(*) as count
            FROM message_media
            WHERE 
                mime_type IS NOT NULL AND
                media_duration IS NOT NULL
            GROUP BY mime_type
            HAVING count > 5
            ORDER BY count DESC;
        """
        return fetch_data(query)
    except sqlite3.OperationalError:
        return []

# Funzione per visualizzazione multivariata
def plot_media_analysis():
    def plot(fig):
        data = get_media_analysis()
        if not data:
            ax = fig.add_subplot(111)
            ax.set_title("Nessun dato media trovato...")
            return
        
        types, durations, counts = zip(*data)
        
        ax = fig.add_subplot(111)
        fig.set_size_inches(12, 6)
        bars = plt.barh(types, counts, color='skyblue')
        plt.bar_label(bars, fmt='%d', padding=3)
        ax.set_xlabel("Numero di messaggi")
        ax.set_title("Distribuzione Tipi Media (Con almeno 5 occorrenze)")
        
        # Aggiungi durata media solo se presente
        if any(durations):
            ax2 = plt.gca().twiny()
            ax2.plot(durations, types, 'ro-', alpha=0.5)
            ax2.set_xlabel("Durata media (secondi)")
        
        plt.tight_layout()
    
    show_plot(plot)


# Funzione per timeline messaggi
def get_message_timeline():
    try:
        # Prima trova l'ultimo timestamp dal database
        last_msg_query = "SELECT MAX(timestamp) FROM message WHERE timestamp > 0"
        max_ts = fetch_data(last_msg_query)[0][0]

        if not max_ts or max_ts <= 0:
            raise ValueError("Nessun timestamp valido nel database")

        # Converti l'ultimo timestamp a datetime
        last_date = datetime.fromtimestamp(max_ts / 1000)
        start_date = last_date - timedelta(days=365)

        # Converti in millisecondi WhatsApp
        min_ts = int(start_date.timestamp()) * 1000
        max_ts = int(last_date.timestamp()) * 1000

        query = """
            SELECT 
                timestamp,
                text_data,
                message_type
            FROM message
            WHERE 
                timestamp IS NOT NULL AND
                timestamp >= ? AND 
                timestamp <= ?
            ORDER BY timestamp DESC;
        """
        return fetch_data(query, (min_ts, max_ts))
    
    except Exception as e:
        print(f"Errore database: {str(e)}")
        return []

# Funzione per visualizzazione timeline
def plot_timeline():
    def plot(fig):
        data = get_message_timeline()
        if not data:
            plt.title("Nessun dato trovato nel database")
            plt.show()
            return

        # I timestamp sono nel primo elemento di ogni riga
        first_ts = data[0][0]
        # Se il valore è maggiore di 1e10 lo consideriamo in ms, altrimenti in s
        unit = 'ms' if first_ts > 1e10 else 's'

        # Converte tutti i timestamp in datetime usando l'unità corretta
        message_dates = pd.to_datetime([row[0] for row in data], unit=unit)
        # "Normalizza" le date (imposta l'orario a mezzanotte) per raggruppare per giorno
        message_dates = message_dates.normalize()

        # Determina l'ultimo giorno (massimo) e imposta il range degli ultimi 365 giorni
        last_date = message_dates.max()
        start_date = last_date - pd.Timedelta(days=365)

        # Crea un intervallo continuo di date (giorno per giorno)
        date_range = pd.date_range(start=start_date, end=last_date, freq='D')

        # Conta il numero di messaggi per ciascun giorno
        daily_counts = pd.Series(message_dates).value_counts().sort_index()
        # Reindicizza la serie per includere ogni giorno nell'intervallo (0 per i giorni senza messaggi)
        daily_counts = daily_counts.reindex(date_range, fill_value=0)

        # Crea il grafico a barre
        ax = fig.add_subplot(111)
        fig.set_size_inches(18, 6)
        ax.bar(date_range, daily_counts.values, width=0.8, edgecolor='black')

        # Formattta l'asse x per visualizzare le date in modo leggibile
        ax.xaxis.set_major_locator(mdates.AutoDateLocator())
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45, ha='right', fontsize=8)

        ax.set_title(f"Distribuzione Giornaliera Messaggi (Ultimi 365 giorni)\nTotale messaggi: {len(data)}")
        ax.set_xlabel("Giorno")
        ax.set_ylabel("Numero Messaggi")
        ax.grid(axis='y', linestyle='--', alpha=0.7)
        plt.tight_layout()

    show_plot(plot)


# Funzione per l'analisi temporale (utile per HEATMAP)
def get_interaction_data():
    query = "SELECT timestamp FROM message WHERE timestamp IS NOT NULL"
    return [row[0] for row in fetch_data(query)]

# Funzione per visualizzare il calore delle interazioni per ora/giorno
def plot_heatmap():
    def plot(fig):  # Accetta la figura come parametro
        timestamps = get_interaction_data()
        
        if not timestamps:
            ax = fig.add_subplot(111)
            ax.set_title("Nessun dato disponibile")
            return

        # Inizializza matrice 24h x 7giorni
        heatmap_data = np.zeros((24, 7))
        
        # Popola la matrice
        for ts in timestamps:
            try:
                dt = datetime.fromtimestamp(ts/1000)
                hour = dt.hour
                weekday = dt.weekday()  # 0=Lunedì, 6=Domenica
                heatmap_data[hour, weekday] += 1
            except Exception as e:
                print(f"Errore conversione timestamp: {e}")
                continue

        # Controllo dati non nulli
        if np.sum(heatmap_data) == 0:
            plt.figure(figsize=(10,6))
            plt.title("Nessuna interazione registrata")
            plt.show()
            return

        # Normalizzazione migliorata
        max_val = np.max(heatmap_data)
        norm = plt.Normalize(vmin=0, vmax=max_val if max_val > 0 else 1)

        # Configurazione grafica
        ax = fig.add_subplot(111)
        fig.set_size_inches(12, 8)
        ax = plt.gca()
        
        # Crea heatmap con annotazioni
        im = ax.imshow(heatmap_data, cmap='YlOrRd', aspect='auto',
                      norm=norm, origin='lower')

        # Etichette assi dettagliate
        giorni = ['Lunedì', 'Martedì', 'Mercoledì', 
                'Giovedì', 'Venerdì', 'Sabato', 'Domenica']
        ore = [f"{h:02d}:00" for h in range(24)]
        
        ax.set_xticks(np.arange(7))
        ax.set_xticklabels(giorni, rotation=45, ha='right')
        ax.set_yticks(np.arange(24))
        ax.set_yticklabels(ore)
        ax.tick_params(axis='both', which='major', labelsize=8)

        # Griglia e colorbar
        ax.set_xticks(np.arange(7)+0.5, minor=True)
        ax.set_yticks(np.arange(24)+0.5, minor=True)
        ax.grid(which='minor', color='white', linestyle='-', linewidth=0.5)
        
        cbar = plt.colorbar(im, ax=ax)
        cbar.set_label('Numero di Messaggi', rotation=270, labelpad=20)

        # Annotazioni valori
        threshold = max_val * 0.5  # Soglia per il contrasto del testo
        for i in range(24):
            for j in range(7):
                color = 'white' if heatmap_data[i, j] > threshold else 'black'
                ax.text(j, i, f"{int(heatmap_data[i, j])}",
                       ha="center", va="center",
                       color=color, fontsize=6)

        plt.title('Mappa Calore delle Interazioni - Frequenza Messaggi per Ora/Giorno\n', fontsize=12)
        plt.tight_layout()

    show_plot(plot)


# CREAZIONE GUI


# Funzione di creazione della GUI
def create_gui():
    root = Tk()
    root.title("WhatsApp Forensics Toolkit - Enhanced")
    root.geometry("900x600")
    root.minsize(800, 500)
    
    # Main container
    main_frame = Frame(root)
    main_frame.pack(fill="both", expand=True, padx=15, pady=15)
    
    # Configurazione griglia responsive
    main_frame.columnconfigure(0, weight=1, uniform="group1")
    main_frame.columnconfigure(1, weight=1, uniform="group1")
    main_frame.rowconfigure(0, weight=1)
    main_frame.rowconfigure(1, weight=1)

    # Sezione Analisi Chat (Sinistra)
    chat_frame = ttk.LabelFrame(main_frame, text=" Analisi Chat ", padding=(10,5))
    chat_frame.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
    
    ttk.Button(chat_frame, text="Chat più attive", command=plot_active_chats).pack(fill="x", pady=3)
    ttk.Button(chat_frame, text="Ultime chat attive", command=show_recent_chats).pack(fill="x", pady=3)
    ttk.Button(chat_frame, text="Messaggi cancellati", command=show_deleted_messages).pack(fill="x", pady=3)
    ttk.Button(chat_frame, text="Chat effimere attive", command=show_ephemeral_chats).pack(fill="x", pady=3)
    
    # Sezione Analisi Testuale (Sinistra - Inferiore)
    text_frame = ttk.LabelFrame(main_frame, text=" Analisi Testuale ", padding=(10,5))
    text_frame.grid(row=1, column=0, sticky="nsew", padx=5, pady=5)
    
    ttk.Button(text_frame, text="Parole più usate", command=plot_word_histogram).pack(fill="x", pady=3)
    ttk.Button(text_frame, text="Parole più usate (4+ lettere)", command=plot_word_histogram_min_4).pack(fill="x", pady=3)
    ttk.Button(text_frame, text="Genera WordCloud (4+ lettere)", command=plot_wordcloud).pack(fill="x", pady=3)
    ttk.Button(text_frame, text="Analisi Sentiment", command=plot_sentiment).pack(fill="x", pady=3)

    # Sezione Ricerche (Destra - Superiore)
    search_frame = ttk.LabelFrame(main_frame, text=" Ricerche ", padding=(10,5))
    search_frame.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)
    
    Label(search_frame, text="Cerca messaggi per parola:").pack(anchor="w")
    search_entry = ttk.Entry(search_frame)
    search_entry.pack(fill="x", pady=3)
    ttk.Button(search_frame, text="Avvia ricerca testuale", command=lambda: show_search_results(search_entry.get())).pack(fill="x", pady=3)
    
    Label(search_frame, text="Ricerca per numero:").pack(anchor="w", pady=(10,0))
    number_entry = ttk.Entry(search_frame)
    number_entry.pack(fill="x", pady=3)

    ttk.Button(search_frame, text="Visualizza posizioni condivise", command=lambda: show_location_map(number_entry.get())).pack(fill="x", pady=3)
    ttk.Button(search_frame, text="Avvia ricerca messaggi cancellati", command=lambda: show_search_deleted(number_entry.get())).pack(fill="x", pady=3)
    ttk.Button(search_frame, text="Avvia ricerca messaggi onetime", command=lambda: show_search_onetime(number_entry.get())).pack(fill="x", pady=3)

    Label(search_frame, text="Ricerca ultimi 100 messaggi per numero / nome gruppo:").pack(anchor="w", pady=(10,0))
    number_group_entry = ttk.Entry(search_frame)
    number_group_entry.pack(fill="x", pady=3)
    ttk.Button(search_frame, text="Visualizza ultimi messaggi", command=lambda: show_latest_messages(number_group_entry.get())).pack(fill="x", pady=3)

    # Sezione Analisi Avanzata (Destra - Inferiore)
    advanced_frame = ttk.LabelFrame(main_frame, text=" Analisi Avanzata ", padding=(10,5))
    advanced_frame.grid(row=1, column=1, sticky="nsew", padx=5, pady=5)
    
    ttk.Button(advanced_frame, text="Analisi Media", command=plot_media_analysis).pack(fill="x", pady=3)
    ttk.Button(advanced_frame, text="Timeline Messaggi", command=plot_timeline).pack(fill="x", pady=3)
    ttk.Button(advanced_frame, text="Mappa Calore Interazioni", command=plot_heatmap).pack(fill="x", pady=2)

    # Padding a tutti i widget
    for child in main_frame.winfo_children():
        child.grid_configure(padx=5, pady=5)
    
    root.mainloop()

if __name__ == "__main__":
    create_gui()