# -*- coding: utf-8 -*-
import os
import sys
import json
import re
import socket
import platform
import subprocess
import logging
import datetime
import tempfile
import ssl

# Platform-specific imports
if platform.system() == "Windows":
    import winreg
else:
    winreg = None  # Not available on non-Windows platforms

# Optional imports with graceful fallback
try:
    import psutil
except ImportError:
    psutil = None
    logging.warning("psutil module not found. Some hardware info may be unavailable.")

from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import smtplib

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

import sys

# Constants
DE_EMAIL = os.environ.get("SMTP_SENDER", "")
EMAIL_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
TO_EMAIL = os.environ.get("SMTP_RECIPIENT", "")
SMTP_SERVER = os.environ.get("SMTP_SERVER", "")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))

def check_office_uninstall_registry():
    if winreg is None:
        return "Registro do Windows não disponível"
    office_products = []
    office_keywords = ["Office", "Microsoft 365", "Microsoft Office", "Office Professional", "Office Standard", "Office Home", "Office Business"]
    exclude_keywords = ["Teams"]
    uninstall_keys = [
        r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
        r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"
    ]
    for uninstall_key in uninstall_keys:
        try:
            reg_key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key)
            for i in range(winreg.QueryInfoKey(reg_key)[0]):
                try:
                    subkey_name = winreg.EnumKey(reg_key, i)
                    subkey = winreg.OpenKey(reg_key, subkey_name)
                    display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                    if any(keyword in display_name for keyword in office_keywords) and not any(exclude in display_name for exclude in exclude_keywords):
                        office_products.append(display_name)
                except FileNotFoundError:
                    continue
                except OSError:
                    continue
                except Exception:
                    continue
        except FileNotFoundError:
            continue
        except Exception:
            continue
    if office_products:
        return ", ".join(set(office_products))
    else:
        return "Microsoft Office não encontrado"

def get_physical_address_from_ipconfig():
    try:
        output = subprocess.check_output("ipconfig /all", shell=True, text=True, encoding='utf-8', errors='ignore')
        match = re.search(r"Physical Address[\. ]*:[ ]*([0-9A-Fa-f\-]{17})", output)
        if match:
            return match.group(1).upper()
    except Exception as e:
        logging.error(f"Error running ipconfig /all or parsing output: {e}")
    return None

