ew11 기기를 위한 코맥스 월패드 컨트롤러
===============================

https://github.com/HAKorea/addons/wallpad 를 참고 하였습니다.

새로 작성한 프로젝트는 다음의 차이점을 가집니다.
1. hex 신호를 전부 string 형태로 바꿔서 디버그가 편하게 했습니다.
2. 같은 계열(전등1,전등2,..)의 신호의 경우 비슷한 형태의 hex 신호를 가지므로 첫번째 기기의 신호와 바뀌는 자릿수를 체크하여 다음 기기의 신호를 생성하게 만들었습니다.
3. 첫번째 기기의 신호와 바뀌는 자릿수 등록을 위한 옵션 파일이 따로 필요합니다. 옵션 파일은 따로 업로드하여 사용할 수 있습니다.
4. 온도조절기를 제외한 다른 기기는 전부 ON,OFF 만 지원합니다.
5. ew11에서 8byte로 신호를 받아오는 경우 에러가 많아서 hex 길이를 16/32 두가지로 만들어뒀습니다. (16: 8byte, 32: 8byte 2개)
(시리얼몬으로 확인 시 3101000000000032B1000100000000B2 방식으로 신호가 오면 32로 세팅을 하고, 3101000000000032 // B1000100000000B2 각각 따로 두줄의 형태로 나오면 16으로 세팅하면 됩니다.)

설치 방법
-------
1. Supervisor -> ADD-ON STORE 이동
2. "https://github.com/kimtc99/wallpad" 를 Repositories 에 추가하고 새로 고침을 합니다.
3. Saram's Repository 항목으로 이동하여 "COMMAX Wallpad Controller with Nodejs"를 선택하고 INSTALL을 눌러 설치합니다.

설정 화면
-------
<pre><code>
"DEBUG": false,
"mqttlog": true,
"check_signal": false,
"find_signal":false,
"sendDelay": 80,

"ew11_IP": "192.168.x.x",
"ew11_port": 8899,
"ew11_data_length": 32,

"mqtt_server": "192.168.x.x",
"mqtt_id": "id",
"mqtt_password": "pwd",
"mqtt_receiveDelay": 10000,

"custom_file": ""
</code></pre>

#### DEBUG : true / false
작업 내역과 저장된 상태 전부를 출력합니다.
#### mqttlog : true / false
MQTT 전송 신호를 출력합니다.
#### check_signal : true / false
ew11을 통해 보내거나 받은 신호를 출력합니다.
#### find_signal : true / false
최대 100개까지 등록되지 않은 신호를 출력하고, /share/collected_signal.txt 에 저장합니다.
#### sendDelay : 숫자 (ms)
기존 신호와 겹치지 않게 신호에 딜레이를 주는 시간을 설정합니다.

#### ew11_IP : 문자
ew11 의 IP 주소를 적습니다. ex) 192.168.0.2
#### ew11_port : 숫자
ew11 의 포트 번호를 적습니다. ex) 8899
#### ew11_data_length": 16 / 32
ew11에서 받는 hex 신호의 길이를 결정합니다. (16: 8byte, 32: 16byte)

#### mqtt_server : 문자
mqtt 서버의 IP 주소를 적습니다. ex) 192.168.0.2
#### mqtt_id : 문자
mqtt 서버 사용자의 아이디를 적습니다.
#### mqtt_password": 문자
mqtt 서버 사용자의 암호를 적습니다. 숫자암호인 경우 꼭 따옴표 "1234"를 해주세요.
#### mqtt_receiveDelay : 숫자
mqtt 서버 접속 딜레이를 설정합니다.
#### custom_file : 문자
옵션 파일의 이름을 적습니다. /share 디렉토리에 업로드 후 사용할 수 있습니다.
아래 옵션 파일 사용법을 참고하여 새로 작성하면 됩니다.
그냥 비워두고 /share/commax_devinfo.json 을 직접 수정하여 사용해도 됩니다.


옵션 파일 (json 형식) 예
-----------------------
<pre><code>
{
  "Light": {
    "Number": 3,
    "commandOFF": "3101000000000032",
    "commandON": "3101010000000033",
    "responseOFF": "B1000100000000B2",
    "responseON": "B1010100000000B3",
    "commandNUM": "4",
    "responseNUM": "6",

    "statePREFIX": "30",
    "stateOFF": "B0000100000000B1",
    "stateON": "B0010100000000B2",
    "stateNUM": "6"
  },
  "Thermo": {
    "Number": 5,
    "commandOFF": "0401040000000009",
    "commandON": "040104810000008A",
    "responseOFF": "848001232300004B",
    "responseON": "848101232300004C",
    "commandCHANGE": "040103220000002A",
    "commandNUM": "4",
    "responseNUM": "6",

    "curTemp": 7,
    "setTemp": 9,
    "chaTemp": 7,

    "statePREFIX": "02",
    "stateOFF": "8280012322000048",
    "stateON": "8281012322000049",
    "stateNUM": "6",
    "stateONOFFNUM": 4
  },
  "LightBreaker": {
    "commandOFF": "2201000100000024",
    "commandON": "2201010100000025",
    "responseOFF": "A2000100001500B8",
    "responseON": "A2010100001500B9",

    "statePREFIX": "20",
    "stateOFF": "A0000100001500B6",
    "stateON": "A0010100001500B7"
  },
  "Gas": {
    "commandOFF": "1101800000000092",
    "responseOFF": "9158580000000041",

    "statePREFIX": "10",
    "stateOFF": "9050500000000030",
    "stateON": "90A0A000000000D0"
  }
}
</code></pre>

