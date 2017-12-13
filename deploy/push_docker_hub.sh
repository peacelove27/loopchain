#!/usr/bin/env bash

ARG=$1

function push_docker_image(){
    local IMAGE_NAME=$1
    local TAG=$2
    docker tag ${IMAGE_NAME} ${DOCKER_REPOSITORY}/${IMAGE_NAME} || exit -1
    docker push ${DOCKER_REPOSITORY}/${IMAGE_NAME} || exit -1

}
function push_loop_other_images(){
    local IMAGE_NAME=$1
    local TAG=$2
    docker tag ${IMAGE_NAME} ${DOCKER_REPOSITORY}/${IMAGE_NAME} || exit -1
    docker push ${DOCKER_REPOSITORY}/${IMAGE_NAME} || exit -1
}

DOCKER_REPOSITORY=loopchain

# No args or '-help' : help message
if [[ ${ARG} == -help ]]; then
    echo "Push docker images into the Docker hub. "
    echo "=========================================="
    echo "$ push_docker_hub.sh"
    echo "=========================================="
    exit 0
fi

# log
echo "PUSH loopchain-fluentd "
push_loop_other_images loopchain-fluentd latest

echo "PUSH loopchain base "
push_loop_other_images loop-base

echo "PUSH Loop peer  "
push_docker_image looppeer

echo "PUSH Loop radio station  "
push_docker_image looprs

exit 0