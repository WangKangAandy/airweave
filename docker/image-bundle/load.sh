#!/usr/bin/env sh
set -eu

TAR_PATH="/bundle/airweave-base-images.tar"

if [ ! -S /var/run/docker.sock ]; then
  echo "ERROR: /var/run/docker.sock is required to load images into host docker."
  exit 1
fi

if [ ! -f "$TAR_PATH" ]; then
  echo "ERROR: bundle tar not found at $TAR_PATH"
  exit 1
fi

echo "Loading bundled images from $TAR_PATH ..."
docker load -i "$TAR_PATH"
echo "Bundle images loaded successfully."
