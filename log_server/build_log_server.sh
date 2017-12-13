#!/usr/bin/env bash

export TAG=$1
docker build -t loopchain-fluentd:${TAG} ./
docker tag loopchain-fluentd:${TAG} loopchain-fluentd:latest