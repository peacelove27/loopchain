#!/bin/sh
# by winDy
# grpc 를 위한 python 코드를 자동으로 생성한다.

echo "Generating python grpc code from proto...."
echo "into > " $PWD
cd loopchain
python3 -m grpc.tools.protoc -I'./protos' --python_out='./protos' --grpc_python_out='./protos' './protos/loopchain.proto'
cd ..
echo ""
