#!/usr/bin/env bash
# Compila la web y la sube al bucket de S3 creado por el stack isitai-base.
#
# Uso (desde CloudShell, con el repo clonado):
#   API_URL=https://xxxx.execute-api.us-east-1.amazonaws.com bash infra/scripts/deploy_web.sh
#
# Se puede correr varias veces: solo sube lo que cambió.
set -euo pipefail

: "${API_URL:?Falta API_URL: la URL de la API, por ejemplo https://xxxx.execute-api.us-east-1.amazonaws.com}"
API_URL="${API_URL%/}" # sin barra final
REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
BASE_STACK="${BASE_STACK:-isitai-base}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# El bucket se llama isitai-web-<cuenta>-<región> (lo define infra/base.yaml).
ACCOUNT="$(aws sts get-caller-identity --query Account --output text)"
BUCKET="isitai-web-${ACCOUNT}-${REGION}"
if ! aws s3api head-bucket --bucket "$BUCKET" --region "$REGION" 2>/dev/null; then
  echo "No existe el bucket $BUCKET. Desplegá primero el stack $BASE_STACK (infra/base.yaml)." >&2
  exit 1
fi

# Vite 8 pide Node ^20.19 o >=22.12: si CloudShell trae uno más viejo, se usa uno temporal en /tmp.
if ! node -e 'const [a,b]=process.versions.node.split(".").map(Number);process.exit(a>22||(a==22&&b>=12)||(a==20&&b>=19)?0:1)' 2>/dev/null; then
  NODE=node-v22.20.0-linux-x64
  curl -fsSL "https://nodejs.org/dist/v22.20.0/$NODE.tar.gz" | tar -xz -C /tmp
  export PATH="/tmp/$NODE/bin:$PATH"
fi

echo "==> Compilando la web (API: $API_URL)"
cd "$ROOT/frontend"
npm ci
# Las variables del entorno tienen prioridad sobre los archivos .env: así nunca
# se publica una web en modo falso ni apuntando a otra API.
VITE_USE_FAKE_API=false VITE_API_URL="$API_URL" npm run build

echo "==> Subiendo a s3://$BUCKET"
# 1) assets/: archivos con hash en el nombre; cambian de nombre si cambian de contenido,
#    así que el navegador los puede guardar mucho tiempo.
aws s3 sync dist/assets "s3://$BUCKET/assets" --region "$REGION" --delete \
  --cache-control "public,max-age=31536000,immutable"
# 2) Todo lo demás (index.html, favicon...) después, para que index.html nunca apunte
#    a archivos que todavía no están. Sin CloudFront no hay invalidación: no-cache hace
#    que el navegador pregunte siempre si hay una versión nueva.
aws s3 sync dist "s3://$BUCKET" --region "$REGION" --delete --exclude "assets/*" \
  --cache-control "no-cache"

WEB_URL="$(aws cloudformation describe-stacks --stack-name "$BASE_STACK" --region "$REGION" \
  --query "Stacks[0].Outputs[?OutputKey=='WebUrl'].OutputValue" --output text 2>/dev/null || true)"

echo
echo "Listo. Web: ${WEB_URL:-http://$BUCKET.s3-website-$REGION.amazonaws.com}"
#echo "Recordá que la API tiene que desplegarse con ALLOWED_ORIGIN igual a esa URL (sin barra final)."