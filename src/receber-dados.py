import poplib
import email
from email.policy import default
import os
import logging
import re
import pyodbc
import json
import getpass
from datetime import datetime

POP3_SERVER = os.environ.get("POP3_SERVER", "")
POP3_PORT = int(os.environ.get("POP3_PORT", "995"))
EMAIL_ACCOUNT = os.environ.get("POP3_USER", "")
EMAIL_PASSWORD = os.environ.get("POP3_PASSWORD", "")

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SAVE_BASE_DIR = os.environ.get("INVENTORY_SAVE_DIR", os.path.join(PROJECT_ROOT, "received"))

# Default path for credentials JSON file
CREDENTIALS_FILE = os.environ.get("DB_CREDENTIALS_FILE", os.path.join(PROJECT_ROOT, "db_credentials.json"))

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def input_and_save_db_credentials():
    print("Enter database connection credentials:")
    server = input("SQL Server (e.g. LAPTOP-RAR92I2N\\SQLEXPRESS): ").strip()
    database = input("Database name (e.g. Pc-Inventory): ").strip()
    user = input("Username (e.g. admin): ").strip()
    password = getpass.getpass("Password: ")

    credentials = {
        "server": server,
        "database": database,
        "user": user,
        "password": password
    }

    with open(CREDENTIALS_FILE, "w") as f:
        json.dump(credentials, f, indent=4)
    print(f"Credentials saved to {CREDENTIALS_FILE}")

def load_db_credentials():
    if not os.path.exists(CREDENTIALS_FILE):
        print(f"Credentials file {CREDENTIALS_FILE} not found. Please enter credentials.")
        input_and_save_db_credentials()

    with open(CREDENTIALS_FILE, "r") as f:
        credentials = json.load(f)
    return credentials

def extract_mac_address(text):
    mac_regex = r'([0-9A-Fa-f]{2}[:-]){5}([0-9A-Fa-f]{2})'
    match = re.search(mac_regex, text)
    if match:
        return match.group(0).replace(":", "-").lower()
    return None

