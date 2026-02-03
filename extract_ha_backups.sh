#!/bin/bash

# --- CONFIGURATION ---
VM_NAME="hass"
DISK_IMAGE="/mnt/myssd/vm-images/hassos-vm/haos_ova-6.6.qcow2"
MOUNT_POINT="/mnt/ha_recovery"
LOCAL_BACKUP_DIR="/mnt/myssd/backup/homeassistant"
TARGET_USER="loris"
# ---------------------

# Check if running as root
if [ "$EUID" -ne 0 ]; then
  echo "Error: Please run as root (sudo)"
  exit 1
fi

echo "--- Starting Home Assistant Backup Extraction ---"
date

# 1. SHUTDOWN VM
echo "[1/6] Stopping VM '$VM_NAME'..."
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
echo "[2/6] Mounting disk image (Read-Only)..."
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
echo "[3/6] Syncing files to $LOCAL_BACKUP_DIR..."
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
# --delete : (OPTIONAL) Removes files locally if they are gone from HA.
#            I removed it below to be safe. Add it back if you want a perfect mirror.

rsync -av "$SOURCE_DIR" "$LOCAL_BACKUP_DIR/"
# To auto-delete old files, change the line above to:
# rsync -av --delete "$SOURCE_DIR" "$LOCAL_BACKUP_DIR/"

# 4. FIX PERMISSIONS
echo "[4/6] Fixing ownership for user $TARGET_USER..."
chown -R "$TARGET_USER:$TARGET_USER" "$LOCAL_BACKUP_DIR"

# 5. UNMOUNT
echo "[5/6] Unmounting disk..."
umount "$MOUNT_POINT"
sleep 2

# 6. RESTART VM
echo "[6/6] Starting VM '$VM_NAME'..."
virsh start "$VM_NAME" > /dev/null

echo "--- SUCCESS: Extraction complete and VM restarted ---"

# 7. TRIGGER PYTHON UPLOAD
#echo "--- Starting Google Drive Upload ---"
#sudo -u "$TARGET_USER" python3 /home/loris/backup_vm_drive.py
