import subprocess
import os
import sys
import datetime
import logging
import tempfile

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def create_weekly_task(task_name, script_path):
    """
    Creates a Windows scheduled task to run the given script every Monday at 10:00 AM.
    """
    try:
        # Construct the schtasks command
        command = [
            'schtasks',
            '/Create',
            '/SC', 'WEEKLY',
            '/D', 'MON',
            '/ST', '10:00',
            '/TN', task_name,
            '/TR', f'\"{sys.executable}\" \"{script_path}\" --run-task',
            '/F'  # Force create the task if it exists
        ]
        # Run the command
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode == 0:
            logging.info(f"Scheduled task '{task_name}' created successfully.")
        else:
            logging.error(f"Failed to create scheduled task. Error:\n{result.stderr}")
    except Exception as e:
        logging.error(f"Exception occurred while creating scheduled task: {e}")

def has_run_this_week(marker_file):
    """
    Check if the task has already run this week by reading the marker file.
    """
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
    """
    Update the marker file with the current year-week.
    """
    current_week = datetime.datetime.now().strftime('%Y-%W')
    try:
        with open(marker_file, 'w') as f:
            f.write(current_week)
    except Exception as e:
        logging.error(f"Error writing marker file: {e}")

def run_task_if_first_login_of_week():
    """
    Run the actual task only if it has not run this week.
    """
    # Use a neutral location for the marker file, e.g., temp directory
    marker_file = os.path.join(tempfile.gettempdir(), '.task_last_run_week')
    if has_run_this_week(marker_file):
        # Already ran this week, exit silently
        logging.info("Task has already run this week. Exiting.")
        return
    # Run the actual executable
    exe_path = r"C:\\Tecnico Giscon\\GInventoryPc\\gEasy_pcinventory-client.exe"
    try:
        subprocess.run([exe_path], check=True)
        update_run_marker(marker_file)
        logging.info("Task executed successfully and marker updated.")
    except Exception as e:
        logging.error(f"Failed to run the executable: {e}")

if __name__ == "__main__":
    task_name = "gEasy_pcinventory_client_Primeiro_login_da_semana"
    script_path = os.path.abspath(__file__)
    if len(sys.argv) > 1 and sys.argv[1] == '--run-task':
        run_task_if_first_login_of_week()
    else:
        create_weekly_task(task_name, script_path)
