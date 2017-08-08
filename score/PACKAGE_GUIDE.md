# Loopchain SCORE package guide

## Loopchain SCORE package file
package file 은 json 형태로 제공되며, 프록시가 로드 될때 같이 로드하여,  
내부에서 패키지 정보가 필요할 때 해당 내용이 제공된다.
```
ex) 
{
  "id":"loopchain-sample",
  "version":"1.0.0",
  "auth":{
    "name":"LoopChain Dev Team",
    "email":"dev@theloop.co.kr",
    "org":"Theloop inc"
  },
  "dependencies":{},
  "description":"LoopChain Sample Score",
  "repository":{},
  "homepage":"http://www.theloop.co.kr",
  "function":{
    "query":[
        {
            "method":"sample_method",
            "params":{
                "tx_hash":"string"
            },
            "description":"sample Search method"
          }
    ],
    "invoke":[
        {
            "method":"create_transaction",
            "params":{
                "sample_data":"string"
            },
            "description":"make new transaction"
        }
    ]
  },
  "main":"default_score"
}
```
- id : 패키지의 아이디
- version : 버젼
- auth : 패키지의 작성자
   - name : 작성자 명
   - email : 작성자 이메일
   - org : 작성자의 회사 혹은 기관명 (풀네임)
- dependencies : 패키지 의존성 ( 향후활용예정 )
- description : 패키지의 설명
- repository : 원격 리파지토리
- homepage : 작성 홈페이지
- function : 스코어 내부함수의 설명
  - query : 조회함수의 설명
     - method : 조회함수 명 (proxy 연계)
     - params : 조회시 파라미터
     - description : 조회함수의 설명
  - invoke : 실행 함수의 설명
     - method : 실행함수 명 (proxy 연계)
     - params : 실행시 파라미터
     - description : 실행함수의 설명
- main : 패카지 실행 파일명