def get_system_info():
    info = {
        "IP e Rede": [],
        "Sistema Operacional": {},
        "Hardware": {},
        "Microsoft Office": {}
    }
    hostname = socket.gethostname()
    info["IP e Rede"].append(f"Nome do Computador: {hostname}")

    try:
        import getpass
        user_name = getpass.getuser()
    except Exception:
        user_name = "N/A"
    info["Sistema Operacional"]["Utilizador"] = user_name

    try:
        domain = socket.getfqdn()
        hostname = socket.gethostname()
        if domain == hostname:
            domain = "N/A"
        else:
            domain = domain.partition('.')[2] if '.' in domain else "N/A"
    except Exception:
        domain = "N/A"
    info["IP e Rede"].append(f"Domínio: {domain}")

    physical_address = get_physical_address_from_ipconfig()
    if physical_address:
        info["IP e Rede"].append(f"Mac Address: {physical_address}")

    if platform.system() == "Windows" and psutil:
        try:
            mac_address = None
            for interface_name, interface_addresses in psutil.net_if_addrs().items():
                for addr in interface_addresses:
                    if addr.family == psutil.AF_LINK:
                        mac = addr.address
                        if mac and mac != "00:00:00:00:00:00":
                            mac_address = mac.upper()
                            break
                if mac_address:
                    break

            ip_address = None
            for interface_name, interface_addresses in psutil.net_if_addrs().items():
                for addr in interface_addresses:
                    if addr.family == socket.AF_INET and mac_address:
                        macs = [a.address.upper() for a in interface_addresses if a.family == psutil.AF_LINK]
                        if mac_address in macs:
                            ip_address = addr.address
                            break
                if ip_address:
                    break

            if ip_address:
                info["IP e Rede"].append(f"IPv4 Address: {ip_address}")

        except Exception as e:
            logging.error(f"Erro ao obter IP/MAC: {e}")
            info["IP e Rede"].append("Erro ao obter IP/MAC")

    info["Sistema Operacional"]["OS"] = f"{platform.system()} {platform.release()} {platform.version()}"
    info["Sistema Operacional"]["Arquitetura"] = platform.machine()

    if platform.system() == "Windows":
        try:
            cpu_info = subprocess.check_output("wmic cpu get name", shell=True).decode('utf-8').strip().split('\n')[-1]
            info["Hardware"]["Processador"] = cpu_info
        except Exception as e:
            logging.error(f"Erro ao obter info do processador: {e}")
            info["Hardware"]["Processador"] = "N/A"
        try:
            ram_bytes = subprocess.check_output("wmic ComputerSystem get TotalPhysicalMemory", shell=True).decode('utf-8').strip().split('\n')[-1]
            ram_gb = round(int(ram_bytes) / (1024 ** 3), 2)
            info["Hardware"]["RAM (GB)"] = ram_gb
            ram_details = subprocess.check_output("wmic memorychip get Capacity,Speed,Manufacturer,PartNumber", shell=True).decode('utf-8').strip()
            info["Hardware"]["RAM Details"] = ram_details
        except Exception as e:
            logging.error(f"Erro ao obter info da RAM: {e}")
            info["Hardware"]["RAM (GB)"] = "N/A"
            info["Hardware"]["RAM Details"] = "N/A"
        try:
            disk_bytes = subprocess.check_output("wmic logicaldisk where DeviceID='C:' get Size", shell=True).decode('utf-8').strip().split('\n')[-1]
            disk_gb = round(int(disk_bytes) / (1024 ** 3), 2)
            info["Hardware"]["Disk C: (GB)"] = disk_gb
            disk_details = subprocess.check_output("wmic diskdrive get Model,SerialNumber,Size", shell=True).decode('utf-8').strip()
            info["Hardware"]["Disk Details"] = disk_details
        except Exception as e:
            logging.error(f"Erro ao obter info do disco: {e}")
            info["Hardware"]["Disk C: (GB)"] = "N/A"
            info["Hardware"]["Disk Details"] = "N/A"
        try:
            motherboard_info = subprocess.check_output("wmic baseboard get Manufacturer,Product,SerialNumber", shell=True).decode('utf-8').strip().split('\n')
            if len(motherboard_info) >= 2:
                headers = motherboard_info[0].split()
                values = motherboard_info[1].split()
                mb_manufacturer = values[0] if len(values) > 0 else "N/A"
                mb_product = values[1] if len(values) > 1 else "N/A"
                mb_serial = values[2] if len(values) > 2 else "N/A"
                info["Hardware"]["Motherboard Manufacturer"] = mb_manufacturer
                info["Hardware"]["Motherboard Product"] = mb_product
                info["Hardware"]["Motherboard SerialNumber"] = mb_serial
            else:
                info["Hardware"]["Motherboard Manufacturer"] = "N/A"
                info["Hardware"]["Motherboard Product"] = "N/A"
                info["Hardware"]["Motherboard SerialNumber"] = "N/A"
        except Exception as e:
            logging.error(f"Erro ao obter info da motherboard: {e}")
            info["Hardware"]["Motherboard Manufacturer"] = "N/A"
            info["Hardware"]["Motherboard Product"] = "N/A"
            info["Hardware"]["Motherboard SerialNumber"] = "N/A"
        try:
            gpu_info = subprocess.check_output("wmic path win32_VideoController get Name,DriverVersion", shell=True).decode('utf-8').strip()
            info["Hardware"]["Graphics"] = gpu_info
        except Exception as e:
            logging.error(f"Erro ao obter info da GPU: {e}")
            info["Hardware"]["Graphics"] = "N/A"

    if platform.system() == "Windows":
        office_version = check_office_uninstall_registry()
        info["Microsoft Office"]["Versão"] = office_version

    return info

def hardware_info_changed(current_hardware_info, filepath="hardware_info.json"):
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            previous_hardware_info = json.load(f)
        logging.info("Arquivo hardware_info.json carregado com sucesso.")
    except FileNotFoundError:
        logging.info("Arquivo hardware_info.json não encontrado. Considerando como primeira execução.")
        previous_hardware_info = None
    except Exception as e:
        logging.error(f"Erro ao ler arquivo de hardware anterior: {e}")
        previous_hardware_info = None

    if previous_hardware_info != current_hardware_info:
        return True
    else:
        logging.info("Nenhuma alteração detectada no hardware.")
    return False

def update_hardware_info_file(current_hardware_info, filepath="hardware_info.json"):
    try:
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(current_hardware_info, f, indent=4)
        logging.info("Arquivo hardware_info.json atualizado com as informações atuais.")
    except Exception as e:
        logging.error(f"Erro ao salvar arquivo de hardware: {e}")

