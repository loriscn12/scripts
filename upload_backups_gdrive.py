import os
import logging
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

# --- CONFIGURATION ---
DRIVE_FOLDER_ID = '1abcDeFghIjKlMnOpQrStUvWxYz' # <--- KEEP YOUR ID
CREDENTIALS_FILE = 'credentials.json'

# NOW WE JUST READ THE LOCAL FOLDER (No more SFTP/VM connection)
LOCAL_BACKUP_FOLDER = '/home/loris/backups/homeassistant' 
LOG_FILE = '/var/log/ha_backup.log'
# ---------------------

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

def authenticate_drive():
    try:
        SCOPES = ['https://www.googleapis.com/auth/drive']
        creds = service_account.Credentials.from_service_account_file(
            CREDENTIALS_FILE, scopes=SCOPES)
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        logging.error(f"Auth failed: {e}")
        return None

def upload_files():
    service = authenticate_drive()
    if not service: return

    if not os.path.exists(LOCAL_BACKUP_FOLDER):
        logging.error(f"Folder not found: {LOCAL_BACKUP_FOLDER}")
        return

    files = [f for f in os.listdir(LOCAL_BACKUP_FOLDER) if f.endswith('.tar')]
    
    if not files:
        logging.info("No .tar files found to upload.")
        return

    logging.info(f"Found {len(files)} backups. Checking Google Drive...")

    for filename in files:
        file_path = os.path.join(LOCAL_BACKUP_FOLDER, filename)
        
        # Simple upload logic
        file_metadata = {'name': filename, 'parents': [DRIVE_FOLDER_ID]}
        media = MediaFileUpload(file_path, resumable=True)
        
        try:
            logging.info(f"Uploading: {filename}")
            service.files().create(
                body=file_metadata,
                media_body=media,
                fields='id'
            ).execute()
            logging.info(f"Success: {filename}")
        except Exception as e:
            logging.error(f"Failed to upload {filename}: {e}")

if __name__ == '__main__':
    upload_files()
