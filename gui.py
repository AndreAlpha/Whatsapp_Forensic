import os
import webbrowser
import io
import base64
from datetime import datetime
import warnings

# Import per la GUI
from tkinter import Tk, Frame, Label, Menu, messagebox, Toplevel, Listbox, Scrollbar, Text, BooleanVar
from tkinter import ttk
from tkinter.filedialog import askopenfilename, asksaveasfilename
from tkinter.simpledialog import askinteger
from tkinter import PhotoImage

# Import per l'analisi e il plotting
import matplotlib.pyplot as plt
import pandas as pd
import numpy as np
from collections import Counter
from wordcloud import WordCloud
import folium
from textblob import TextBlob

# Import per il report PDF
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import cm
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image, Table, TableStyle, PageBreak
from reportlab.lib import colors

# Import per il clustering (opzionali)
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.decomposition import PCA
    from scipy.cluster.hierarchy import dendrogram, linkage
    import nltk
    CLUSTERING_ENABLED = True
except ImportError:
    CLUSTERING_ENABLED = False

# Ignora avvisi non critici
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning)

from database_manager import DatabaseManager
from icons import ICON_DATA

class WhatsAppForensicsApp:
    """Classe principale dell'applicazione GUI per l'analisi forense di WhatsApp."""
    def __init__(self, root):
        self.root = root
        self.root.title("WhatsApp Forensics Toolkit")
        self.root.geometry("1050x700")
        self.root.minsize(900, 650)
        self.db_manager = None
        self.db_path = None
        self.icons = {}
        self.welcome_tab = None
        self.clustering_enabled = CLUSTERING_ENABLED
        self.nltk_stopwords_ready = False

        self._setup_styles_and_icons()
        self._create_widgets()

    def _setup_styles_and_icons(self):
        self.style = ttk.Style(self.root)
        self.style.theme_use("clam")
        self.colors = {"bg": "#ECECEC", "fg": "#333333", "button": "#FFFFFF", "accent": "#075E54"}
        self.root.configure(bg=self.colors["bg"])
        self.style.configure("TButton", padding=6, relief="flat", font=('Helvetica', 10), background=self.colors["button"], foreground=self.colors["fg"])
        self.style.map("TButton", background=[('active', '#E0E0E0')])
        self.style.configure("TLabelFrame", padding=10, font=('Helvetica', 11, 'bold'), foreground=self.colors["accent"])
        self.style.configure("TNotebook", background=self.colors["bg"], borderwidth=0)
        self.style.configure("TNotebook.Tab", font=('Helvetica', 10, 'bold'), padding=[10, 5], foreground=self.colors["fg"])
        self.style.map("TNotebook.Tab", background=[("selected", self.colors["bg"])], foreground=[("selected", self.colors["accent"])])
        self.style.configure("Accent.TButton", foreground="white", background=self.colors["accent"], font=('Helvetica', 11, 'bold'))
        self.style.map("Accent.TButton", background=[('active', '#128C7E')])
        
        for name, b64_data in ICON_DATA.items():
            try:
                image_data = base64.b64decode(b64_data)
                self.icons[name] = PhotoImage(data=image_data)
            except Exception as e:
                print(f"Errore nel caricare l'icona '{name}': {e}")

    def _create_widgets(self):
        menu_bar = Menu(self.root)
        self.root.config(menu=menu_bar)
        file_menu = Menu(menu_bar, tearoff=0)
        menu_bar.add_cascade(label="File", menu=file_menu)
        file_menu.add_command(label="Apri Database (msgstore.db)...", command=self._open_database)
        file_menu.add_separator()
        file_menu.add_command(label="Esci", command=self.root.quit)

        self.status_bar = Label(self.root, text="Pronto. Aprire un database per iniziare.", bd=1, relief="sunken", anchor="w", padx=5)
        self.status_bar.pack(side="bottom", fill="x")

        self.notebook = ttk.Notebook(self.root, padding=10)
        self.notebook.pack(expand=True, fill="both")
        
        self._create_welcome_tab()
        
        if not self.clustering_enabled:
            messagebox.showwarning("Librerie Mancanti", "Le librerie per il clustering (scikit-learn, scipy, nltk) non sono installate. La scheda 'Analisi Clustering' non sarà disponibile.")

    def _open_database(self):
        db_path = askopenfilename(title="Seleziona il database msgstore.db", filetypes=[("Database SQLite", "*.db"), ("Tutti i file", "*.*")])
        if db_path:
            try:
                self.db_manager = DatabaseManager(db_path)
                self.db_path = db_path
                self.status_bar.config(text=f"Database caricato: {os.path.basename(db_path)}")
                self._populate_analysis_tabs()
            except Exception as e:
                messagebox.showerror("Errore Inizializzazione", f"Impossibile inizializzare il database o le schede di analisi:\n{e}")
                self.status_bar.config(text="Errore nel caricamento del database.")

    def _populate_analysis_tabs(self):
        try:
            # Rimuove la welcome tab se esiste
            if self.welcome_tab and self.welcome_tab.winfo_exists():
                self.notebook.forget(self.welcome_tab)
                self.welcome_tab = None
            # Pulisce le tab esistenti per un nuovo caricamento
            for i in self.notebook.tabs():
                self.notebook.forget(i)

            # Crea le tab di analisi
            self._create_chat_analysis_tab()
            self._create_text_analysis_tab()
            if self.clustering_enabled:
                self._create_clustering_analysis_tab()
            self._create_search_tab()
            self._create_advanced_analysis_tab()
            self._create_report_tab()
        except Exception as e:
            messagebox.showerror("Errore Creazione Tabs", f"Impossibile creare le schede di analisi:\n{e}")

    def _create_tab_frame(self, tab_name, parent_notebook):
        tab = ttk.Frame(parent_notebook, padding=10, style="TFrame")
        parent_notebook.add(tab, text=tab_name)
        frame = ttk.LabelFrame(tab, text=f"Funzioni di {tab_name}")
        frame.pack(expand=True, fill="both", padx=10, pady=10)
        return frame

    def _add_button(self, parent, text, icon_name, command):
        icon_to_use = self.icons.get(icon_name)
        btn = ttk.Button(parent, text=text, image=icon_to_use, compound="left", command=command)
        btn.pack(fill="x", pady=4, ipady=5)
        return btn

    def _create_welcome_tab(self):
        self.welcome_tab = ttk.Frame(self.notebook, padding=20)
        self.notebook.add(self.welcome_tab, text="Benvenuto")
        
        Label(self.welcome_tab, image=self.icons.get('welcome')).pack(pady=20)
        Label(self.welcome_tab, text="WhatsApp Forensics Toolkit", font=("Helvetica", 18, "bold"), bg=self.colors["bg"], fg=self.colors["accent"]).pack(pady=10)
        Label(self.welcome_tab, text="Per iniziare, apri un database WhatsApp (msgstore.db) dal menu 'File'.", font=("Helvetica", 11), bg=self.colors["bg"]).pack(pady=5)
        ttk.Button(self.welcome_tab, text="Apri Database...", command=self._open_database, style="Accent.TButton").pack(pady=20, ipady=8)

    def _create_chat_analysis_tab(self):
        frame = self._create_tab_frame("Analisi Chat", self.notebook)
        self._add_button(frame, "Top 10 Chat più Attive", "chart_bar", self._plot_active_chats)
        self._add_button(frame, "Ultime 20 Chat Attive", "chat", self._show_recent_chats)
        self._add_button(frame, "Mostra Messaggi Cancellati", "trash", lambda: self._show_deleted_messages())
        self._add_button(frame, "Chat con Messaggi Effimeri", "clock", self._show_ephemeral_chats)

    def _create_text_analysis_tab(self):
        frame = self._create_tab_frame("Analisi Testuale", self.notebook)
        self._add_button(frame, "Top 20 Parole più Usate", "text", lambda: self._plot_word_histogram(min_len=1))
        self._add_button(frame, "Top 20 Parole (min. 4 lettere)", "text", lambda: self._plot_word_histogram(min_len=4))
        self._add_button(frame, "Genera WordCloud", "cloud", self._plot_wordcloud)
        self._add_button(frame, "Distribuzione del Sentiment", "sentiment", self._plot_sentiment)

    def _create_clustering_analysis_tab(self):
        frame = self._create_tab_frame("Analisi Clustering", self.notebook)
        self._add_button(frame, "Clustering Gerarchico (Dendrogramma)", "cluster", self._perform_hierarchical_clustering)
        self._add_button(frame, "Clustering K-Means", "cluster", self._perform_kmeans_clustering)

    def _create_search_tab(self):
        tab = ttk.Frame(self.notebook, padding=10)
        self.notebook.add(tab, text="Ricerche")
        
        search_word_frame = ttk.LabelFrame(tab, text="Ricerca per Parola Chiave")
        search_word_frame.pack(fill="x", padx=10, pady=10)
        self.search_entry = ttk.Entry(search_word_frame, font=('Helvetica', 10))
        self.search_entry.pack(side="left", fill="x", expand=True, padx=5, ipady=4)
        ttk.Button(search_word_frame, text=" Cerca", image=self.icons.get('search'), compound="left", command=self._search_by_keyword).pack(side="right", padx=5)

        search_num_frame = ttk.LabelFrame(tab, text="Ricerca per Numero di Telefono o Nome Gruppo")
        search_num_frame.pack(fill="both", expand=True, padx=10, pady=10)
        Label(search_num_frame, text="Inserisci numero o nome:", font=('Helvetica', 9)).pack(anchor='w', padx=5)
        self.number_entry = ttk.Entry(search_num_frame, font=('Helvetica', 10))
        self.number_entry.pack(fill="x", padx=5, pady=(0, 10), ipady=4)

        btn_frame = ttk.Frame(search_num_frame)
        btn_frame.pack(fill='x', expand=True, anchor="n")
        
        self._add_button(btn_frame, "Ultimi 100 Messaggi", "chat", self._search_latest_messages)
        self._add_button(btn_frame, "Messaggi Cancellati", "trash", self._search_deleted_messages_by_number)
        self._add_button(btn_frame, "Messaggi 'Vedi una volta'", "clock", self._search_onetime_messages)
        self._add_button(btn_frame, "Posizioni (Mappa)", "map", self._show_location_map)

    def _create_advanced_analysis_tab(self):
        frame = self._create_tab_frame("Analisi Avanzata", self.notebook)
        self._add_button(frame, "Analisi dei Tipi di Media", "media", self._plot_media_analysis)
        self._add_button(frame, "Timeline Messaggi", "timeline", self._plot_timeline)
        self._add_button(frame, "Heatmap delle Interazioni", "heatmap", self._plot_heatmap)

    def _create_report_tab(self):
        frame = self._create_tab_frame("Report", self.notebook)
        self._add_button(frame, "Genera Report PDF", "pdf", self._open_report_window)
    
    def _prepare_nltk_stopwords(self):
        """Controlla e scarica le stopwords di NLTK solo se necessario."""
        if self.nltk_stopwords_ready:
            return True
        try:
            from nltk.corpus import stopwords
            stopwords.words('italian')
            self.nltk_stopwords_ready = True
            return True
        except LookupError:
            self.status_bar.config(text="Download del pacchetto 'stopwords' di NLTK in corso...")
            self.root.update_idletasks()
            if messagebox.askyesno("Download Necessario", "Il pacchetto 'stopwords' di NLTK per l'italiano non è stato trovato. Vuoi scaricarlo ora?"):
                try:
                    nltk.download('stopwords')
                    self.nltk_stopwords_ready = True
                    self.status_bar.config(text="Download completato.")
                    return True
                except Exception as e:
                    messagebox.showerror("Errore Download", f"Impossibile scaricare il pacchetto NLTK:\n{e}")
                    self.status_bar.config(text="Download fallito.")
                    return False
            else:
                self.status_bar.config(text="Download annullato.")
                return False
        except Exception as e:
            messagebox.showerror("Errore NLTK", f"Errore durante l'inizializzazione di NLTK:\n{e}")
            return False

    def _show_plot(self, plot_function, title, figsize=(10,6)):
        self.status_bar.config(text=f"Generazione grafico: {title}...")
        self.root.update_idletasks()
        try:
            plt.style.use('seaborn-v0_8-whitegrid')
            plt.close('all')
            fig = plt.figure(figsize=figsize)
            plot_function(fig)
            plt.tight_layout(pad=2.0)
            plt.show()
            self.status_bar.config(text="Grafico generato con successo.")
        except Exception as e:
            messagebox.showerror("Errore Grafico", f"Impossibile generare il grafico:\n{e}")
            self.status_bar.config(text="Errore durante la generazione del grafico.")
        finally:
            plt.close('all')

    def _format_timestamp(self, ts, default="N/D"):
        if ts and isinstance(ts, (int, float)) and ts > 0:
            unit = 1000 if ts > 1e12 else 1
            return datetime.fromtimestamp(ts / unit).strftime('%Y-%m-%d %H:%M:%S')
        return default

    def _create_results_window(self, title, data, is_text_content=False):
        if not data:
            messagebox.showinfo("Nessun Risultato", "La ricerca non ha prodotto risultati.")
            return

        top = Toplevel(self.root)
        top.title(title)
        top.geometry("800x500")

        frame = Frame(top)
        frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        if is_text_content:
            text_area = Text(frame, wrap="word", font=('Consolas', 10))
            scrollbar_y = ttk.Scrollbar(frame, orient="vertical", command=text_area.yview)
            text_area.config(yscrollcommand=scrollbar_y.set)
            text_area.insert("1.0", data)
            text_area.config(state="disabled")
            scrollbar_y.pack(side="right", fill="y")
            text_area.pack(side="left", fill="both", expand=True)
        else:
            listbox = Listbox(frame, font=('Consolas', 9))
            scrollbar_y = Scrollbar(frame, orient="vertical", command=listbox.yview)
            scrollbar_x = Scrollbar(frame, orient="horizontal", command=listbox.xview)
            listbox.config(yscrollcommand=scrollbar_y.set, xscrollcommand=scrollbar_x.set)
            for item in data: listbox.insert("end", item)
            scrollbar_y.pack(side="right", fill="y")
            scrollbar_x.pack(side="bottom", fill="x")
            listbox.pack(side="left", fill="both", expand=True)

    def _plot_active_chats(self):
        data = self.db_manager.get_active_chats()
        if not data: return messagebox.showinfo("Informazione", "Nessuna chat attiva trovata.")
        def plot(fig):
            chat_ids, counts = zip(*data)
            ax = fig.add_subplot(111)
            ax.barh(chat_ids, counts, color='#075E54')
            ax.set_xlabel("Numero di Messaggi"); ax.set_ylabel("Chat"); ax.set_title("Top 10 Chat più Attive")
            ax.invert_yaxis()
        self._show_plot(plot, "Chat Attive")

    def _show_recent_chats(self):
        self.status_bar.config(text="Caricamento chat recenti...")
        data = self.db_manager.get_recent_chats()
        formatted = [f"{i}. {row[0]} (Ultimo: {self._format_timestamp(row[1])})" for i, row in enumerate(data, 1)]
        self._create_results_window("Ultime 20 Chat Attive", formatted)
        self.status_bar.config(text="Pronto.")

    def _show_deleted_messages(self, number=None):
        self.status_bar.config(text="Ricerca messaggi cancellati...")
        data = self.db_manager.get_deleted_messages(number)
        results = []
        for phone, group, msg_ts, rev_ts, from_me in data:
            direction = f"DA: Tu | A: {phone or 'Sconosciuto'}" if from_me else f"DA: {phone or 'Sconosciuto'} | A: Tu"
            group_info = f" | GRUPPO: {group}" if group else ""
            results.append(f"{direction}{group_info} | INVIO: {self._format_timestamp(msg_ts)} | CANCELLAZIONE: {self._format_timestamp(rev_ts)}")
        title = f"Messaggi Cancellati (Filtro: {number})" if number else "Tutti i Messaggi Cancellati"
        self._create_results_window(title, results)
        self.status_bar.config(text="Pronto.")

    def _show_ephemeral_chats(self):
        self.status_bar.config(text="Caricamento chat effimere...")
        data = self.db_manager.get_ephemeral_chats()
        results = [f"{(f'GRUPPO: {g}' if g else f'NUMERO: {p}')} | TIMER: {int(e / 86400)} giorni" for p, g, e in data]
        self._create_results_window("Chat con Messaggi Effimeri", results)
        self.status_bar.config(text="Pronto.")

    def _plot_word_histogram(self, min_len=1):
        self.status_bar.config(text="Analisi frequenza parole...")
        text_data = self.db_manager.get_all_text_messages()
        if not text_data: return messagebox.showinfo("Informazione", "Nessun messaggio di testo trovato.")
        words = " ".join(row[0] for row in text_data).lower().split()
        if min_len > 1:
            words = [word.strip('.,!?()[]{}"\'') for word in words if len(word) >= min_len]
        if not words: return messagebox.showinfo("Informazione", "Nessuna parola trovata con i criteri specificati.")
        word_counts = Counter(words).most_common(20)
        def plot(fig):
            common_words, counts = zip(*word_counts)
            ax = fig.add_subplot(111)
            ax.barh(common_words, counts, color='#128C7E')
            ax.set_title(f"Top 20 Parole più Utilizzate (min. {min_len} lettere)")
            ax.invert_yaxis()
        self._show_plot(plot, f"Frequenza Parole (min {min_len})")

    def _plot_wordcloud(self):
        self.status_bar.config(text="Generazione WordCloud...")
        text_data = self.db_manager.get_all_text_messages()
        if not text_data: return messagebox.showinfo("Informazione", "Nessun testo per la WordCloud.")
        text = " ".join(row[0] for row in text_data)
        words = [word.strip('.,!?()[]{}"\'') for word in text.lower().split() if len(word) >= 4]
        if not words: return messagebox.showinfo("Informazione", "Nessuna parola sufficiente per la WordCloud.")
        def plot(fig):
            wordcloud = WordCloud(width=800, height=400, background_color='white', colormap='viridis').generate(" ".join(words))
            ax = fig.add_subplot(111)
            ax.imshow(wordcloud, interpolation='bilinear')
            ax.axis("off"); ax.set_title("WordCloud delle Parole Più Usate")
        self._show_plot(plot, "WordCloud")

    def _plot_sentiment(self):
        self.status_bar.config(text="Analisi sentiment...")
        data = self.db_manager.get_text_for_sentiment()
        if not data: return messagebox.showinfo("Informazione", "Nessun testo per l'analisi del sentiment.")
        sentiments = [TextBlob(row[0]).sentiment.polarity for row in data]
        def plot(fig):
            ax = fig.add_subplot(111)
            ax.hist(sentiments, bins=20, color='purple', alpha=0.7)
            ax.set_title('Distribuzione del Sentiment dei Messaggi'); ax.set_xlabel('Polarità (-1 Negativo, 1 Positivo)'); ax.set_ylabel('Frequenza')
        self._show_plot(plot, "Analisi Sentiment")

    def _perform_hierarchical_clustering(self):
        if not self._prepare_nltk_stopwords(): return
        from nltk.corpus import stopwords
        self.status_bar.config(text="Avvio analisi gerarchica..."); self.root.update_idletasks()
        message_data = self.db_manager.get_messages_for_clustering(limit=100)
        if not message_data or len(message_data) < 2:
            messagebox.showinfo("Dati Insufficienti", "Non ci sono abbastanza messaggi (min 2) per l'analisi."); self.status_bar.config(text="Pronto."); return
        messagebox.showinfo("Nota", "Il clustering gerarchico verrà eseguito su un campione di max 100 messaggi per garantire la leggibilità del dendrogramma.")
        self.status_bar.config(text="Vettorizzazione del testo..."); self.root.update_idletasks()
        vectorizer = TfidfVectorizer(max_features=100, stop_words=stopwords.words('italian'))
        docs = [row[0] for row in message_data]
        tfidf_matrix = vectorizer.fit_transform(docs)
        self.status_bar.config(text="Calcolo del linkage..."); self.root.update_idletasks()
        linked = linkage(tfidf_matrix.toarray(), method='ward')
        def plot(fig):
            ax = fig.add_subplot(111)
            dendrogram(linked, orientation='top', distance_sort='descending', show_leaf_counts=True, ax=ax)
            ax.set_title("Dendrogramma del Clustering Gerarchico"); ax.set_ylabel("Distanza")
        self._show_plot(plot, "Dendrogramma Gerarchico", figsize=(12, 7))
        self.status_bar.config(text="Pronto.")

    def _perform_kmeans_clustering(self):
        if not self._prepare_nltk_stopwords(): return
        from nltk.corpus import stopwords
        k = askinteger("Numero di Cluster", "Inserisci il numero di cluster (k) desiderato:", initialvalue=5, minvalue=2, maxvalue=20)
        if not k: return
        self.status_bar.config(text=f"Avvio analisi K-Means con k={k}..."); self.root.update_idletasks()
        message_data = self.db_manager.get_messages_for_clustering(limit=2000)
        if not message_data or len(message_data) < k:
            messagebox.showinfo("Dati Insufficienti", f"Non ci sono abbastanza messaggi per creare {k} cluster."); self.status_bar.config(text="Pronto."); return
        self.status_bar.config(text="Vettorizzazione del testo..."); self.root.update_idletasks()
        vectorizer = TfidfVectorizer(max_df=0.8, min_df=5, stop_words=stopwords.words('italian'))
        docs = [row[0] for row in message_data]
        tfidf_matrix = vectorizer.fit_transform(docs)
        self.status_bar.config(text="Esecuzione di K-Means..."); self.root.update_idletasks()
        kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
        kmeans.fit(tfidf_matrix)
        clusters = kmeans.labels_
        pca = PCA(n_components=2, random_state=42)
        coords = pca.fit_transform(tfidf_matrix.toarray())
        def plot(fig):
            ax = fig.add_subplot(111)
            scatter = ax.scatter(coords[:, 0], coords[:, 1], c=clusters, cmap='viridis', alpha=0.7)
            ax.set_title(f'Visualizzazione Cluster K-Means (k={k}) con PCA')
            legend1 = ax.legend(*scatter.legend_elements(), title="Cluster"); ax.add_artist(legend1)
        self._show_plot(plot, f"Cluster K-Means (k={k})")
        self.status_bar.config(text="Calcolo parole chiave per cluster..."); self.root.update_idletasks()
        results_text = f"Parole chiave per i {k} cluster individuati:\n" + "="*40 + "\n\n"
        order_centroids = kmeans.cluster_centers_.argsort()[:, ::-1]
        try:
            terms = vectorizer.get_feature_names_out()
        except AttributeError:
            terms = vectorizer.get_feature_names()
        for i in range(k):
            top_words = [terms[ind] for ind in order_centroids[i, :10]]
            results_text += f"Cluster {i}:\n" + ", ".join(top_words) + "\n\n"
        self._create_results_window(f"Parole Chiave per Cluster (k={k})", results_text, is_text_content=True)
        self.status_bar.config(text="Pronto.")

    def _search_by_keyword(self):
        word = self.search_entry.get().strip()
        if not word: return messagebox.showwarning("Input Mancante", "Inserisci una parola da cercare.")
        self.status_bar.config(text=f"Ricerca di '{word}'..."); self.root.update_idletasks()
        data = self.db_manager.search_messages_by_word(word)
        results = [f"{self._format_timestamp(ts)} | {(f'GRUPPO: {g} | DA: {s}' if g else f'DA: Tu | A: {r}' if from_me else f'DA: {s} | A: Tu')} | MSG: {txt}" for txt, ts, from_me, s, r, g in data]
        self._create_results_window(f"Risultati per '{word}'", results)
        self.status_bar.config(text="Pronto.")

    def _search_latest_messages(self):
        key = self.number_entry.get().strip()
        if not key: return messagebox.showwarning("Input Mancante", "Inserisci un numero o nome gruppo.")
        self.status_bar.config(text=f"Ricerca ultimi messaggi per '{key}'..."); self.root.update_idletasks()
        data = self.db_manager.search_latest_messages(key)
        results = [f"{self._format_timestamp(ts)} | {(f'DA: Tu | GRUPPO: {g}' if from_me and g else f'DA: Tu | A: {n}' if from_me else f'DA: {n} | GRUPPO: {g}' if g else f'DA: {n} | A: Tu')} | TESTO: {txt or '[Media]'}" for n, g, ts, txt, from_me in data]
        self._create_results_window(f"Ultimi messaggi per '{key}'", results)
        self.status_bar.config(text="Pronto.")

    def _search_deleted_messages_by_number(self):
        number = self.number_entry.get().strip()
        if not number: return messagebox.showwarning("Input Mancante", "Inserisci un numero per filtrare.")
        self._show_deleted_messages(number)

    def _search_onetime_messages(self):
        number = self.number_entry.get().strip()
        if not number: return messagebox.showwarning("Input Mancante", "Inserisci un numero.")
        data = self.db_manager.search_onetime_messages(number)
        type_map = {42: "IMMAGINE", 43: "VIDEO", 82: "AUDIO"}
        results = [f"{self._format_timestamp(ts)} | {(f'DA: Tu | A: {n}' if from_me else f'DA: {n} | A: Tu')} | TIPO: {type_map.get(tid, 'Sconosciuto')}" for n, g, ts, txt, tid, from_me in data]
        self._create_results_window(f"Messaggi 'Vedi una volta' per '{number}'", results)

    def _show_location_map(self):
        number = self.number_entry.get().strip()
        if not number: return messagebox.showwarning("Input Mancante", "Inserisci un numero.")
        data = self.db_manager.search_locations_by_number(number)
        if not data: return messagebox.showinfo("Nessun Risultato", f"Nessuna posizione trovata per '{number}'.")
        map_center = [data[0][3], data[0][4]]
        m = folium.Map(location=map_center, zoom_start=13)
        for _, name, addr, lat, lon, ts in data:
            popup_content = f"<b>Data:</b> {self._format_timestamp(ts)}<br><b>Luogo:</b> {name or 'N/D'}<br><b>Indirizzo:</b> {addr or 'N/D'}"
            folium.Marker([lat, lon], popup=folium.Popup(popup_content, max_width=300), tooltip=name or self._format_timestamp(ts)).add_to(m)
        map_filename = "mappa_posizioni.html"
        m.save(map_filename)
        webbrowser.open(f'file://{os.path.realpath(map_filename)}')

    def _plot_media_analysis(self):
        data = self.db_manager.get_media_analysis_data()
        if not data: return messagebox.showinfo("Informazione", "Nessun dato media per l'analisi.")
        def plot(fig):
            types, _, counts = zip(*data)
            ax = fig.add_subplot(111)
            ax.barh([t.split('/')[1] for t in types], counts, color='teal', alpha=0.8)
            ax.set_title("Distribuzione Tipi di Media")
        self._show_plot(plot, "Analisi Media")

    def _plot_timeline(self):
        timestamps = self.db_manager.get_message_timestamps()
        if not timestamps: return messagebox.showinfo("Informazione", "Nessun messaggio per la timeline.")
        unit = 'ms' if timestamps[0][0] > 1e12 else 's'
        dates = pd.to_datetime([row[0] for row in timestamps], unit=unit).normalize()
        date_range = pd.date_range(start=dates.min(), end=dates.max(), freq='D')
        counts = dates.value_counts().reindex(date_range, fill_value=0)
        def plot(fig):
            ax = fig.add_subplot(111)
            ax.bar(date_range, counts.values, color='royalblue')
            ax.set_title("Timeline Messaggi"); fig.autofmt_xdate()
        self._show_plot(plot, "Timeline Messaggi", figsize=(14,7))

    def _plot_heatmap(self):
        timestamps = self.db_manager.get_message_timestamps()
        if not timestamps: return messagebox.showinfo("Informazione", "Nessun dato per la heatmap.")
        heatmap_data = np.zeros((24, 7))
        unit = 1000 if timestamps[0][0] > 1e12 else 1
        for ts_tuple in timestamps:
            try:
                dt = datetime.fromtimestamp(ts_tuple[0] / unit)
                heatmap_data[dt.hour, dt.weekday()] += 1
            except (ValueError, OSError): continue
        def plot(fig):
            ax = fig.add_subplot(111)
            im = ax.imshow(heatmap_data, cmap='YlOrRd', aspect='auto', origin='lower')
            ax.set_xticks(np.arange(7), ['Lunedì', 'Martedì', 'Mercoledì', 'Giovedì', 'Venerdì', 'Sabato', 'Domenica'], rotation=45, ha='right')
            ax.set_yticks(np.arange(24), [f"{h:02d}:00" for h in range(24)])
            plt.colorbar(im, ax=ax, label='Numero di Messaggi')
            ax.set_title('Heatmap delle Interazioni')
        self._show_plot(plot, "Heatmap Interazioni")

    def _generate_plot_to_buffer(self, plot_function, figsize):
        buffer = io.BytesIO()
        plt.style.use('seaborn-v0_8-whitegrid')
        fig = plt.figure(figsize=figsize)
        plot_function(fig)
        plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=300)
        plt.close(fig)
        buffer.seek(0)
        return buffer

    def _generate_active_chats_plot_for_pdf(self):
        data = self.db_manager.get_active_chats()
        if not data: return None
        def plot(fig):
            chat_ids, counts = zip(*data); ax = fig.add_subplot(111); ax.barh(chat_ids, counts, color='#075E54')
            ax.set_title("Top 10 Chat Attive"); ax.set_xlabel("Numero di Messaggi"); ax.invert_yaxis()
        buffer = self._generate_plot_to_buffer(plot, (8, 4))
        return Image(buffer, width=15*cm, height=7.5*cm)

    def _generate_media_analysis_plot_for_pdf(self):
        data = self.db_manager.get_media_analysis_data()
        if not data: return None
        def plot(fig):
            types, _, counts = zip(*data); ax = fig.add_subplot(111); ax.barh([t.split('/')[1] for t in types], counts, color='teal')
            ax.set_title("Distribuzione Tipi di Media"); ax.set_xlabel("Conteggio"); ax.invert_yaxis()
        buffer = self._generate_plot_to_buffer(plot, (8, 4))
        return Image(buffer, width=15*cm, height=7.5*cm)

    def _generate_timeline_plot_for_pdf(self):
        timestamps = self.db_manager.get_message_timestamps()
        if not timestamps: return None
        unit = 'ms' if timestamps[0][0] > 1e12 else 's'
        dates = pd.to_datetime([row[0] for row in timestamps], unit=unit).normalize()
        counts = dates.value_counts().sort_index()
        def plot(fig):
            ax = fig.add_subplot(111); ax.plot(counts.index, counts.values, color='royalblue')
            ax.set_title("Timeline Attività Messaggi"); ax.set_ylabel("Numero di Messaggi"); fig.autofmt_xdate()
        buffer = self._generate_plot_to_buffer(plot, (10, 5))
        return Image(buffer, width=16*cm, height=8*cm)
        
    def _generate_sentiment_plot_for_pdf(self):
        data = self.db_manager.get_text_for_sentiment()
        if not data: return None
        sentiments = [TextBlob(row[0]).sentiment.polarity for row in data]
        def plot(fig):
            ax = fig.add_subplot(111); ax.hist(sentiments, bins=20, color='purple', alpha=0.7)
            ax.set_title('Distribuzione del Sentiment'); ax.set_xlabel('Polarità'); ax.set_ylabel('Frequenza')
        buffer = self._generate_plot_to_buffer(plot, (8, 4))
        return Image(buffer, width=15*cm, height=7.5*cm)

    def _generate_heatmap_plot_for_pdf(self):
        timestamps = self.db_manager.get_message_timestamps()
        if not timestamps: return None
        heatmap_data = np.zeros((24, 7)); unit = 1000 if timestamps[0][0] > 1e12 else 1
        for ts_tuple in timestamps:
            try: dt = datetime.fromtimestamp(ts_tuple[0] / unit); heatmap_data[dt.hour, dt.weekday()] += 1
            except (ValueError, OSError): continue
        buffer = io.BytesIO()
        plt.style.use('seaborn-v0_8-whitegrid'); plt.figure(figsize=(8, 5)); ax = plt.subplot(111)
        im = ax.imshow(heatmap_data, cmap='YlOrRd', aspect='auto', origin='lower')
        ax.set_xticks(np.arange(7), ['Lun', 'Mar', 'Mer', 'Gio', 'Ven', 'Sab', 'Dom'])
        ax.set_yticks(np.arange(0, 24, 2)); ax.set_title('Heatmap delle Interazioni (Giorno/Ora)')
        plt.colorbar(im, ax=ax, label='N. Messaggi'); plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=300); plt.close(); buffer.seek(0)
        return Image(buffer, width=14*cm, height=8*cm)
        
    def _generate_wordcloud_plot_for_pdf(self):
        text_data = self.db_manager.get_all_text_messages()
        if not text_data: return None
        text = " ".join(row[0] for row in text_data)
        words = [word.strip('.,!?()[]{}"\'') for word in text.lower().split() if len(word) >= 4]
        if not words: return None
        buffer = io.BytesIO()
        wordcloud = WordCloud(width=800, height=400, background_color='white', colormap='viridis').generate(" ".join(words))
        plt.figure(figsize=(8, 4)); plt.imshow(wordcloud, interpolation='bilinear'); plt.axis("off"); plt.tight_layout()
        plt.savefig(buffer, format='png', dpi=300); plt.close(); buffer.seek(0)
        return Image(buffer, width=16*cm, height=8*cm)

    def _open_report_window(self):
        top = Toplevel(self.root); top.title("Genera Report PDF"); top.geometry("600x750")
        plot_frame = ttk.LabelFrame(top, text="Seleziona i grafici da includere")
        plot_frame.pack(pady=10, padx=10, fill="x")
        self.report_vars = {}
        report_plot_options = {
            "active_chats": "Grafico Chat più Attive", "media_types": "Grafico Tipi di Media",
            "timeline": "Grafico Timeline Messaggi", "sentiment": "Grafico Analisi del Sentiment",
            "heatmap": "Heatmap delle Interazioni", "wordcloud": "WordCloud delle Parole"
        }
        for key, label in report_plot_options.items():
            var = BooleanVar(value=True); self.report_vars[key] = var
            chk = ttk.Checkbutton(plot_frame, text=label, variable=var); chk.pack(anchor="w", padx=10, pady=2)
        notes_frame = ttk.LabelFrame(top, text="Considerazioni del Consulente Tecnico")
        notes_frame.pack(expand=True, fill="both", padx=10, pady=(0, 10))
        text_widget = Text(notes_frame, wrap="word", font=('Helvetica', 10), bd=0, highlightthickness=0)
        scrollbar = ttk.Scrollbar(notes_frame, command=text_widget.yview); text_widget.config(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y"); text_widget.pack(side="left", fill="both", expand=True, padx=5, pady=5)
        def get_selections_and_generate():
            selected_plots = {key: var.get() for key, var in self.report_vars.items()}
            expert_notes = text_widget.get("1.0", "end-1c")
            self._generate_pdf_report(expert_notes, selected_plots); top.destroy()
        ttk.Button(top, text="Salva Report in PDF", command=get_selections_and_generate, style="Accent.TButton").pack(pady=10, ipady=5)

    def _generate_pdf_report(self, expert_notes, selected_plots):
        filepath = asksaveasfilename(defaultextension=".pdf", filetypes=[("PDF Documents", "*.pdf")], title="Salva Report come PDF")
        if not filepath: return
        self.status_bar.config(text="Generazione Report PDF in corso..."); self.root.update_idletasks()
        try:
            doc = SimpleDocTemplate(filepath, pagesize=A4, rightMargin=2*cm, leftMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
            styles = getSampleStyleSheet(); story = []
            story.append(Paragraph("Report di Analisi Forense WhatsApp", styles['h1']))
            story.append(Paragraph(f"File Analizzato: {os.path.basename(self.db_path)}", styles['Normal']))
            story.append(Paragraph(f"Data Report: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", styles['Normal']))
            story.append(Spacer(1, 1*cm))
            stats = self.db_manager.get_summary_stats()
            story.append(Paragraph("Statistiche Riassuntive", styles['h2']))
            story.append(Paragraph(f" •  <b>Numero Totale di Chat:</b> {stats['total_chats']}", styles['Normal']))
            story.append(Paragraph(f" •  <b>Numero Totale di Messaggi:</b> {stats['total_messages']}", styles['Normal']))
            story.append(Paragraph(f" •  <b>Periodo di Attività:</b> Dal {self._format_timestamp(stats['start_date'])} al {self._format_timestamp(stats['end_date'])}", styles['Normal']))
            story.append(Spacer(1, 1*cm))
            story.append(Paragraph("Top 5 Chat più Attive", styles['h2']))
            active_chats_data = [['Chat/Utente', 'Numero Messaggi']] + self.db_manager.get_active_chats(limit=5)
            tbl = Table(active_chats_data, colWidths=[10*cm, 4*cm])
            tbl.setStyle(TableStyle([('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#075E54")), ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'CENTER'), ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 12), ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 1, colors.black)]))
            story.append(tbl)
            
            plot_generators = {
                "active_chats": self._generate_active_chats_plot_for_pdf, "heatmap": self._generate_heatmap_plot_for_pdf,
                "wordcloud": self._generate_wordcloud_plot_for_pdf, "media_types": self._generate_media_analysis_plot_for_pdf,
                "timeline": self._generate_timeline_plot_for_pdf, "sentiment": self._generate_sentiment_plot_for_pdf,
            }

            if any(selected_plots.values()):
                story.append(PageBreak()); story.append(Paragraph("Analisi Grafiche", styles['h2']))
                for key, is_selected in selected_plots.items():
                    if is_selected and key in plot_generators:
                        plot_image = plot_generators[key]()
                        if plot_image:
                            story.append(plot_image); story.append(Spacer(1, 0.5*cm))
            if expert_notes.strip():
                story.append(PageBreak()); story.append(Paragraph("Considerazioni del Consulente Tecnico", styles['h2']))
                story.append(Paragraph(expert_notes.replace('\n', '<br/>'), styles['Normal']))

            doc.build(story)
            messagebox.showinfo("Successo", f"Report PDF salvato con successo in:\n{filepath}")
        except Exception as e:
            messagebox.showerror("Errore Report", f"Impossibile generare il report PDF:\n{e}")
        finally:
            self.status_bar.config(text="Pronto."); plt.close('all')
