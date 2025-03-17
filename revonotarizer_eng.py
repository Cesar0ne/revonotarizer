import os
import time
import hashlib
import subprocess
import logging
from logging import Formatter, StreamHandler
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from fpdf import FPDF

# -------------------- CONFIGURATION --------------------
# Directory to monitor for incoming files
WATCH_DIRECTORY = '/your_input_directory/'
# Directory to save the generated PDFs (notarization output)
PDF_OUTPUT_DIRECTORY = '/your_receipts_directory/'
# Log file (make sure the path is absolute)
LOG_FILE = '/your_log_directory/notaryser.log'

# Revo CLI and notarization configuration:
REVO_CLI = '/your_revo_cli_directory/revo-cli'  # If not in PATH, specify the full path
CONTRACT_ADDRESS = '8dbfe93530592d739014c0c391897b9afa928974'  # Smart contract address; you can use this or one created by you
SENDER_ADDRESS = 'YourRevoAddress'         # Sender address
GAS_LIMIT = '25000'     # Modify according to contract requirements
GAS_PRICE = '0.00000001'  # Modify if necessary
AMOUNT = '0'            # Generally 0 for notarization operations

# Ensure that the output directories exist
if not os.path.exists(PDF_OUTPUT_DIRECTORY):
    os.makedirs(PDF_OUTPUT_DIRECTORY)
if not os.path.exists(os.path.dirname(LOG_FILE)):
    os.makedirs(os.path.dirname(LOG_FILE))

# -------------------- CUSTOM LOG HANDLER WITH ROTATION --------------------
class LineCountRotatingFileHandler(logging.FileHandler):
    """
    Log handler that rotates the log file when it reaches a maximum number of lines.
    """
    def __init__(self, filename, mode='a', max_lines=1000, backupCount=5, encoding=None, delay=False):
        self.max_lines = max_lines
        self.backupCount = backupCount
        self.line_count = 0
        self.terminator = "\n"
        super().__init__(filename, mode, encoding, delay)
        # If the file already exists, count the lines
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
        # Rotate backups: move file .1 to .2, .2 to .3, etc.
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

# -------------------- LOG CONFIGURATION --------------------
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Console handler
ch = StreamHandler()
ch.setLevel(logging.INFO)
formatter = Formatter('%(asctime)s - %(levelname)s - %(message)s')
ch.setFormatter(formatter)

# File handler with line-based rotation
fh = LineCountRotatingFileHandler(LOG_FILE, max_lines=1000, backupCount=5)
fh.setLevel(logging.INFO)
fh.setFormatter(formatter)

logger.addHandler(ch)
logger.addHandler(fh)

# -------------------- UTILITY FUNCTIONS --------------------
def compute_file_hash(file_path, algorithm='sha256'):
    """Computes the file hash and returns the result in hexadecimal format."""
    hash_func = hashlib.new(algorithm)
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_func.update(chunk)
    return hash_func.hexdigest()

def wait_for_file_stability(file_path, interval=1, retries=5):
    """
    Waits until the file size remains stable for 'interval' seconds.
    Returns True if the file is stable, False otherwise.
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
    Notarizes the file using the Revo CLI command.
    """
    # Create the notarization text
    notarization_text = f"File notarized with Revonotarizer (customize this text as desired) - file hash: {file_hash}"
    # Convert the text to hexadecimal format (UTF-8)
    data_hex = notarization_text.encode('utf-8').hex()
    
    cmd = [
        REVO_CLI,
        "sendtocontract",
        CONTRACT_ADDRESS,
        data_hex,    # Sends the notarized text in hexadecimal format
        AMOUNT,
        GAS_LIMIT,
        GAS_PRICE,
        SENDER_ADDRESS,
        "true"       # Broadcast flag; modify if necessary
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        notarization_output = result.stdout.strip()
        logger.info("Notarization completed: %s", notarization_output)
        return notarization_output
    except subprocess.CalledProcessError as e:
        logger.error("Error during notarization: %s", e.stderr)
        return None

def create_pdf_summary(file_path, file_hash, notarization_result):
    """
    Creates a PDF summary containing:
    - File name
    - File size (in bytes)
    - Last modified timestamp
    - Computed hash (in hexadecimal format)
    - Notarization result
    The PDF is saved in the PDF_OUTPUT_DIRECTORY.
    """
    file_stats = os.stat(file_path)
    file_name = os.path.basename(file_path)
    file_size = file_stats.st_size
    timestamp = time.ctime(file_stats.st_mtime)

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Arial", size=12)
    pdf.cell(200, 10, txt="Notarized File Summary", ln=True, align='C')
    pdf.ln(10)
    pdf.cell(200, 10, txt=f"File Name: {file_name}", ln=True)
    pdf.cell(200, 10, txt=f"File Size: {file_size} bytes", ln=True)
    pdf.cell(200, 10, txt=f"Timestamp: {timestamp}", ln=True)
    pdf.cell(200, 10, txt=f"Hash (hex): {file_hash}", ln=True)
    if notarization_result:
        pdf.cell(200, 10, txt=f"Notarization Result: {notarization_result}", ln=True)
    else:
        pdf.cell(200, 10, txt="Notarization failed.", ln=True)

    pdf_output_filename = os.path.splitext(file_name)[0] + "_receipt.pdf"
    pdf_output_path = os.path.join(PDF_OUTPUT_DIRECTORY, pdf_output_filename)
    pdf.output(pdf_output_path)
    logger.info("PDF created: %s", pdf_output_path)

# -------------------- EVENT HANDLING --------------------
class FileEventHandler(FileSystemEventHandler):
    def on_created(self, event):
        # Process only files (not directories)
        if not event.is_directory:
            logger.info("New file detected: %s", event.src_path)
            if wait_for_file_stability(event.src_path):
                file_hash = compute_file_hash(event.src_path)
                logger.info("Computed hash (hex): %s", file_hash)
                notarization_result = notarize_file(file_hash)
                create_pdf_summary(event.src_path, file_hash, notarization_result)
            else:
                logger.error("The file %s is not stable after several attempts.", event.src_path)

# -------------------- EXECUTION --------------------
if __name__ == "__main__":
    event_handler = FileEventHandler()
    observer = Observer()
    observer.schedule(event_handler, WATCH_DIRECTORY, recursive=False)
    observer.start()
    logger.info("Monitoring directory: %s", WATCH_DIRECTORY)
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
        logger.info("Shutdown requested. Stopping observer.")
    observer.join()