def parse_system_info(file_path):
    data = {
        "computer_name": None,
        "domain": None,
        "Ipv4_address": None,
        "mac_address": None,
        "os": None,
        "architecture": None,
        "processor": None,
        "ram_gb": None,
        "ram_details": None,
        "disk_c_gb": None,
        "disk_details": None,
        "motherboard_manufacturer": None,
        "motherboard_product": None,
        "motherboard_serialnumber": None,
        "graphics": None,
        "microsoft_office_version": None,
    }
    
    try:
        # Read the file content
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        
        
        # Direct extraction of key fields using simple string operations
        
        # MAC Address
        if "Physical Address (from ipconfig):" in content:
            mac_start = content.find("Physical Address (from ipconfig):") + len("Physical Address (from ipconfig):")
            mac_end = content.find("[", mac_start)
            if mac_end == -1:  # If no section follows
                mac_address = content[mac_start:].strip()
            else:
                mac_address = content[mac_start:mac_end].strip()
            data["mac_address"] = mac_address.lower()
        
        # Motherboard SerialNumber
        if "Motherboard SerialNumber:" in content:
            sn_start = content.find("Motherboard SerialNumber:") + len("Motherboard SerialNumber:")
            sn_end = content.find("Graphics:", sn_start)
            if sn_end == -1:
                sn_end = content.find("[", sn_start)
            if sn_end == -1:  # If no section follows
                motherboard_sn = content[sn_start:].strip()
            else:
                motherboard_sn = content[sn_start:sn_end].strip()
            data["motherboard_serialnumber"] = motherboard_sn
        
        # Computer Name
        if "Nome do Computador:" in content:
            name_start = content.find("Nome do Computador:") + len("Nome do Computador:")
            name_end = content.find("Domínio:", name_start)
            if name_end == -1:
                name_end = content.find("[", name_start)
            computer_name = content[name_start:name_end].strip()
            data["computer_name"] = computer_name
        
        # Domain
        if "Domínio:" in content:
            domain_start = content.find("Domínio:") + len("Domínio:")
            domain_end = content.find("Mac Address", domain_start)
            if domain_end == -1:
                domain_end = content.find("[", domain_start)
            domain = content[domain_start:domain_end].strip()
            data["domain"] = domain
            
        # Mac Address  
        if "Mac Address:" in content:
            mac_start = content.find("Mac Address:") + len("Mac Address:")
            mac_end = content.find("IPv4 Address", mac_start)
            if mac_end == -1:
                mac_end = content.find("[", mac_start)
            mac = content[mac_start:mac_end].strip()
            data["mac_address"] = mac
            
        # IPv4 Address
        if "IPv4 Address:" in content:
            ipv4_start = content.find("IPv4 Address:") + len("IPv4 Address:")
            ipv4_end = content.find("[", ipv4_start)
            if ipv4_end == -1:
                ipv4_address = content[ipv4_start:].strip()
            else:
                ipv4_address = content[ipv4_start:ipv4_end].strip()
            data["ipv4_address"] = ipv4_address
        
        # OS
        if "OS:" in content:
            os_start = content.find("OS:") + len("OS:")
            os_end = content.find("Arquitetura:", os_start)
            if os_end == -1:
                os_end = content.find("[", os_start)
            os_value = content[os_start:os_end].strip()
            data["os"] = os_value
        
        # Architecture
        if "Arquitetura:" in content:
            arch_start = content.find("Arquitetura:") + len("Arquitetura:")
            arch_end = content.find("[", arch_start)
            architecture = content[arch_start:arch_end].strip()
            data["architecture"] = architecture
        
        # Processor
        if "Processador:" in content:
            proc_start = content.find("Processador:") + len("Processador:")
            proc_end = content.find("RAM (GB):", proc_start)
            processor = content[proc_start:proc_end].strip()
            data["processor"] = processor
        
        # RAM GB
        if "RAM (GB):" in content:
            ram_start = content.find("RAM (GB):") + len("RAM (GB):")
            ram_end = content.find("RAM Details:", ram_start)
            ram_gb = content[ram_start:ram_end].strip()
            data["ram_gb"] = ram_gb
        
        # RAM Details
        if "RAM Details:" in content:
            ram_details_start = content.find("RAM Details:") + len("RAM Details:")
            ram_details_end = content.find("Disk C: (GB):", ram_details_start)
            ram_details = content[ram_details_start:ram_details_end].strip()
            data["ram_details"] = ram_details
        
        # Disk C GB
        if "Disk C: (GB):" in content:
            disk_start = content.find("Disk C: (GB):") + len("Disk C: (GB):")
            disk_end = content.find("Disk Details:", disk_start)
            disk_c_gb = content[disk_start:disk_end].strip()
            data["disk_c_gb"] = disk_c_gb
        
        # Disk Details
        if "Disk Details:" in content:
            disk_details_start = content.find("Disk Details:") + len("Disk Details:")
            disk_details_end = content.find("Motherboard Manufacturer:", disk_details_start)
            disk_details = content[disk_details_start:disk_details_end].strip()
            data["disk_details"] = disk_details
        
        # Motherboard Manufacturer
        if "Motherboard Manufacturer:" in content:
            mfr_start = content.find("Motherboard Manufacturer:") + len("Motherboard Manufacturer:")
            mfr_end = content.find("Motherboard Product:", mfr_start)
            motherboard_manufacturer = content[mfr_start:mfr_end].strip()
            data["motherboard_manufacturer"] = motherboard_manufacturer
        
        # Motherboard Product
        if "Motherboard Product:" in content:
            prod_start = content.find("Motherboard Product:") + len("Motherboard Product:")
            prod_end = content.find("Motherboard SerialNumber:", prod_start)
            motherboard_product = content[prod_start:prod_end].strip()
            data["motherboard_product"] = motherboard_product
        
        # Graphics
        if "Graphics:" in content:
            graphics_start = content.find("Graphics:") + len("Graphics:")
            graphics_end = content.find("[Microsoft Office]", graphics_start)
            if graphics_end == -1:
                graphics_end = len(content)
            graphics = content[graphics_start:graphics_end].strip()
            data["graphics"] = graphics
        
        # Microsoft Office Version
        if "Versão:" in content:
            version_start = content.find("Versão:") + len("Versão:")
            version_end = len(content)
            office_version = content[version_start:version_end].strip()
            data["microsoft_office_version"] = office_version
        
        
    except Exception as e:
        import traceback
    
    return data

