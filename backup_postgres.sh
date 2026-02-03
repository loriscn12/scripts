#!/bin/bash

cd /home/root
date1=$(date +%Y%m%d-%H%M)
mkdir pg-backup

PGPASSWORD="$PG_PASS" pg_dumpall -h postgres.default.svc.cluster.local -p 5432 -U postgres > pg-backup/postgres-db.tar
file_name="pg-backup-"$date1".tar.gz"

# Compressing backup file
tar -zcvf $file_name pg-backup

notification_msg="Postgres-Backup-failed"
filesize=$(stat -c %s $file_name)
mfs=10
if [[ "$filesize" -gt "$mfs" ]]; then
  aws s3 cp $file_name $S3_BUCKET
  notification_msg="Postgres-Backup-was-successful"
fi

# Send Slack Notification
#send_slack_notification() {
#  payload='payload={"text": "'$1'"}'
#  curl --silent --data-urlencode "$(printf "%s" $payload)" ${APP_SLACK_WEBHOOK} || true
#}
#send_slack_notification $notification_msg
