#!/usr/bin/env bash
set -euo pipefail

: "${DEPLOY_HOST:?Set DEPLOY_HOST}"
: "${DEPLOY_USER:?Set DEPLOY_USER}"
: "${SSH_PRIVATE_KEY:?Set SSH_PRIVATE_KEY credential file}"
: "${SSH_KNOWN_HOSTS:?Set SSH_KNOWN_HOSTS credential file}"
: "${DEPLOY_ENV:?Set DEPLOY_ENV credential file}"
: "${GIT_COMMIT:?Run in Jenkins}"

[[ "$GIT_COMMIT" =~ ^[a-f0-9]{40,64}$ ]]
[[ "$DEPLOY_HOST" =~ ^[A-Za-z0-9][A-Za-z0-9.-]*$ ]]
[[ "$DEPLOY_USER" =~ ^[a-z_][a-z0-9_-]*$ ]]

keydir=$(mktemp -d)
trap 'rm -rf "$keydir"' EXIT
install -m 600 "$SSH_PRIVATE_KEY" "$keydir/key"
install -m 600 "$SSH_KNOWN_HOSTS" "$keydir/known_hosts"
ssh_options=(-i "$keydir/key" -o BatchMode=yes -o StrictHostKeyChecking=yes -o "UserKnownHostsFile=$keydir/known_hosts")
target="$DEPLOY_USER@$DEPLOY_HOST"

ssh "${ssh_options[@]}" "$target" 'mkdir -p ~/mtg-shop && chmod 700 ~/mtg-shop'
scp "${ssh_options[@]}" docker-compose.yml "$target:mtg-shop/"
scp "${ssh_options[@]}" -r monitoring "$target:mtg-shop/"
scp "${ssh_options[@]}" "$DEPLOY_ENV" "$target:mtg-shop/.env.next"
ssh "${ssh_options[@]}" "$target" 'chmod 600 ~/mtg-shop/.env.next && mv ~/mtg-shop/.env.next ~/mtg-shop/.env'
ssh "${ssh_options[@]}" "$target" 'docker load' < image.tar
ssh "${ssh_options[@]}" "$target" "bash -s -- '$GIT_COMMIT'" <<'REMOTE'
set -euo pipefail
cd ~/mtg-shop
export APP_IMAGE="mtg-shop:$1"
docker compose up -d --no-build --wait --wait-timeout 180
sed '/^APP_IMAGE=/d' .env > .env.next
printf '\nAPP_IMAGE=%s\n' "$APP_IMAGE" >> .env.next
chmod 600 .env.next
mv .env.next .env
app_port=$(docker compose port api 8000 | awk -F: '{print $NF}')
curl --fail --silent --show-error "http://127.0.0.1:$app_port/health"
REMOTE
