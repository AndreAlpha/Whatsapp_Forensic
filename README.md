# Whatsapp_Forensic

## Guida alla Decifrazione e Analisi del Database .crypt15

Questa guida descrive il processo per decifrare un database cifrato (`msgstore.db.crypt15`) utilizzando una chiave a 64 cifre in formato esadecimale. È pensata per uso forense e per l'interrogazione di dati con finalità lecite.

### Strumenti necessari

*   **Java** (testato con java 21.0.3 2024-04-16 LTS)
*   **Python** (testato con Python 3.11.9)
*   [HexToCrypt15Key](https://github.com/Forenser-lab/HexToCrypt15Key)
*   [wa-crypt-tools](https://github.com/ElDavoo/wa-crypt-tools) (`wadecrypt.py`)
*   `main.py` (questo tool)

### Installazione Dipendenze

Eseguire i seguenti comandi per installare le librerie Python necessarie:

```bash
pip install sqlite3 matplotlib pandas numpy folium wordcloud textblob tk reportlab scikit-learn scipy nltk
```

### Procedura

#### 1. Conversione della Chiave

Convertire la chiave esadecimale (64 caratteri) in un file binario utilizzando lo script `HexToCrypt15Key.java`.

1.  Compilare il file Java:
    ```bash
    javac HexToCrypt15Key.java
    ```
2.  Eseguire la conversione:
    ```bash
    java HexToCrypt15Key [chiave_esadecimale]
    ```
    *Nota: Sostituire `[chiave_esadecimale]` con la chiave reale a 64 cifre.*

Verrà generato un file binario utilizzabile con lo strumento di decifrazione.

#### 2. Decifrazione del Database

Utilizzare lo strumento `wadecrypt` per decifrare il database `.crypt15`.

*   **Input richiesti:**
    *   `key` (file binario generato con HexToCrypt15Key)
    *   `msgstore.db.crypt15` (file cifrato)

Eseguire il seguente comando dalla cartella `wa-crypt-tools`:

```bash
python wadecrypt.py [percorso_chiave] [percorso_database_cifrato]
```

Esempio:
```bash
python wadecrypt.py "C:\key" "C:\user\desktop\msgstore.db.crypt15"
```

**Output:** `msgstore.db` (file SQLite decifrato)

#### 3. Verifica e Analisi del Database Decifrato

Una volta ottenuto il file `msgstore.db`:

1.  Avviare il tool di analisi:
    ```bash
    python main.py
    ```
2.  Caricare il database `msgstore.db` tramite l'interfaccia grafica.
