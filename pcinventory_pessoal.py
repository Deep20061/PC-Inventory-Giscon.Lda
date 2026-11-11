# -*- coding: utf-8 -*-
import os
import re
import socket
import platform
import subprocess
import logging

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

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def check_office_uninstall_registry():
    """
    Checks the Windows Registry for installed Microsoft Office products.
    """
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
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, uninstall_key) as reg_key:
                for i in range(winreg.QueryInfoKey(reg_key)[0]):
                    try:
                        subkey_name = winreg.EnumKey(reg_key, i)
                        with winreg.OpenKey(reg_key, subkey_name) as subkey:
                            display_name, _ = winreg.QueryValueEx(subkey, "DisplayName")
                            if any(keyword in display_name for keyword in office_keywords) and not any(exclude in display_name for exclude in exclude_keywords):
                                office_products.append(display_name)
                    except (FileNotFoundError, OSError):
                        continue
        except FileNotFoundError:
            continue
    if office_products:
        return ", ".join(sorted(set(office_products)))
    else:
        return "Microsoft Office não encontrado"

def get_physical_address_from_ipconfig():
    """
    Gets the physical address (MAC) from the 'ipconfig /all' command output.
    """
    try:
        output = subprocess.check_output("ipconfig /all", shell=True, text=True, encoding='utf-8', errors='ignore')
        # It looks for a block that has an IPv4 address to be more certain it's an active adapter.
        for block in output.split('\n\n'):
            if 'Physical Address' in block and 'IPv4 Address' in block:
                match = re.search(r"Physical Address[\. ]*:[ ]*([0-9A-Fa-f\-]{17})", block)
                if match:
                    return match.group(1).upper()
    except Exception as e:
        logging.error(f"Error running ipconfig /all or parsing output: {e}")
    return None

def get_system_info():
    """
    Collects detailed system information.
    """
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
        # Use fqdn and split to get domain if it exists
        fqdn = socket.getfqdn()
        if '.' in fqdn and fqdn.lower() != hostname.lower():
            domain = fqdn.split('.', 1)[1]
        else:
            domain = "N/A (não está em um domínio)"
    except Exception:
        domain = "N/A"
    info["IP e Rede"].append(f"Domínio: {domain}")

    physical_address = get_physical_address_from_ipconfig()
    
    if not physical_address and psutil:
        try:
            for interface, addrs in psutil.net_if_addrs().items():
                for addr in addrs:
                    if addr.family == psutil.AF_LINK and addr.address and addr.address != "00:00:00:00:00:00":
                        if psutil.net_if_stats()[interface].isup:
                            physical_address = addr.address.upper().replace(':', '-')
                            break
                if physical_address:
                    break
        except Exception as e:
            logging.warning(f"Could not get MAC address using psutil: {e}")

    if physical_address:
        info["IP e Rede"].append(f"Mac Address: {physical_address}")

    ip_address = "N/A"
    try:
        ip_address = socket.gethostbyname(hostname)
        info["IP e Rede"].append(f"IPv4 Address: {ip_address}")
    except socket.gaierror:
        info["IP e Rede"].append("IPv4 Address: N/A (não foi possível resolver)")


    info["Sistema Operacional"]["OS"] = f"{platform.system()} {platform.release()} {platform.version()}"
    info["Sistema Operacional"]["Arquitetura"] = platform.machine()

    if platform.system() == "Windows":
        try:
            cpu_info = subprocess.check_output("wmic cpu get name", shell=True, text=True, encoding='utf-8', errors='ignore').strip().split('\n')[-1]
            info["Hardware"]["Processador"] = cpu_info.strip()
        except Exception as e:
            logging.error(f"Erro ao obter info do processador: {e}")
            info["Hardware"]["Processador"] = "N/A"
        try:
            ram_bytes = subprocess.check_output("wmic ComputerSystem get TotalPhysicalMemory", shell=True, text=True, encoding='utf-8', errors='ignore').strip().split('\n')[-1]
            ram_gb = round(int(ram_bytes) / (1024 ** 3), 2)
            info["Hardware"]["RAM (GB)"] = ram_gb
            ram_details = subprocess.check_output("wmic memorychip get Capacity,Speed,Manufacturer,PartNumber", shell=True, text=True, encoding='utf-8', errors='ignore').strip()
            info["Hardware"]["RAM Details"] = ram_details
        except Exception as e:
            logging.error(f"Erro ao obter info da RAM: {e}")
            info["Hardware"]["RAM (GB)"] = "N/A"
            info["Hardware"]["RAM Details"] = "N/A"
        try:
            disk_bytes = subprocess.check_output("wmic logicaldisk where DeviceID='C:' get Size", shell=True, text=True, encoding='utf-8', errors='ignore').strip().split('\n')[-1]
            disk_gb = round(int(disk_bytes) / (1024 ** 3), 2)
            info["Hardware"]["Disk C: (GB)"] = disk_gb
            disk_details = subprocess.check_output("wmic diskdrive get Model,SerialNumber,Size", shell=True, text=True, encoding='utf-8', errors='ignore').strip()
            info["Hardware"]["Disk Details"] = disk_details
        except Exception as e:
            logging.error(f"Erro ao obter info do disco: {e}")
            info["Hardware"]["Disk C: (GB)"] = "N/A"
            info["Hardware"]["Disk Details"] = "N/A"
        try:
            output = subprocess.check_output("wmic baseboard get Manufacturer,Product,SerialNumber", shell=True, text=True, encoding='utf-8', errors='ignore').strip()
            lines = output.splitlines()
            if len(lines) > 1:
                header = lines[0]
                man_pos = header.find("Manufacturer")
                prod_pos = header.find("Product")
                ser_pos = header.find("SerialNumber")
                
                data_line = lines[1]
                info["Hardware"]["Motherboard Manufacturer"] = data_line[man_pos:prod_pos].strip()
                info["Hardware"]["Motherboard Product"] = data_line[prod_pos:ser_pos].strip()
                info["Hardware"]["Motherboard SerialNumber"] = data_line[ser_pos:].strip()
            else:
                raise ValueError("WMIC output for baseboard is not as expected.")
        except Exception as e:
            logging.error(f"Erro ao obter info da motherboard: {e}")
            info["Hardware"]["Motherboard Manufacturer"] = "N/A"
            info["Hardware"]["Motherboard Product"] = "N/A"
            info["Hardware"]["Motherboard SerialNumber"] = "N/A"
        try:
            gpu_info = subprocess.check_output("wmic path win32_VideoController get Name,DriverVersion", shell=True, text=True, encoding='utf-8', errors='ignore').strip()
            info["Hardware"]["Graphics"] = gpu_info
        except Exception as e:
            logging.error(f"Erro ao obter info da GPU: {e}")
            info["Hardware"]["Graphics"] = "N/A"

    if platform.system() == "Windows":
        office_version = check_office_uninstall_registry()
        info["Microsoft Office"]["Versão"] = office_version

    return info

def main():
    """
    Recolhe a informação do sistema e guarda-a num ficheiro de texto.
    """
    logging.info("A recolher informação do sistema...")
    system_info = get_system_info()

    filename = "pcinventory_pessoal_info.txt"

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
        logging.info(f"Informação do sistema guardada com sucesso em '{filename}'.")
    except Exception as e:
        logging.error(f"Erro ao criar o ficheiro de informação do sistema: {e}")

if __name__ == "__main__":
    main()
    input("Recolha de informação concluída. Pressione Enter para sair...")