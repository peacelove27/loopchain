#!/usr/bin/env bash


function build_docker(){
    local POST_FIX=$1
    echo "BUILD LOOP BASE"
    docker build -f dockerfile_base --tag loop-base:latest ..
    echo "BUILD LOCAL RADIOSTATION"
    docker build -f dockerfile_rs --tag looprs:${POST_FIX} ..  || exit -1
    echo "BUILD LOCAL PEER"
    docker build -f dockerfile_peer --tag looppeer:${POST_FIX} ..  || exit -1
}

function build_local_fluentd(){
    local TAG=$1
    echo "BUILD LOCAL FLUENTD"
    cd ../log_server/
    ./build_log_server.sh ${TAG}
    cd ../deploy/
}

ARG=$1
LOG=$2
# No args or '-help' : help message
if [[ $# -eq 0 ]] || [ ${ARG} = -help ] ; then
    echo "Build docker image. "
    echo "=========================================="
    echo "$ build_docker_image.sh \$OPTION"
    echo "OPTION"
    echo "------------------------------------------"
    echo "dev: build docker image for development. "
    echo "release: build docker image for release. "
    echo "=========================================="
    exit 0
fi

# loopchain version
git rev-parse HEAD > LOOPCHAIN_VERSION

echo "REMOVE PYCACHE"
find .. | grep -E "(__pycache__|\.pyc|\.pyo$)" | xargs rm -rf

if [[ ${LOG} = log || "$(docker images -q loopchain-fluentd:latest > /dev/null)" == "" ]]; then
    # build fluentd for local operation.
    build_local_fluentd ${ARG}
fi


build_docker ${ARG}