def get_db_connection():
    credentials = load_db_credentials()
    required = ("server", "database", "user", "password")
    missing = [key for key in required if not credentials.get(key)]
    if missing:
        raise ValueError(
            "Faltam campos obrigat?rios em db_credentials.json: "
            + ", ".join(missing)
        )

    installed_drivers = pyodbc.drivers()
    preferred_drivers = (
        "ODBC Driver 18 for SQL Server",
        "ODBC Driver 17 for SQL Server",
        "ODBC Driver 13 for SQL Server",
    )
    requested_driver = os.environ.get("DB_DRIVER") or credentials.get("driver")
    driver = requested_driver or next(
        (name for name in preferred_drivers if name in installed_drivers),
        None,
    )
    if not driver or driver not in installed_drivers:
        raise RuntimeError(
            "N?o foi encontrado um driver ODBC instalado para SQL Server. "
            "Instale o ODBC Driver 17 ou 18 e, se necess?rio, defina DB_DRIVER."
        )

    def odbc_value(value):
        return "{" + str(value).replace("}", "}}") + "}"

    conn_str = (
        f"DRIVER={odbc_value(driver)};"
        f"SERVER={odbc_value(credentials['server'])};"
        f"DATABASE={odbc_value(credentials['database'])};"
        f"UID={odbc_value(credentials['user'])};"
        f"PWD={odbc_value(credentials['password'])};"
        "Encrypt=yes;TrustServerCertificate=no;"
    )
    return pyodbc.connect(conn_str)

def test_db_connection():
    """Test database connection and handle failures"""
    max_retries = 3
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            conn = get_db_connection()
            conn.close()
            logging.info("Database connection successful")
            return True
        except Exception as e:
            logging.error(f"Database connection failed (attempt {retry_count + 1}/{max_retries}): {e}")
            retry_count += 1
            
            if retry_count < max_retries:
                answer = input("Conecção para a base de dados falhou. Tentar novamente? (y/n): ").strip().lower()
                if answer == "y":
                    input_and_save_db_credentials()
                else:
                    print("Retrying with current credentials...")
            else:
                print("Maximum retry attempts reached. Database operations will be skipped.")
                return False
    
    return False

