# Whatsapp_Forensic
Guida alla Decifrazione e Analisi del Database .crypt15 
Questa guida descrive il processo per decifrare un database cifrato (msgstore.db.crypt15) 
utilizzando una chiave a 64 cifre in formato esadecimale. È pensata per uso forense o per il 
recupero di dati con fi nalità lecite. 
 
Strumenti necessari:  
•  java (testato con java 21.0.3 2024-04-16 LTS) 
•  python (testato con Python 3.11.9) 
•  HexToCrypt15Key (https://github.com/Forenser-lab/HexToCrypt15Key) 
•  wadecrypt.py (https://github.com/ElDavoo/wa-crypt-tools) 
•  wa_forensic.py 
Comandi per installare le librerie python necessarie:  
•  pip install sqlite3 
•  pip install matplotlib 
•  pip install pandas 
•  pip install numpy 
•  pip install folium 
•  pip install wordcloud 
•  pip install textblob 
•  pip install tk 
 
 
1. Conversione della Chiave 
Convertire la chiave esadecimale (64 caratteri) in un fi le binario utilizzando lo script 
HexToCrypt15Key.java. 
Compilare il fi le Java e avviare la conversione della chiave.  
•  Eseguire i seguenti comandi: 
o  javac HexToCrypt15Key.java 
o  java HexToCrypt15Key [chiave_esadecimale] 
•  Verrà generato un fi le binario utilizzabile con lo strumento di decifrazione. 
•  Nota: Sostituire [chiave_esadecimale] con la chiave reale a 64 cifre. 
 
2. Decifrazione del Database Utilizzare lo strumento wadecrypt per decifrare il database .crypt15. 
•  Input richiesti: 
o  key (fi le binario generato  con HexToCrypt15Key) 
o  msgstore.db.crypt15 (fi le cifrato) 
•  Eseguire il seguente comando dalla cartella .\wa-crypt-tools-main\wa-crypt-
tools-main\src\wa_crypt_tools: 
o  python wadecrypt.py [percorso della chiave key] [percorso del database cifrato] 
o  Es. python wadecrypt.py “C:\key” “C:\user\desktop\msgstore.db.crypt15” 
•  Output: msgstore.db (fi le SQLite decifrato) 
 
3. Verifi ca e Analisi del Database Decifrato  
Una volta ottenuto il fi le msgstore.db: 
•  Eseguire lo script python con il seguente comando: 
o  python wa_forensic.py --db-path [percorso del database decriptato]  
o  Es.  python wa_forensic.py --db-path “C:\user\desktop\msgstore.db” 
