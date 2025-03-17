import os
import time
import hashlib
import subprocess
import logging
from logging import Formatter, StreamHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from fpdf import FPDF

# -------------------- CONFIGURAZIONE --------------------
# Cartella da monitorare per i file in ingresso
WATCH_DIRECTORY = '/latua/notaryfolder'
# Cartella dove salvare i PDF generati (output notarizzazione)
PDF_OUTPUT_DIRECTORY = '/cartelladelle/ricevute'
# File di log (assicurati che il percorso sia assoluto)
LOG_FILE = '/cartelladeilog/notaryser.log'

# Configurazione Revo CLI e notarizzazione:
REVO_CLI = '/mettiilpercorsodi/revo-cli'  # Se non è nel PATH, specifica il percorso completo
CONTRACT_ADDRESS = '8dbfe93530592d739014c0c391897b9afa928974'  # Indirizzo dello smart contract, usa questo o creane uno
SENDER_ADDRESS = 'iltuoindirizzorevo'         # Indirizzo del mittente
GAS_LIMIT = '25000'     # Modifica in base alle esigenze del contratto
GAS_PRICE = '0.00000001'  # Modifica se necessario
AMOUNT = '0'            # Generalmente 0 per operazioni di notarizzazione

# Assicurati che le cartelle di output esistano
if not os.path.exists(PDF_OUTPUT_DIRECTORY):
    os.makedirs(PDF_OUTPUT_DIRECTORY)
if not os.path.exists(os.path.dirname(LOG_FILE)):
    os.makedirs(os.path.dirname(LOG_FILE))

# -------------------- GESTORE DI LOG PERSONALIZZATO --------------------
class LineCountRotatingFileHandler(logging.FileHandler):
    """
    Gestore di log che ruota il file di log quando raggiunge un numero massimo di righe.
    """
    def __init__(self, filename, mode='a', max_lines=1000, backupCount=5, encoding=None, delay=False):
        self.max_lines = max_lines
        self.backupCount = backupCount
        self.line_count = 0
        self.terminator = "\n"
        super().__init__(filename, mode, encoding, delay)
        # Se il file esiste già , conta le righe
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                self.line_count = sum(1 for _ in f)

    def emit(self, record):
        try:
            msg = self.format(record)
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
            self.line_count += 1
            if self.line_count >= self.max_lines:
                self.doRollover()
        except Exception:
            self.handleError(record)

    def doRollover(self):
        self.stream.close()
        # Ruota i backup: sposta il file .1 in .2, .2 in .3, ecc.
        for i in range(self.backupCount - 1, 0, -1):
            sfn = f"{self.baseFilename}.{i}"
            dfn = f"{self.baseFilename}.{i+1}"
            if os.path.exists(sfn):
                if os.path.exists(dfn):
                    os.remove(dfn)
                os.rename(sfn, dfn)
        dfn = self.baseFilename + ".1"
        if os.path.exists(dfn):
            os.remove(dfn)
        os.rename(self.baseFilename, dfn)
        self.stream = self._open()
        self.line_count = 0

# -------------------- CONFIGURAZIONE DEI LOG --------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Handler per la console
ch = StreamHandler()
ch.setLevel(logging.INFO)
formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# Handler per il file con rotazione basata sulle righe
fh = LineCountRotatingFileHandler(LOG_FILE, max_lines=1000, backupCount=5)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)

logger.addHandler(ch)
logger.addHandler(fh)

# -------------------- FUNZIONI UTILI --------------------
def compute_file_hash(file_path, algorithm='sha256'):
    """Calcola l'hash del file e restituisce il risultato in formato esadecimale."""
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def wait_for_file_stability(file_path, interval=1, retries=5):
    """
    Attende che la dimensione del file rimanga stabile per 'interval' secondi.
    Ritorna True se il file e' stabile, False altrimenti.
    """
    previous_size = -1
    for _ in range(retries):
        current_size = os.path.getsize(file_path)
        if current_size == previous_size and current_size > 0:
            return True
        previous_size = current_size
        time.sleep(interval)
    return False

def notarize_file(file_hash):
    """
    Notarizza il file tramite il comando Revo CLI.
    Invece di inviare solo l'hash, crea un testo promozionale e lo converte in esadecimale.
    """
    # Crea il testo notarizzato
    notarization_text = f"File notarizzato con Revonotarizer (puoi personalizzare il testo) - hash del file: {file_hash}"
    # Converte il testo in formato esadecimale (UTF-8)
    data_hex = notarization_text.encode('utf-8').hex()
    
    cmd = [
        REVO_CLI,
        "sendtocontract",
        CONTRACT_ADDRESS,
        data_hex,    # Invia il testo notarizzato in esadecimale
        AMOUNT,
        GAS_LIMIT,
        GAS_PRICE,
        SENDER_ADDRESS,
        "true"       # Flag broadcast; modifica se necessario
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        notarization_output = result.stdout.strip()
        logger.info("Notarizzazione completata: %s", notarization_output)
        return notarization_output
    except subprocess.CalledProcessError as e:
        logger.error("Errore nella notarizzazione: %s", e.stderr)
        return None

def create_pdf_summary(file_path, file_hash, notarization_result):
    """
    Crea un PDF riassuntivo con le informazioni del file:
    - Nome del file
    - Dimensione in bytes
    - Timestamp dell'ultima modifica
    - Hash calcolato (in formato esadecimale)
    - Risultato della notarizzazione
    Il PDF viene salvato nella cartella PDF_OUTPUT_DIRECTORY.
    """
    file_stats = os.stat(file_path)
    file_name = os.path.basename(file_path)
    file_size = file_stats.st_size
    timestamp = time.ctime(file_stats.st_mtime)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Riassunto File Notarizzato", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"Nome File: {file_name}", ln=True)
    pdf.cell(200, 10, txt=f"Dimensione: {file_size} bytes", ln=True)
    pdf.cell(200, 10, txt=f"Timestamp: {timestamp}", ln=True)
    pdf.cell(200, 10, txt=f"Hash (hex): {file_hash}", ln=True)
    if notarization_result:
        pdf.cell(200, 10, txt=f"Risultato Notarizzazione: {notarization_result}", ln=True)
    else:
        pdf.cell(200, 10, txt="Notarizzazione fallita.", ln=True)

    pdf_output_filename = os.path.splitext(file_name)[0] + "_ricevuta.pdf"
    pdf_output_path = os.path.join(PDF_OUTPUT_DIRECTORY, pdf_output_filename)
    pdf.output(pdf_output_path)
    logger.info("PDF creato: %s", pdf_output_path)

# -------------------- GESTIONE DEGLI EVENTI --------------------
class FileEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Processa solo i file (non le cartelle)
        if not event.is_directory:
            logger.info("Nuovo file rilevato: %s", event.src_path)
            if wait_for_file_stability(event.src_path):
                file_hash = compute_file_hash(event.src_path)
                logger.info("Hash calcolato (hex): %s", file_hash)
                notarization_result = notarize_file(file_hash)
                create_pdf_summary(event.src_path, file_hash, notarization_result)
            else:
                logger.error("Il file %s non Ã¨ stabile dopo vari tentativi.", event.src_path)

# -------------------- ESECUZIONE --------------------
if __name__ == "__main__":
    event_handler = FileEventHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIRECTORY, recursive=False)
    observer.start()
    logger.info("Monitoraggio in corso nella cartella: %s", WATCH_DIRECTORY)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Interruzione richiesta. Arresto dell'osservatore.")
    observer.join()