옵션 파일 (json 형식) 사용법
-----------------------
항상 hex 신호는 첫번째 기기의 신호를 기준으로 생성이 됩니다. 첫번째 신호를 입력해 주세요.
([선택] 옵션은 생략 가능합니다. 비워두지 말고 아예 옵션을 지워버리세요.)
### 기본 기기 옵션
1. Number[선택] : 같은 계열의 기기 갯수를 적습니다. (예: 등이 3개이면 3을 입력)  생략하면 1로 입력됩니다.
2. commandOFF, commandON : 기기를 켜거나 끄는 명령을 입력합니다. 비우면 아무런 명령을 보내지 않습니다.
3. responseOFF, responseON : 명령을 입력하면 오는 응답을 입력합니다. 비우면 응답을 확인하지 않습니다.
4. commandNUM[선택] : 명령 신호의 기기 번호를 의미하는 hex의 자릿수를 입력합니다. 생략하면 2번의 신호을 비교하여 자동으로 찾습니다.
5. responseNUM[선택] : 응답 신호의 기기 번호를 의미하는 hex의 자릿수를 입력합니다. 생략하면 3번의 신호를 비교하여 자동으로 찾습니다.
6. statePREFIX[필수] : 기기 상태 확인을 위한 신호의 첫 2자리를 적습니다.
7. stateOFF, stateON : 기기의 상태를 나타내는 응답을 입력합니다. 지우면 해당 기기는 엘리베이터로 인식합니다.
8. stateNUM[선택] : 상태 신호의 기기 번호를 의미하는 hex의 자릿수를 입력합니다. 생략하면 7번의 신호를 비교하여 자동으로 찾습니다.

### 온도 전용 옵션
9. commandCHANGE[필수] : 온도 변경 신호를 적습니다. 이 옵션이 입력되면 온도조절기로 인식합니다.
10. curTemp[선택] : 온도 상태 신호에서 현재 온도를 나타내는 위치를 입력합니다. 생략하면 7로 입력됩니다.
11. setTemp[선택] : 온도 상태 신호에서 설정 온도를 나타내는 위치를 입력합니다. 생략하면 9로 입력됩니다.
12. chaTemp[선택] : 온도 변경 신호에서 현재 온도를 나타내는 위치를 입력합니다. 생략하면 7로 입력됩니다.
13. stateONOFFNUM[선택] : 온도 상태 신호에서 기기의 온오프를 나타내는 위치를 입력합니다. 생략하면 4로 입력됩니다.

### commandNUM, responseNUM, stateNUM 은 무엇인가?
예를 들어 전등은
3101000000000032 명령을 주면 B1000100000000B2 의 응답신호를 보냅니다. (1번 전등 OFF)
3102000000000033 명령을 주면 B1000200000000B3 의 응답신호를 보냅니다. (2번 전등 OFF)

OFF 명령은 4번째 자리가 기기에 따라 바뀌고, OFF 응답은 6번째 자리가 기기에 따라 바뀝니다.
"commandNUM": "4" 이고 "responseNUM": "6" 입니다.

생략하면 입력된 정보를 이용하여 자동으로 자릿수를 찾습니다. 오류가 날 수도 있으니 DEBUG 옵션으로 신호가 제대로 생성되었는지 확인 후 사용하세요.


기기 등록 예
------------
<pre><code>
climate:
  - platform: mqtt
    name: "거실"
    modes:
      - "off"
      - "heat"
    mode_state_topic: "homenet/Thermo1/power/state"
    mode_command_topic: "homenet/Thermo1/power/command"
    mode_state_template: >-
     {% set modes = { 'OFF':'off', 'ON':'heat'} %}
     {{ modes[value] if value in modes.keys() else 'off' }}
    current_temperature_topic: "homenet/Thermo1/curTemp/state"
    temperature_state_topic: "homenet/Thermo1/setTemp/state"
    temperature_command_topic: "homenet/Thermo1/setTemp/command"
    precision: 1.0

light:
  - platform: mqtt
    name: "거실등1"
    state_topic: "homenet/Light1/power/state"
    command_topic: "homenet/Light1/power/command"

</code></pre>
