#!/usr/bin/env bash
# Despliega todo en el lab de esta sesión (backend y web). Uso, desde la raíz del repo en CloudShell:
#   bash infra/scripts/deploy.sh    (o MODEL=mock bash infra/scripts/deploy.sh)
set -euo pipefail
cd "$(dirname "$0")/../.."
export AWS_DEFAULT_REGION=${AWS_REGION:-us-east-1}
bash infra/scripts/deploy_backend.sh
export API_URL=$(aws cloudformation describe-stacks --stack-name isitai-api --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue" --output text)
bash infra/scripts/deploy_web.sh
