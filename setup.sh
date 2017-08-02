#!/bin/sh
# by winDy
# 프로젝트의 기본적인 작업 환경을 자동으로 구성한다

# 이 스크립트는 다음의 항목을 포함합니다.
# * virtualenv 환경 설정 
# * Python 3rd party들을 virtualenv환경 아래 현재 프로젝트에 추가. 

# Check System OS type
if [ "$(uname)" == "Darwin" ]; then
    # Do something under Mac OS X platform
    echo "Your System is Mac"
    echo ""
elif [ "$(expr substr $(uname -s) 1 5)" == "Linux" ]; then
    # Do something under GNU/Linux platform
    echo "Your System is Linux"
    echo ""
elif [ "$(expr substr $(uname -s) 1 10)" == "MINGW32_NT" ]; then
    # Do something under Windows NT platform
    echo "Your System is Windows"
    echo "We totally no idea about this script with Windows.... Sorry about it"
    echo ""
    exit
fi

if [ -z "$VIRTUAL_ENV" ]; then
    echo "virtualenv 환경 설정"
    pip3 install virtualenv
    virtualenv -p python3 .

    echo ""
    echo "virtualenv 를 활성화하기 위해 다음의 커맨드를 입력후 ./setup.sh 를 다시 실행해 주세요."
    echo "source bin/activate"
    echo ""
    exit
else
    echo "Install requirements in virtualenv...."
    pip3 install -r requirements.txt
    echo ""

    echo "complete."
    echo "grpc 코드를 생성하기 위해 다음의 스크립트를 실행하세요."
    echo "generate_code.sh"
    # 이 script 는 생성 방법은 http://www.grpc.io/docs/tutorials/basic/python.html 의 샘플을 이용하여 테스트 되었습니다.
fi