#!/bin/bash
set -e

# Image tag expected by MopenHands/SWE-bench
IMAGE_TAG="docker.io/xingyaoww/sweb.eval.x86_64.aws-cloudformation_s_cfn-lint-3470"

echo "Building Docker image: $IMAGE_TAG"

docker build -t "$IMAGE_TAG" -f Dockerfile.cfn-lint .

echo "Build complete. Image tagged as $IMAGE_TAG"
echo "Verifying image existence..."
docker image inspect "$IMAGE_TAG" > /dev/null
echo "Verification successful."