def insert_historico(cursor, data, received_datetime):
    sql = """
    INSERT INTO historico (
       nome, dominio, ipv4, mac_address, os, arquitetura,
            processador, ram_gb, ram_det, disco_c_gb, disco_det,
            mb_produtor, mb_produto, mb_serialnumber,
            grafica, office, data_e_hora
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(sql, (
        data["computer_name"], data["domain"], data["ipv4_address"], data["mac_address"],
        data["os"], data["architecture"], data["processor"], data["ram_gb"],
        data["ram_details"], data["disk_c_gb"], data["disk_details"],
        data["motherboard_manufacturer"], data["motherboard_product"], data["motherboard_serialnumber"],
        data["graphics"], data["microsoft_office_version"], received_datetime
    ))

def insert_or_update_atual(cursor, data, received_datetime):
    # Validate mac_address and motherboard_serialnumber are not None or empty
    mac_address = data["mac_address"]
    motherboard_serialnumber = data.get("motherboard_serialnumber")
    
    if not mac_address and not motherboard_serialnumber:
        # Log and skip instead of raising error
        logging.warning("Both mac_address and motherboard_serialnumber are missing or empty. Skipping insert/update.")
        return

    # First check if a record exists with the MAC address or motherboard serial number
    sql_check = """
    SELECT COUNT(*) FROM atual WHERE 
    (CAST(mac_address AS VARCHAR(255)) = ? AND mac_address IS NOT NULL) OR 
    (CAST(mb_serialnumber AS VARCHAR(255)) = ? AND mb_serialnumber IS NOT NULL)
    """
    cursor.execute(sql_check, (mac_address, motherboard_serialnumber))
    exists = cursor.fetchone()[0] > 0
    
    if exists:
        # Update existing record
        sql_update = """
        UPDATE atual SET
            nome = ?, dominio = ?, ipv4 = ?, os = ?, arquitetura = ?,
            processador = ?, ram_gb = ?, ram_det = ?, disco_c_gb = ?, disco_det = ?,
            mb_produtor = ?, mb_produto = ?, mb_serialnumber = ?, grafica = ?,
            office = ?, data_e_hora = ?
        WHERE (CAST(mac_address AS VARCHAR(255)) = ? AND mac_address IS NOT NULL) OR 
              (CAST(mb_serialnumber AS VARCHAR(255)) = ? AND mb_serialnumber IS NOT NULL)
        """
        cursor.execute(sql_update, (
            data["computer_name"], data["domain"], data["ipv4_address"], data["os"], data["architecture"],
            data["processor"], data["ram_gb"], data["ram_details"], data["disk_c_gb"], data["disk_details"],
            data["motherboard_manufacturer"], data["motherboard_product"], data["motherboard_serialnumber"],
            data["graphics"], data["microsoft_office_version"], received_datetime,
           data["mac_address"], motherboard_serialnumber
        ))
        logging.info(f"Updated existing record in 'atual' table for MAC: {mac_address} or MB_SN: {motherboard_serialnumber}")
    else:
        # Insert new record
        sql_insert = """
        INSERT INTO atual (
            nome, dominio, ipv4, mac_address, os, arquitetura,
            processador, ram_gb, ram_det, disco_c_gb, disco_det,
            mb_produtor, mb_produto, mb_serialnumber,
            grafica, office, data_e_hora
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        cursor.execute(sql_insert, (
            data["computer_name"], data["domain"], data["ipv4_address"], data["mac_address"],
            data["os"], data["architecture"], data["processor"], data["ram_gb"],
            data["ram_details"], data["disk_c_gb"], data["disk_details"],
            data["motherboard_manufacturer"], data["motherboard_product"], data["motherboard_serialnumber"],
            data["graphics"], data["microsoft_office_version"], received_datetime
        ))
        logging.info(f"Inserted new record in 'atual' table for MAC: {mac_address} or MB_SN: {motherboard_serialnumber}")

def pop3_fetch_and_save():
    if not all((POP3_SERVER, EMAIL_ACCOUNT, EMAIL_PASSWORD)):
        logging.error("Configura??o POP3 incompleta. Defina POP3_SERVER, POP3_USER e POP3_PASSWORD.")
        return

    try:
        mail = poplib.POP3_SSL(POP3_SERVER, POP3_PORT, timeout=30)
        mail.user(EMAIL_ACCOUNT)
        mail.pass_(EMAIL_PASSWORD)
        num_messages = len(mail.list()[1])
        logging.info(f"POP3: Number of messages in mailbox: {num_messages}")
        for i in range(num_messages, 0, -1):
            response, lines, octets = mail.retr(i)
            msg_content = b"\r\n".join(lines)
            msg = email.message_from_bytes(msg_content, policy=default)
            subject = msg.get("Subject", "")
            logging.info(f"POP3: Checking email with subject: {subject}")
            sanitized_subject = "".join(c for c in subject if c.isalnum() or c in (" ", "_", "-")).rstrip()
            if not sanitized_subject:
                sanitized_subject = "No_Subject"
            save_dir = os.path.join(SAVE_BASE_DIR, sanitized_subject)
            os.makedirs(save_dir, exist_ok=True)
            for part in msg.iter_attachments():
                filename = part.get_filename()
                if filename:
                    content = part.get_content()
                    base_filename = filename
                    filepath = os.path.join(save_dir, base_filename)
                    counter = 1
                    while os.path.exists(filepath):
                        name, ext = os.path.splitext(base_filename)
                        new_filename = f"{name}_{counter}{ext}"
                        filepath = os.path.join(save_dir, new_filename)
                        counter += 1
                    with open(filepath, "wb") as f:
                        if isinstance(content, str):
                            f.write(content.encode('utf-8'))
                        else:
                            f.write(content)
                    logging.info(f"Attachment saved: {filepath}")

                    # Parse the saved file and insert/update database
                    try:
                        data = parse_system_info(filepath)
                        received_datetime = datetime.now()







                        with get_db_connection() as conn:
                            with conn.cursor() as cursor:
                                insert_historico(cursor, data, received_datetime)
                                insert_or_update_atual(cursor, data, received_datetime)
                                conn.commit()
                        logging.info(f"Database updated for file: {filepath}")
                        try:
                            os.remove(filepath)
                            logging.info(f"Deleted attachment file after database update: {filepath}")
                        except Exception as e:
                            logging.error(f"Failed to delete attachment file {filepath}: {e}")
                    except Exception as e:
                        print("erro ao inserir")

            # Mark the message for deletion after processing
            mail.dele(i)

        mail.quit()
    except Exception as e:
        logging.error(f"POP3: Exception: {e}")

if __name__ == "__main__":
    if test_db_connection():
        pop3_fetch_and_save()
    else:
        print("Database connection failed after multiple attempts. Exiting program.")
