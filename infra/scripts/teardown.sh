#!/usr/bin/env bash
# Borra TODO lo de isitai en la cuenta actual. Uso, desde CloudShell:
#   bash infra/scripts/teardown.sh          (pide confirmación)
#   bash infra/scripts/teardown.sh --yes    (sin preguntar)
# Antes de correrlo, descargá lo que quieras conservar del bucket del dataset:
#   aws s3 sync s3://isitai-dataset-<cuenta>-us-east-1 ./dataset-backup
set -euo pipefail
REGION=${AWS_REGION:-us-east-1}
export AWS_DEFAULT_REGION=$REGION
ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ARTIFACTS=isitai-artifacts-$ACCOUNT-$REGION
WEB=isitai-web-$ACCOUNT-$REGION
DATASET=isitai-dataset-$ACCOUNT-$REGION

if [ "${1:-}" != "--yes" ]; then
  echo "Se borrarán en la cuenta $ACCOUNT: stacks isitai-*, buckets web, dataset y artefactos, y el parámetro SSM."
  read -r -p "Escribí el ID de la cuenta para confirmar: " answer
  [ "$answer" = "$ACCOUNT" ] || { echo "Cancelado."; exit 1; }
fi

stack_exists() { aws cloudformation describe-stacks --stack-name "$1" > /dev/null 2>&1; }
bucket_exists() { aws s3api head-bucket --bucket "$1" > /dev/null 2>&1; }

del_stack() {
  if stack_exists "$1"; then
    aws cloudformation delete-stack --stack-name "$1"
    aws cloudformation wait stack-delete-complete --stack-name "$1"
    echo "Borrado stack $1"
  else
    echo "Sin stack $1 (se omite)"
  fi
}

# Vacía un bucket con todas sus versiones y marcadores de borrado.
empty_bucket() {
  if bucket_exists "$1"; then
    python3 -c 'import boto3, sys; boto3.resource("s3").Bucket(sys.argv[1]).object_versions.delete()' "$1"
    echo "Vaciado $1"
  fi
}

# Orden inverso al despliegue: primero lo que consume, al final la base.
del_stack isitai-api
del_stack isitai-model
del_stack isitai-mock
del_stack isitai-data

empty_bucket "$WEB"
empty_bucket "$DATASET"
del_stack isitai-base

if bucket_exists "$ARTIFACTS"; then
  empty_bucket "$ARTIFACTS"
  aws s3 rb "s3://$ARTIFACTS" --force
  echo "Borrado bucket $ARTIFACTS"
fi

aws ssm delete-parameter --name /isitai/model/api-key > /dev/null 2>&1 && echo "Borrado parámetro SSM" || true

# Los log groups de Lambda sobreviven al stack: se borran aparte.
for lg in $(aws logs describe-log-groups --log-group-name-prefix /aws/lambda/isitai- --query 'logGroups[].logGroupName' --output text); do
  aws logs delete-log-group --log-group-name "$lg" && echo "Borrado log group $lg"
done

echo "Listo: no queda nada de isitai en la cuenta $ACCOUNT."