def send_email_with_attachment(subject, body, to_email, from_email, password, attachment_path, smtp_server=SMTP_SERVER, smtp_port=SMTP_PORT):
    if not all((to_email, from_email, password, smtp_server)):
        logging.error(
            "Configuração SMTP incompleta. Defina SMTP_SENDER, SMTP_RECIPIENT, "
            "SMTP_PASSWORD e SMTP_SERVER."
        )
        return False

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'plain'))

    try:
        with open(attachment_path, "rb") as attachment:
            part = MIMEBase("application", "octet-stream")
            part.set_payload(attachment.read())
        encoders.encode_base64(part)
        part.add_header(
            "Content-Disposition",
            f"attachment; filename= {os.path.basename(attachment_path)}",
        )
        msg.attach(part)
        logging.info(f"Arquivo {attachment_path} anexado ao e-mail.")
    except Exception as e:
        logging.error(f"Erro ao anexar o arquivo: {e}")
        return False

    try:
        with smtplib.SMTP(smtp_server, smtp_port, timeout=30) as server:
            server.starttls(context=ssl.create_default_context())
            server.login(from_email, password)
            server.send_message(msg)
        logging.info("E-mail enviado com sucesso!")
        return True
    except Exception as e:
        logging.error(f"Erro ao enviar e-mail: {e}")
        return False

def create_weekly_task(task_name, script_path):
    try:
        import getpass
        current_user = getpass.getuser()
        command = [
            'schtasks',
            '/Create',
            '/SC', 'WEEKLY',
            '/D', 'MON',
            '/ST', '10:00',
            '/TN', task_name,
            '/TR', f'\"{sys.executable}\" \"{script_path}\" --run-task',
            '/RU', current_user,
            '/F'
        ]
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Scheduled task '{task_name}' created successfully.")
        else:
            logging.error(f"Failed to create scheduled task. Error:\n{result.stderr}")
    except Exception as e:
        logging.error(f"Exception occurred while creating scheduled task: {e}")

def task_exists(task_name):
    try:
        result = subprocess.run(['schtasks', '/Query', '/TN', task_name], capture_output=True, text=True)
        return result.returncode == 0
    except Exception as e:
        logging.error(f"Exception occurred while checking scheduled task existence: {e}")
        return False

def has_run_this_week(marker_file):
    if not os.path.exists(marker_file):
        return False
    try:
        with open(marker_file, 'r') as f:
            last_run_str = f.read().strip()
            current_week = datetime.datetime.now().strftime('%Y-%W')
            return last_run_str == current_week
    except Exception as e:
        logging.error(f"Error reading marker file: {e}")
        return False

def update_run_marker(marker_file):
    current_week = datetime.datetime.now().strftime('%Y-%W')
    try:
        with open(marker_file, 'w') as f:
            f.write(current_week)
    except Exception as e:
        logging.error(f"Error writing marker file: {e}")

def run_task_if_first_login_of_week():
    marker_file = os.path.join(tempfile.gettempdir(), '.task_last_run_week')
    if has_run_this_week(marker_file):
        logging.info("Task has already run this week. Exiting.")
        return
    # Determine executable path depending on frozen state
    if getattr(sys, 'frozen', False):
        exe_path = os.path.join(sys._MEIPASS, "gEasy_pcinventory-client.exe")
    else:
        exe_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "gEasy_pcinventory-client.exe")
    if not os.path.exists(exe_path):
        logging.error(f"Executable not found at {exe_path}. Cannot run task.")
        return
    try:
        subprocess.run([exe_path], check=True)
        update_run_marker(marker_file)
        logging.info("Task executed successfully and marker updated.")
    except Exception as e:
        logging.error(f"Failed to run the executable: {e}")

TARGET_FOLDER = r"C:\\Tecnico Giscon\\GInventoryPc\\"
EXE_FILENAME = "gEasy_pcinventory-client.exe"
EXE_SOURCE_PATH = os.path.join(TARGET_FOLDER, EXE_FILENAME)
EXE_DEST_PATH = os.path.join(TARGET_FOLDER, EXE_FILENAME)

import hashlib
import shutil

def files_are_identical(file1, file2):
    try:
        if os.path.getsize(file1) != os.path.getsize(file2):
            return False
        # Optional: compare hash for more certainty
        hash1 = hashlib.md5()
        hash2 = hashlib.md5()
        with open(file1, 'rb') as f1, open(file2, 'rb') as f2:
            while True:
                b1 = f1.read(4096)
                b2 = f2.read(4096)
                if not b1 and not b2:
                    break
                if b1 != b2:
                    return False
                hash1.update(b1)
                hash2.update(b2)
        return hash1.digest() == hash2.digest()
    except Exception as e:
        logging.error(f"Error comparing files {file1} and {file2}: {e}")
        return False

