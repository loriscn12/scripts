#!/bin/bash

# --- CONFIGURATION ---
VM_NAME="hass"
DISK_IMAGE="/mnt/myssd/vm-images/hassos-vm/haos_ova-6.6.qcow2"
MOUNT_POINT="/mnt/ha_recovery"
LOCAL_BACKUP_DIR="/mnt/myssd/backup/homeassistant"
TARGET_USER="loris"
BACKUP_RETENTION_COUNT=5
# ---------------------

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run as root (sudo)"
  exit 1
fi

echo "--- Starting Home Assistant Backup Extraction ---"
date

# 1. SHUTDOWN VM
echo "[1/7] Stopping VM '$VM_NAME'..."
virsh shutdown "$VM_NAME" > /dev/null

MAX_RETRIES=24
COUNT=0
while [ "$(virsh domstate "$VM_NAME" | tr -d '\n')" != "shut off" ]; do
    if [ "$COUNT" -ge "$MAX_RETRIES" ]; then
        echo "Error: VM failed to shut down. Aborting."
        exit 1
    fi
    sleep 5
    ((COUNT++))
done
echo "      VM is OFF."

# 2. MOUNT DISK (READ-ONLY)
echo "[2/7] Mounting disk image (Read-Only)..."
mkdir -p "$MOUNT_POINT"
umount "$MOUNT_POINT" 2>/dev/null

# --ro prevents locking issues and is safer for backups
guestmount --ro -a "$DISK_IMAGE" -m /dev/sda8 "$MOUNT_POINT"

if [ $? -ne 0 ]; then
    echo "CRITICAL ERROR: Failed to mount. Restarting VM..."
    virsh start "$VM_NAME"
    exit 1
fi

# 3. SYNC FILES
echo "[3/7] Syncing files to $LOCAL_BACKUP_DIR..."
mkdir -p "$LOCAL_BACKUP_DIR"

SOURCE_DIR="$MOUNT_POINT/supervisor/backup/"

if [ ! -d "$SOURCE_DIR" ]; then
    echo "ERROR: Backup folder not found at $SOURCE_DIR"
    umount "$MOUNT_POINT"
    virsh start "$VM_NAME"
    exit 1
fi

# EXPLANATION OF FLAGS:
# -a : Archive (keep permissions/times)
# -v : Verbose
rsync -av "$SOURCE_DIR" "$LOCAL_BACKUP_DIR/"

# 4. FIX PERMISSIONS
echo "[4/7] Fixing ownership for user $TARGET_USER..."
chown -R "$TARGET_USER:$TARGET_USER" "$LOCAL_BACKUP_DIR"

# 5. CLEANUP OLD BACKUPS (NEW STEP)
echo "[5/7] Cleaning up old backups (Retaining latest $BACKUP_RETENTION_COUNT)..."

# Navigate to directory safely
cd "$LOCAL_BACKUP_DIR" || { echo "Failed to enter backup dir"; exit 1; }

# List files by time (newest first), skip the first X files, delete the rest.
# -1t : One file per line, sorted by modification time (newest first)
# tail -n +X : Start outputting from line X onwards (skipping the newest)
# xargs -d '\n' -r rm : Delete the files piped to it, handling spaces correctly
ls -1t | tail -n +$((BACKUP_RETENTION_COUNT + 1)) | xargs -d '\n' -r rm --

# 6. UNMOUNT
echo "[6/7] Unmounting disk..."
# Move out of the directory so we don't block unmounting (though we are local, good practice)
cd /
umount "$MOUNT_POINT"
sleep 2

# 7. RESTART VM
echo "[7/7] Starting VM '$VM_NAME'..."
virsh start "$VM_NAME" > /dev/null

echo "--- SUCCESS: Extraction complete, cleaned up, and VM restarted ---"

# 8. TRIGGER PYTHON UPLOAD
#echo "--- Starting Google Drive Upload ---"
#sudo -u "$TARGET_USER" python3 /home/loris/backup_vm_drive.py
