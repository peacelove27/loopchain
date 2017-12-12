#!/usr/bin/env bash

function launch_docker_in_local(){

    local PORT=$1
    local PEER_NAME=$2
    local DOCKER_TAG=$3
    local DEPLOY_SCORE=$4
    # resfulAPI
    local API_PORT=$(($PORT+1900))
    echo "RUN ${PEER_NAME} ${DOCKER_TAG} ${PORT} ${API_PORT} ${DEPLOY_SCORE}"
    docker run -d ${DOCKER_LOGDRIVE} --name ${PEER_NAME} --env-file ./env_${DOCKER_TAG}.list \
        --link radio_station:radio_station -p ${PORT}:${PORT} -p ${API_PORT}:${API_PORT} \
        -e USE_GUNICORN_HA_SERVER=True \
        looppeer:${DOCKER_TAG} python3 peer.py  -r radio_station:7102 -d -p ${PORT} || exit -1

}

ARG=$1
DEPLOY_SCORE=$2

# No args or '-help' : help message
if [[ $# -eq 0 ]] || [ ${ARG} = -help ] ; then
    echo "Build docker image. "
    echo "=========================================="
    echo "$ launch_containers_in_local.sh \$OPTION \$DEPLOY_SCORE"
    echo "OPTION"
    echo "------------------------------------------"
    echo "dev: build docker image for development. "
    echo "release: build docker image for release. "
    echo "=========================================="
    exit 0
fi

export TAG=$ARG

if [[ ${#DEPLOY_SCORE} -eq 0 ]]; then
    DEPLOY_SCORE=loopchain/default
fi


# Launch log server
export LOG_PATH=$(pwd)/log

echo "RUN fluentd-logger"
docker run -d --name custom-docker-fluentd-logger -v ${LOG_PATH}:/fluentd/log loopchain-fluentd

export LOG_SERVER_IP=$(docker inspect -f '{{.NetworkSettings.IPAddress}}' custom-docker-fluentd-logger)
export DOCKER_LOGDRIVE='--log-driver=fluentd --log-opt fluentd-address='${LOG_SERVER_IP}':24224'

sleep 10

# Launch RadioStation.
echo "RUN RADIO STATION"
docker run -d ${DOCKER_LOGDRIVE} --name radio_station -p 7102:7102 -p 9002:9002 looprs:${TAG} python3 radiostation.py -d


# Launch Peer 0. Port = 7100
launch_docker_in_local 7100 peer0  ${TAG}

# Launch Peer 1. Port = 7200
launch_docker_in_local 7200 peer1  ${TAG}

# Launch Peer 2. Port = 7300
launch_docker_in_local 7300 peer2  ${TAG}

# Launch Peer 3. Port = 7400
launch_docker_in_local 7400 peer3  ${TAG}

