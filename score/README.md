# Loopchain SCORE 개발가이드

## Loopchain Score 란 
* Loopchain의 스마트 컨트렉트를 통칭합니다.
* 각 피어에서 독립적으로 실행되며, Block 이 확정되는 시점에서 실행됩니다.
* Block별로 실행하며, 블록체인으로 구성하는 비지니스로직을 구현한다.
* Python 언어로 개발되며, Loopchain의 dependency 를 따릅니다.

## SCORE 개발
스코어의 개발은 3단계로 나뉠수 있습니다.
1. 비지니스 모델 타당성 검증
2. 모델 구현 및 유닛테스트
3. 인티그레이션 테스트 및 모델 배포
 
### 1. 비지니스 모델 타당성 검증
 스코어 안에서는 다음과 같은 내용을 통한 비지니스는 불가합니다.

#### 1. 랜덤값에 의존하는 비지니스 모델 
 스코어 안에서 랜덤값을 생성하거나, 실행하는 모델은 불가하나, 블록의 해쉬 혹은 트랜잭션을 이용한 랜덤값 이용은 가능합니다. 
#### 2. 외부의 데이터에 의존성이 있는 비지니스 모델
 스코어 안에서 다른 사이트를 호출하거나, 외부의 데이터를 요구하는 모델은 아직 불가능하나 향후 고려되고 있습니다.
#### 3. 시간에 따라 행동하는 혹은 실행시간에 따라 내용이 바뀌는 모델
 **현재 시간(실행시간)은 사용 불가능**하며, 블록의 시간 혹은 트랜잭션 시간으로 대체는 가능합니다. 
 
### 폴더 및 실행구조
  * / score / 회사명(기관명) / 패키지명
  > ex) /score/loopchain/default/
  * __`deploy` 폴더명은 사용 불가__
  * 원격 리파지토리를 사용하지 않을 경우 다음과 같이 가능합니다.
    - `회사명(기관명)_패키지명.zip` 으로 리파지토리 전체를 압축하여 score에 저장하여 실행 
  * 패키지 설명 및 실행에 대한 상세내용은 `package.json` 파일로 정의 하며, `package.json` 정의에 대한 내용은 [다른 가이드에서 설명합니다.](PACKAGE_GUIDE.md) 

## 2. SCORE 테스트
* 스코어를 작성하거나, 개발할때는 **coverage 90%** 이상을 목표로 개발 하여야 하며, 퍼포먼스도 고려되어야 합니다.
* 모든 테스트 코드는 스코어의 패키지 루트에 있어야 하며, 차후 리파지토리 등록전에 실행됩니다. 

### SCORE의 테스트 방법
```
# TEST 실행은 loopchain root 폴더에서 실행
$>python3 -m unittest score/회사명(기관명)/패키지명/테스트파일
ex)
$>python3 -m unittest score/theloop/chain_message_score/test_chain_message.py
```
__IDE에서 테스트시 Working Directory 를 Loopchain root로 설정하여 테스트 바랍니다.__

## 3. SCORE 배포 및 관리
* 스코어의 배포는 특별히 관리되는 리파지토리에서 관리 됩니다.
  - 차후 다수의 리파지토리를 검색하여, 순위별로 배포하는 방안도 검토 중입니다.
* 리모트 리파지토리에서 관리하지 않는 스코어는 내부 리파지토리가 포함된 zip 파일에서 관리합니다.
* peer 에서 스코어의 배포는 다음의 명령어를 통해 하게 됩니다.
   - Docker에서 실행시  
     ```
     docker run -d ${DOCKER_LOGDRIVE} --name ${PEER_NAME} --link radio_station:radio_station -p ${PORT}:${PORT}  looppeer:${DOCKER_TAG}  python3 peer.py -c ${DEPLOY_SCORE}  -r radio_station -d -p ${PORT}
     ```
   - Local에서 실행시
     ```
     python3 peer.py -c ${DEPLOY_SCORE}  -r radio_station -d -p ${PORT}
     ```
   - 참조
     - DEPLOY_SCORE 는 `기관명/패키지명` 입니다.
     - PEER_NAME은 Peer의 이름을 지칭합니다.
     - PORT는 radio_station 의 위치 IP:PORT 로 설정됩니다. 
     - /deploy/launch_containers_in_local_demo.sh 파일을 참조 바랍니다.

