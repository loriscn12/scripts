#!/bin/bash

# 1. Configuration
BACKUP_ROOT="/mnt/myssd/backup/yaml-k8s"
DATE=$(date +%F)
BACKUP_DIR="$BACKUP_ROOT/yaml-backup-$DATE"
MICROK8S="/snap/bin/microk8s"  # Full path is safer for Cron

# 2. Create Directory
mkdir -p "$BACKUP_DIR"

# 3. The Backup Loop
# We use the full path to microk8s here
for ns in $($MICROK8S kubectl get ns --no-headers | awk '{print $1}'); do
  mkdir -p "$BACKUP_DIR/$ns"
   
  # Export key resources
  for type in deployments services configmaps secrets ingress cronjobs daemonsets statefulsets; do
    # We ignore errors (2>/dev/null) in case a resource type doesn't exist in that namespace
    $MICROK8S kubectl get $type -n $ns -o yaml > "$BACKUP_DIR/$ns/$type.yaml" 2>/dev/null
  done
done

# 4. Retention Policy (Delete backups older than 5 days)
# -mtime +5 finds files/directories modified more than 5 days ago
find "$BACKUP_ROOT" -name "yaml-backup-*" -type d -mtime +5 -exec rm -rf {} +
