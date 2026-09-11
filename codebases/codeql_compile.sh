#!/bin/bash

# Simple CodeQL Java Compilation Script
# Usage: ./codeql_compile.sh <app_name>

if [ $# -ne 1 ]; then
    echo "Usage: $0 <app_name>"
    exit 1
fi

APP_NAME="$1"

# List of supported apps
SUPPORTED_APPS=("java" "python" "go" "javascript" "mlflow" "N4si-python" "AutoGPT" "gradio" "reflex" "web3.py" "pyramid" "keystone-classic")

# Check if app is in supported list
if [[ ! " ${SUPPORTED_APPS[@]} " =~ " ${APP_NAME} " ]]; then
    echo "Error: '$APP_NAME' is not a supported app"
    echo "Supported apps: ${SUPPORTED_APPS[*]}"
    exit 1
fi

echo "Creating CodeQL database for $APP_NAME..."

DATABASES="../databases"
# Conditional statements for known apps
if [ "$APP_NAME" = "java" ]; then
    codeql database create "$DATABASES/$APP_NAME" --language=java --command="mvn clean compile" --source-root="$APP_NAME" --overwrite

elif [ "$APP_NAME" = "python" ]; then
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite

elif [ "$APP_NAME" = "go" ]; then
    codeql database create "$DATABASES/$APP_NAME" --language=go --command="make build" --source-root="$APP_NAME" --overwrite

elif [ "$APP_NAME" = "javascript" ]; then
    codeql database create "$DATABASES/$APP_NAME" --language=javascript --source-root="$APP_NAME" --overwrite

elif [ "$APP_NAME" = "keystone-classic" ]; then
    git submodule update --init keystone-classic
    codeql database create "$DATABASES/$APP_NAME" --language=javascript --source-root="$APP_NAME" --overwrite

elif [ "$APP_NAME" = "mlflow" ]; then
    # check out to the submodule
    git submodule update --init mlflow
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite
elif [ "$APP_NAME" = "N4si-python" ]; then
    # check out to the submodule
    git submodule update --init N4si-python
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite
elif [ "$APP_NAME" = "AutoGPT" ]; then
    # check out to the submodule
    git submodule update --init AutoGPT
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite
elif [ "$APP_NAME" = "gradio" ]; then
    # check out to the submodule
    git submodule update --init gradio
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite
elif [ "$APP_NAME" = "reflex" ]; then
    # check out to the submodule
    git submodule update --init reflex
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite
elif [ "$APP_NAME" = "web3.py" ]; then
    # check out to the submodule
    git submodule update --init reflex
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite
elif [ "$APP_NAME" = "pyramid" ]; then
    # check out to the submodule
    git submodule update --init reflex
    codeql database create "$DATABASES/$APP_NAME" --language=python --source-root="$APP_NAME" --overwrite


fi

echo "CodeQL database created: $DATABASES/$APP_NAME"
