Python으로 만든 코맥스 월패드 - socket전용
===================================
처음 작동 시 자동으로 기기를 찾습니다.


설치 방법
-------
1. Supervisor -> ADD-ON STORE 이동
2. "https://github.com/kimtc99/wallpad" 를 Repositories 에 추가하고 새로 고침을 합니다.
3. Saram's Repository 항목으로 이동하여 "COMMAX Wallpad Controller with Python"를 선택하고 INSTALL을 눌러 설치합니다.

설정 화면
-------
<pre><code>
"DEBUG": false,
"mqtt_log": true,
"check_all_received_signal": false,
"save_unregistered_signal": true,
"ew11_IP": "192.168.x.x",
"ew11_port": 8899,
"mqtt_server": "192.168.x.x",
"mqtt_id": "id",
"mqtt_password": "pwd"
</code></pre>

#### DEBUG : true / false
작업 내역과 저장된 상태 전부를 출력합니다.
#### mqttlog : true / false
MQTT 전송 신호를 출력합니다.
#### check_all_received_signal : true / false
ew11을 통해 보내거나 받은 신호를 출력합니다.
#### save_unregistered_signal : true / false
등록되지 않은 신호 20개를 출력하고, /share/collected_signal.txt 에 저장합니다.

#### ew11_IP : 문자
ew11 의 IP 주소를 적습니다. ex) 192.168.0.2
#### ew11_port : 숫자
ew11 의 포트 번호를 적습니다. ex) 8899

#### mqtt_server : 문자
mqtt 서버의 IP 주소를 적습니다. ex) 192.168.0.2
#### mqtt_id : 문자
mqtt 서버 사용자의 아이디를 적습니다.
#### mqtt_password": 문자
mqtt 서버 사용자의 암호를 적습니다. 숫자암호인 경우 꼭 따음표 "1234"를 해주세요.

기기 정보 파일 (commax_found_device.json) 사용법
-------------------------------------------
처음 프로그램을 실행하면 20초 동안 신호를 수집하여 share 폴더에 기기 정보 파일 commax_found_device.json을 만듭니다.
기기 검색 단계 20초 동안 가스잠금장치와 일괄전등스위치를 껐다 켜면 수집에 도움이 됩니다.
만약 수집된 내용이 집의 신호와 다른 경우 파일을 수정해주세요.

기기 정보 파일 (commax_found_device.json) 예
-----------------------
<pre><code>
{
  "Light": {
    "Number": 3,
    "commandOFF": "3101000000000032",
    "commandON": "3101010000000033",
    "commandNUM": 4,

    "statePREFIX": "30",
    "stateOFF": "B0000100000000B1",
    "stateON": "B0010100000000B2",
    "stateNUM": 6
  },
  "Thermo": {
    "Number": 5,
    "commandOFF": "0401040000000009",
    "commandON": "040104810000008A",
    "commandCHANGE": "040103220000002A",
    "commandNUM": 4,

    "curTemp": 7,
    "setTemp": 9,
    "chaTemp": 7,

    "statePREFIX": "02",
    "stateOFF": "8280012322000048",
    "stateON": "8281012322000049",
    "stateNUM": 6,
    "stateONOFFNUM": 4
  },
  "LightBreaker": {
    "Number": 1,
    "commandOFF": "2201000100000024",
    "commandON": "2201010100000025",

    "statePREFIX": "20",
    "stateOFF": "A0000100001500B6",
    "stateON": "A0010100001500B7"
  },
  "Gas": {
    "Number": 1,
    "commandOFF": "1101800000000092",

    "statePREFIX": "10",
    "stateOFF": "9050500000000030",
    "stateON": "90A0A000000000D0"
  },
  "Fan": {
    "Number": 0,
    "commandOFF": "780101000000007A",
    "commandON": "780102010000007C",
    "speedNUM": 8,

    "statePREFIX": "76",
    "stateOFF": "F6000100000000F7",
    "stateON": "F6040101000000FC"
  },
  "EV": {
    "Number": 1,
    "commandOFF": "220140070000006A",

    "statePREFIX": "23"
  }
}
</code></pre>

기기 정보 파일 (commax_found_device.json) 옵션 설명
---------------------------------------------
전등이나 보일러의 hex 신호는 항상 첫번째 기기의 신호를 기준으로 생성이 됩니다. 첫번째 신호를 입력해 주세요.
### 기본 기기 옵션
1. Number : 같은 계열의 기기 갯수 (0 인 경우 해당 장치는 작동하지 않습니다.)
2. commandOFF, commandON : 기기를 켜거나 끄는 명령
3. commandNUM : 명령 신호의 기기 번호를 의미하는 hex의 자릿수
4. statePREFIX : 기기 상태 확인을 위한 신호의 첫 2자리
5. stateOFF, stateON : 기기의 상태를 나타내는 응답
6. stateNUM : 상태 신호의 기기 번호를 의미하는 hex의 자릿수

### 온도 전용 옵션
9. commandCHANGE : 온도 변경 신호
10. curTemp : 온도 상태 신호에서 현재 온도를 나타내는 위치
11. setTemp : 온도 상태 신호에서 설정 온도를 나타내는 위치
12. chaTemp : 온도 변경 신호에서 현재 온도를 나타내는 위치
13. stateONOFFNUM : 온도 상태 신호에서 기기의 온오프를 나타내는 위치

### commandNUM, stateNUM 은 무엇인가?
예를 들어 전등은
3101000000000032 명령을 주면 B1000100000000B2 의 응답신호를 보냅니다. (1번 전등 OFF)
3102000000000033 명령을 주면 B1000200000000B3 의 응답신호를 보냅니다. (2번 전등 OFF)

OFF 명령은 4번째 자리가 기기에 따라 바뀌고, OFF 응답은 6번째 자리가 기기에 따라 바뀝니다.
"commandNUM": "4"입니다.


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
