#!/usr/bin/env bash
# Uso, desde la raíz del repo en CloudShell: bash infra/scripts/deploy_backend.sh
# Variables opcionales: MODEL=real|mock (real por defecto), CACHE_ENDPOINT y HISTORY_TABLE
# (vacías = sin caché / sin historial), ALLOWED_ORIGIN (URL de CloudFront, para CORS)
set -euo pipefail
cd "$(dirname "$0")/../.."
MODEL=${MODEL:-real}
REGION=${AWS_REGION:-us-east-1}
export AWS_DEFAULT_REGION=$REGION
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ARTIFACTS=isitai-artifacts-$ACCOUNT-$REGION
MANIFEST=backend/model_api/models/models.json

out() { aws cloudformation describe-stacks --stack-name "$1" --query "Stacks[0].Outputs[?OutputKey=='$2'].OutputValue" --output text; }
deploy() { aws cloudformation deploy --stack-name "$1" --template-file "$2" --no-fail-on-empty-changeset "${@:3}"; }
package() { aws cloudformation package --template-file "$1" --s3-bucket "$ARTIFACTS" --output-template-file "$2" > /dev/null; }

if [ ! -f "$MANIFEST" ] && [ "$MODEL" != mock ]; then
  echo "Falta $MANIFEST: exportá los modelos (guía de ML) o usá MODEL=mock"
  exit 1
fi
aws s3api head-bucket --bucket "$ARTIFACTS" 2>/dev/null || aws s3 mb "s3://$ARTIFACTS" --region "$REGION"

KEY=$(aws ssm get-parameter --name /isitai/model/api-key --with-decryption --query Parameter.Value --output text 2>/dev/null || true)
if [ -z "$KEY" ]; then
  KEY=$(openssl rand -hex 24)
  aws ssm put-parameter --name /isitai/model/api-key --type SecureString --value "$KEY" > /dev/null
fi

bash infra/scripts/build_layers.sh
package infra/mock.yaml build/mock.out.yaml
deploy isitai-mock build/mock.out.yaml --parameter-overrides MockApiKey="$KEY"
if [ -f "$MANIFEST" ]; then
  package infra/model.yaml build/model.out.yaml
  deploy isitai-model build/model.out.yaml --parameter-overrides ModelApiKey="$KEY"
fi

if [ "$MODEL" = mock ]; then
  URL=$(out isitai-mock MockUrl)
  MODEL_ID=mock
else
  URL=$(out isitai-model ModelUrl)
  MODEL_ID=real-$(sha256sum "$MANIFEST" | cut -c1-8)
fi
DEFAULT_MODEL=resnet18
if [ -f "$MANIFEST" ]; then
  DEFAULT_MODEL=$(python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["default_model"])' "$MANIFEST")
fi

CACHE_TABLE=${CACHE_TABLE:-$(out_opt isitai-data CacheTableName)}
HISTORY_TABLE=${HISTORY_TABLE:-$(out_opt isitai-data HistoryTableName)}
[ -z "$CACHE_TABLE" ] && echo "Aviso: sin tabla de caché (desplegá isitai-data primero para activarla)"

package infra/api.yaml build/api.out.yaml
deploy isitai-api build/api.out.yaml --parameter-overrides \
  ModelApiUrl="${URL%/}" ModelApiKey="$KEY" ModelId="$MODEL_ID" DefaultModel="$DEFAULT_MODEL" \
  CacheEndpoint="${CACHE_ENDPOINT:-}" HistoryTable="${HISTORY_TABLE:-}" AllowedOrigin="${ALLOWED_ORIGIN:-}"

API=$(out isitai-api ApiUrl)
echo "API: $API  (modelo: $MODEL_ID)"
curl -s "$API/v1/health" || echo "(no respondió todavía; probá de nuevo en un minuto)"
echo