def copy_executable_to_target_folder():
    # Adjust source path if running as frozen executable
    if getattr(sys, 'frozen', False):
        # When frozen, the executable is the running executable itself
        source_path = sys.executable
    else:
        source_path = EXE_SOURCE_PATH

    if not os.path.exists(source_path):
        logging.error(f"Source executable not found at {source_path}. Cannot copy.")
        return False
    if not os.path.exists(TARGET_FOLDER):
        try:
            os.makedirs(TARGET_FOLDER)
            logging.info(f"Created target folder: {TARGET_FOLDER}")
        except Exception as e:
            logging.error(f"Failed to create target folder {TARGET_FOLDER}: {e}")
            return False
    if os.path.exists(EXE_DEST_PATH):
        if files_are_identical(source_path, EXE_DEST_PATH):
            logging.info(f"Executable already exists at {EXE_DEST_PATH} and is identical. Skipping copy.")
            return True
        else:
            logging.info(f"Executable exists at {EXE_DEST_PATH} but differs from source. Will attempt to overwrite.")
    max_retries = 15
    for attempt in range(max_retries):
        try:
            shutil.copy2(source_path, EXE_DEST_PATH)
            logging.info(f"Copied {EXE_FILENAME} to {TARGET_FOLDER}")
            return True
        except (PermissionError, OSError) as e:
            logging.warning(f"PermissionError or OSError on copying file, retrying... ({attempt+1}/{max_retries}) - {e}")
            time.sleep(3)
        except Exception as e:
            logging.error(f"Error copying file: {e}")
            break
    logging.error(f"Failed to copy {EXE_FILENAME} after {max_retries} attempts due to file lock or other errors.")
    return False

def main():
    # Copy executable to target folder before proceeding
    copy_executable_to_target_folder()

    # Adjust current working directory if running as frozen executable
    if getattr(sys, 'frozen', False):
        os.chdir(sys._MEIPASS)
    system_info = get_system_info()
    # Save files in the target folder as requested
    filename = os.path.join(TARGET_FOLDER, "system_info.txt")
    hardware_info_file = os.path.join(TARGET_FOLDER, "hardware_info.json")

    if hardware_info_changed(system_info.get("Hardware", {}), filepath=hardware_info_file):
        try:
            with open(filename, "w", encoding="utf-8") as f:
                for category, data in system_info.items():
                    f.write(f"[{category}]\n")
                    if isinstance(data, list):
                        for item in data:
                            f.write(f"{item}\n")
                    else:
                        for key, value in data.items():
                            f.write(f"{key}: {value}\n")
                    f.write("\n")
            logging.info(f"Arquivo {filename} criado com as informações do sistema.")
        except Exception as e:
            logging.error(f"Erro ao criar arquivo de informações do sistema: {e}")
            return

        subject = f"{socket.getfqdn()} - {socket.gethostname()}"
        body = "Alteração detectada no hardware. Segue em anexo o arquivo com as informações do sistema."

        if send_email_with_attachment(subject, body, TO_EMAIL, DE_EMAIL, EMAIL_PASSWORD, filename):
            update_hardware_info_file(system_info.get("Hardware", {}), filepath=hardware_info_file)
        else:
            logging.error("Falha ao enviar o e-mail.")
    else:
        # Suppress info logs about no changes
        pass

if __name__ == "__main__":
    import traceback
    import time
    import sys
    # Copy executable to target folder before any scheduled task logic
    copy_executable_to_target_folder()

    task_name = "gEasy_pcinventory_client_Primeiro_login_da_semana"
    script_path = os.path.abspath(sys.argv[0])
    try:
        if not task_exists(task_name):
            create_weekly_task(task_name, script_path)
        run_task_if_first_login_of_week()
        main()
    except Exception:
        log_path = os.path.join(os.path.dirname(os.path.abspath(sys.argv[0])), "error_log.txt")
        with open(log_path, "w", encoding="utf-8") as log_file:
            log_file.write("An error occurred:\n")
            log_file.write(traceback.format_exc())
        logging.error(f"An error occurred. See the log file at {log_path}")
        # Removed input prompts to avoid user interaction in executable mode

    # Removed input prompts to avoid user interaction in executable mode

    # Removed pause to avoid user interaction in executable mode
