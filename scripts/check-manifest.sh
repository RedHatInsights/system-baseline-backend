#!/bin/bash

./scripts/create-manifest.py
if [[ $? -ne 0 ]]; then
    exit 1
fi

changed=`git diff --name-only HEAD`

if [[ $changed == *"system_baseline-manifest"* ]]; then
  echo "Pipfile.lock changed without updating system_baseline-manifest. Run ./scripts/create-manifest.py to update."
  exit 1
else
  exit 0
fi
