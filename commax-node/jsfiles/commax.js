/**
* EW11를 위한 Commax 월패드 컨트롤러
*  - Saram
* https://github.com/kimtc99/wallpad
* 2020-02-24
* 참고: https://github.com/HAKorea/addons/tree/master/wallpad
*/

const util = require('util');
const net = require('net');
const mqtt = require('mqtt');
const fs = require('fs');
fs.writeFileSync("/share/collected_signal.txt", "", {encoding: 'utf8'}); // text 파일 초기화

// 옵션 불러오기
const CONFIG = require('/data/options.json');
const mqttlog = CONFIG.mqttlog;
var find_signal = CONFIG.find_signal;
const DEBUG = CONFIG.DEBUG;
const check_signal = CONFIG.check_signal;
const ew11len = CONFIG.ew11_data_length;
const OPTION = (require('/share/commax_devinfo.json')) ? require('/share/commax_devinfo.json') : require('./commax_devinfo.json');
const Thermo = Object.keys(OPTION).find(name => OPTION[name].hasOwnProperty("commandCHANGE"))
// const Fan = Object.keys(OPTION).find(name => OPTION[name].hasOwnProperty("commandCHANGE"))
const EV = Object.keys(OPTION).find(name => !(OPTION[name].hasOwnProperty("stateOFF")))


// 변수 지정
var log = (...args) => console.log('[' + new Date().toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'}) + ']', args.join(' '));
var saveHomeState = {};
var lastReceive = new Date().getTime();
var mqttReady = false;
var queue = new Array();
var collectdata = [];
var EVontime = '';

////////////////////////////////////
// 통신 연결
////////////////////////////////////
/** ew11 */
log('Connecting ew11...');
const ew11 = net.connect(CONFIG.ew11_port, CONFIG.ew11_IP, function() {
  log('ew11 connected!!');
});
ew11.setEncoding('hex');
/** MQTT-Broker */
const client = mqtt.connect('mqtt://'+CONFIG.mqtt_server, {clientId: 'Commax-Homenet-ew11', username: CONFIG.mqtt_id, password: CONFIG.mqtt_password});
const TOPIC_PREFIX = 'homenet';
const STATE_TOPIC = 'homenet/%s/%s/state';
const DEVICE_TOPIC = 'homenet/+/+/command';
client.on('connect', () => {
    client.subscribe(DEVICE_TOPIC, (err) => {if (err) log('MQTT Subscribe fail! -', DEVICE_TOPIC) });
});

/////////////////////////////
//기기 신호 등록을 위한 함수
////////////////////////////
function pad(n, width) { // 숫자 -> 문자 변경 , 1->01
  n = n + '';
  return n.length >= width ? n : new Array(width - n.length + 1).join('0') + n;
}

function checksum(hex) { // 체크섬 계산
  var sum = [0,0];
  for (var i = 0; i < hex.length-1; i = i+2) {
    sum[0] += parseInt(hex.substring(i,i+1),16);
    sum[1] += parseInt(hex.substring(i+1,i+2),16);
  };
  if (sum[1] >= 16) {
    sum[0] += parseInt(sum[1] / 16);
    sum[1] = sum[1] % 16;
  }
  sum[0] = sum[0] % 16;

  return String(sum[0].toString(16)+sum[1].toString(16)).toUpperCase();
}

function make_hex(k,hex,chn) { // 일반 16자리 (8byte) hex 만들기
  if (chn) {
    if (hex) {
      var tmp_hex = hex.substring(0,14);
      var change = String(chn).split(',').map(Number);

      change.forEach(function(key) {
        tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
      });

      return (tmp_hex + checksum(tmp_hex)).toUpperCase();
    }
  } else {
    return hex;
  }
}

function find_hex_change(hex1,hex2) { // hex에서 기기 번호 찾기
  var numlist = [];
  if (hex1 && hex2)
    for (var k = 3; k< hex1.length-2; k++) {
      if (Number(hex1[k]) * Number(hex2[k]) == 1) numlist.push(k+1)
    }
  return String(numlist)
}

function make_hex_temp(k,curTemp,setTemp,state) { // 온도조절기 16자리 (8byte) hex 만들기
  if (state === 'OFF') { // OFF 신호 생성
    var tmp_hex = OPTION[Thermo].commandOFF.substring(0,14);
    var change = (OPTION[Thermo].commandNUM) ? String(OPTION[Thermo].commandNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].commandOFF,OPTION[Thermo].commandON).split(',').map(Number);

    tmp_hex = tmp_hex.substring(0,change-1)+String((parseInt(tmp_hex[change-1],16)+k).toString(16)) + tmp_hex.substring(change);

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else if (state === 'ON') { // ON 신호 생성
    var tmp_hex = OPTION[Thermo].commandON.substring(0,14);
    var change = (OPTION[Thermo].commandNUM) ? String(OPTION[Thermo].commandNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].commandOFF,OPTION[Thermo].commandON).split(',').map(Number);

    change.forEach(function(key) {
      tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
    });

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else if (state === 'responseOFF') { // OFF 응답 신호 생성
    var tmp_hex = OPTION[Thermo].responseOFF.substring(0,14);
    var change = (OPTION[Thermo].responseNUM) ? String(OPTION[Thermo].responseNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].responseOFF,OPTION[Thermo].responseON).split(',').map(Number);
    var curT = pad(curTemp, 2);
    var setT = pad(setTemp, 2);
    var curTnum = (OPTION[Thermo].curTemp) ? OPTION[Thermo].curTemp : 7;
    var setTnum = (OPTION[Thermo].setTemp) ? OPTION[Thermo].setTemp : 9;

    change.forEach(function(key) {
      tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
    });
    tmp_hex = tmp_hex.substring(0,curTnum-1)+String(curT)+tmp_hex.substring(curTnum+1);
    tmp_hex = tmp_hex.substring(0,setTnum-1)+String(setT)+tmp_hex.substring(setTnum+1);

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else if (state === 'responseON') { // ON 응답 신호 생성
    var tmp_hex = OPTION[Thermo].responseON.substring(0,14);
    var change = (OPTION[Thermo].responseNUM) ? String(OPTION[Thermo].responseNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].responseOFF,OPTION[Thermo].responseON).split(',').map(Number);
    var curT = pad(curTemp, 2);
    var setT = pad(setTemp, 2);
    var curTnum = (OPTION[Thermo].curTemp) ? OPTION[Thermo].curTemp : 7;
    var setTnum = (OPTION[Thermo].setTemp) ? OPTION[Thermo].setTemp : 9;

    change.forEach(function(key) {
      tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
    });
    tmp_hex = tmp_hex.substring(0,curTnum-1)+String(curT)+tmp_hex.substring(curTnum+1);
    tmp_hex = tmp_hex.substring(0,setTnum-1)+String(setT)+tmp_hex.substring(setTnum+1);

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else if (state === 'responseON2') { // ON 응답 신호 생성
    var tmp_hex = OPTION[Thermo].responseON.substring(0,14);
    var change = (OPTION[Thermo].responseNUM) ? String(OPTION[Thermo].responseNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].responseOFF,OPTION[Thermo].responseON).split(',').map(Number);
    var curT = pad(curTemp, 2);
    var setT = pad(setTemp, 2);
    var curTnum = (OPTION[Thermo].curTemp) ? OPTION[Thermo].curTemp : 7;
    var setTnum = (OPTION[Thermo].setTemp) ? OPTION[Thermo].setTemp : 9;

    change.forEach(function(key) {
      tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
    });
    tmp_hex = tmp_hex.substring(0,curTnum-1)+String(curT)+tmp_hex.substring(curTnum+1);
    tmp_hex = tmp_hex.substring(0,setTnum-1)+String(setT)+tmp_hex.substring(setTnum+1);
    tmp_hex = tmp_hex.substring(0,3)+String(3)+tmp_hex.substring(4);

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else if (state === 'CHANGE') { // 온도 변경 신호 생성
    var tmp_hex = OPTION[Thermo].commandCHANGE.substring(0,14);
    var change = (OPTION[Thermo].commandNUM) ? String(OPTION[Thermo].commandNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].commandOFF,OPTION[Thermo].commandON).split(',').map(Number);
    var setT = pad(setTemp, 2);
    var chaTnum = (OPTION[Thermo].chaTemp) ? OPTION[Thermo].chaTemp : 7;

    change.forEach(function(key) {
      tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
    });
    tmp_hex = tmp_hex.substring(0,chaTnum-1)+String(setT)+tmp_hex.substring(chaTnum+1);

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else if (state === 'stateOFF') { // OFF 상태 중 온도 신호 생성
    var tmp_hex = OPTION[Thermo].stateOFF.substring(0,14);
    var change = (OPTION[Thermo].stateNUM) ? String(OPTION[Thermo].stateNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].stateOFF,OPTION[Thermo].stateON).split(',').map(Number);
    var curT = pad(curTemp, 2);
    var setT = pad(setTemp, 2);
    var curTnum = (OPTION[Thermo].curTemp) ? OPTION[Thermo].curTemp : 7;
    var setTnum = (OPTION[Thermo].setTemp) ? OPTION[Thermo].setTemp : 9;

    change.forEach(function(key) {
      tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
    });
    tmp_hex = tmp_hex.substring(0,curTnum-1)+String(curT)+tmp_hex.substring(curTnum+1);
    tmp_hex = tmp_hex.substring(0,setTnum-1)+String(setT)+tmp_hex.substring(setTnum+1);

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else if (state === 'stateON') { // ON 상태 중 온도 신호 생성
    var tmp_hex = OPTION[Thermo].stateON.substring(0,14);
    var change = (OPTION[Thermo].stateNUM) ? String(OPTION[Thermo].stateNUM).split(',').map(Number) : find_hex_change(OPTION[Thermo].stateOFF,OPTION[Thermo].stateON).split(',').map(Number);
    var curT = pad(curTemp, 2);
    var setT = pad(setTemp, 2);
    var curTnum = (OPTION[Thermo].curTemp) ? OPTION[Thermo].curTemp : 7;
    var setTnum = (OPTION[Thermo].setTemp) ? OPTION[Thermo].setTemp : 9;

    change.forEach(function(key) {
      tmp_hex = tmp_hex.substring(0,key-1)+String((parseInt(tmp_hex[key-1],16)+k).toString(16)) + tmp_hex.substring(key);
    });
    tmp_hex = tmp_hex.substring(0,curTnum-1)+String(curT)+tmp_hex.substring(curTnum+1);
    tmp_hex = tmp_hex.substring(0,setTnum-1)+String(setT)+tmp_hex.substring(setTnum+1);

    return (tmp_hex + checksum(tmp_hex)).toUpperCase();

  } else {
    return;
  }
}

function make_device_info(device) { // 기기 등록을 위한 함수
  var num = (device.Number) ? device.Number : 1;
  var devlist = {Num: num};
  if (ew11len == 32) {
    devlist['prefix'] = (device.statePREFIX.length > 2) ? device.statePREFIX.substring(0,2).toUpperCase() : device.statePREFIX.toUpperCase();
  } else if (ew11len == 16) {
    devlist['prefix'] = device.stateOFF.substring(0,2).toUpperCase();
  } else {
    log('[ERROR] ew11_data_length must be 16 or 32.')
  }
  var arr1 = "", arr2 = "", arr3 = "", arr4 = "", arr5 = "", arr6 = "";
  const cmdNUM = (device.commandNUM) ? device.commandNUM : find_hex_change(device.commandOFF,device.commandON);
  const staNUM = (device.stateNUM) ? device.stateNUM : find_hex_change(device.stateOFF,device.stateON);
  const resNUM = (device.responseNUM) ? device.responseNUM : find_hex_change(device.responseOFF,device.responseOFF);
  for (var k = 0; k < num; k++) {
    arr1 = make_hex(k,device.commandOFF,cmdNUM);
    arr2 = make_hex(k,device.commandON,cmdNUM);
    arr3 = make_hex(k,device.stateOFF,staNUM);
    arr4 = make_hex(k,device.stateON,staNUM);
    arr5 = make_hex(k,device.responseOFF,resNUM);
    arr6 = make_hex(k,device.responseON,resNUM);
    devlist[k] = {commandOFF: arr1, commandON: arr2, stateOFF: arr3, stateON: arr4, responseOFF: arr5, responseON: arr6};
  }
  return devlist;
}
// 기기 신호 등록을 위한 함수 끝 /////////

/////////////////////////////
// 시작
////////////////////////////
// 기기 리스트 생성
var DEVICE_LISTS = {};
for (var k in OPTION) {
  DEVICE_LISTS[k] = make_device_info(OPTION[k]);
}
//
// 기기의 시작 문자열 수집
var prefix_list = {};
for (var key in DEVICE_LISTS) {
  prefix_list[DEVICE_LISTS[key].prefix] = key;  // state 시작 문자열 등록
}
// DEBUG
if (DEBUG) {
  log('[DEBUG] ----------------------');
  log('[DEBUG] Registered device lists..');
  log('[DEBUG] DEVICE_LISTS: '+ JSON.stringify(DEVICE_LISTS));
  log('[DEBUG] FOUND::: Thermostat: '+ Thermo +', Elevator: '+ EV);
  log('[DEBUG] ----------------------');
}

////////////////////////////
// 상태 변경 함수
////////////////////////////
function updateState(device, idx, onoff) { // 일반 상태 변경
  if (onoff){
    const saveddevice = Object.keys(saveHomeState);
    const deviceId = device + String(idx+1);
    const state = 'power';
    const key = deviceId+state;

    // 상태 업데이트
    if (saveHomeState[saveddevice.find(list => list === key)] === onoff) {
      return
    } else {
      saveHomeState[key] = onoff;
      var topic = util.format(STATE_TOPIC, deviceId, state);
      if (mqttlog) log('[LOG] MQTT >> HA :', topic, '->', onoff);
      client.publish(topic, onoff, {retain: true});
    }
  }
  return;
}

function updateTemp(device, idx, temperature) { // 온도조절기 상태 변경
  const saveddevice = Object.keys(saveHomeState);
  var key = "";
  var deviceId = device + String(idx+1);
  var topic = "";

  // 상태 업데이트
  for (var state in temperature) {
    key = deviceId+state;
    var temp = saveHomeState[saveddevice.find(list => list === key)];

    if ( temp === temperature[state]) {
      // if (DEBUG)  log('[DEBUG] '+ deviceId + ' is already ' + state + temperature[state]);
    } else {
      saveHomeState[key] = temperature[state];
      topic = util.format(STATE_TOPIC, deviceId, state);
      client.publish(topic, temperature[state], {retain: true});
      if (mqttlog) log('[LOG] MQTT >> HA :', topic, '->', temperature[state]);
    }
  }
  return
}
// 함수 끝

// EV 초기화
if (EV) updateState(EV, 0, 'OFF');

/////////////////////////////
// 통신
////////////////////////////
ew11.on('data', function (data) { // ew11과 통신
  lastReceive = new Date().getTime();
  data = data.toUpperCase();

  var device = prefix_list[Object.keys(prefix_list).find(list => list === data.substring(0,2))]
  var onoff ='', temperature={curTemp: "" , setTemp: ""}, index = 0;

  // 엘리베이터 신호을 받은 경우
  if (EV && device === EV) {
    updateState(device, 0, 'ON');
    EVontime = lastReceive;
    for (var k = 0; k < queue.length; k++) {
      if (queue[k].pushcmd === OPTION[EV].commandON) {
        queue.splice(k, 1);
        if (DEBUG) log('[DEBUG] EV is comming. Delete an EV queue: '+JSON.stringify(list));
        break;
      }
    return;
    }
  }

  // 실행한 명령 삭제
  Outer: for (var k = 0; k < queue.length; k++) {
    list = queue[k];
    Inner: for (var j = 0; j < list.recvcmd.length; j++) {
      if (data.indexOf(list.recvcmd[j]) != -1) {
        queue.splice(k, 1);
        if (DEBUG) log('[DEBUG] Found matched hex: ' + data + '. Delete a queue: '+JSON.stringify(list));
        break Outer;
      }
    }
  }

  if (device && data.length == ew11len) {
    if (check_signal) log("ew11:: Receive a signal: "+ data);
    const datahex = data.substring(ew11len-16);
    const num = DEVICE_LISTS[device].Num;
    if (device === Thermo) { // 온도조절기
      var curTnum = (OPTION[Thermo].curTemp) ? OPTION[Thermo].curTemp : 7;
      var setTnum = (OPTION[Thermo].setTemp) ? OPTION[Thermo].setTemp : 9;
      temperature.curTemp = datahex.substring(curTnum-1,curTnum+1);
      temperature.setTemp = datahex.substring(setTnum-1,setTnum+1);

      const onoffNUM = (OPTION[Thermo].stateONOFFNUM) ? OPTION[Thermo].stateONOFFNUM : 4;
      const staNUM = (OPTION[Thermo].stateNUM) ? OPTION[Thermo].stateNUM : find_hex_change(OPTION[Thermo].stateOFF,OPTION[Thermo].stateON);
      index = Number(datahex[staNUM-1])-1;
      onoff = (Number(datahex[onoffNUM-1]) > 0) ? "ON" : "OFF";

      updateState(device, index, onoff);
      updateTemp(device, index, temperature);
      if (check_signal) log('[DEBUG] STATUS:: ' + device + String(index+1) + ": "+onoff+', curTemp: '+ temperature.curTemp+", setTemp: "+temperature.setTemp);
    } else { // 일반 장치
      for(var k in DEVICE_LISTS[device]) {
        if (data.indexOf(DEVICE_LISTS[device][k].stateON) != -1) {
          onoff = "ON";
          index = Number(k);
        } else if (data.indexOf(DEVICE_LISTS[device][k].stateOFF) != -1) {
          onoff = "OFF";
          index = Number(k);
        }
      }
      if (onoff) updateState(device, index, onoff);
      if (check_signal) log('[DEBUG] STATUS:: ' + device + String(index+1) + ": "+onoff);
    }
  } else {
    if (find_signal) {
      if (collectdata.length < 100) {
        if (!collectdata.includes(data)) {
          log("[NEW] Unregisterd signal : " + data);
          collectdata.push(data);

          fs.appendFile("/share/collected_signal.txt", '[' + new Date().toLocaleString('ko-KR', {timeZone: 'Asia/Seoul'}) + '] :: '+data +'\n', { encoding: 'utf8', flag: 'a' },() => {});
        }
      } else {
        log("[Complete] Collect 100 signals. See : /share/collected_signal.txt");
        collectdata = [];
        find_signal = false;
      }
    }
  }
  if (saveHomeState[EV+String(1)+'power'] === 'ON') {
    if (lastReceive - EVontime > 1000) updateState(EV, 0, 'OFF');
  }
});

client.on('message', (topic, message) => { // MQTT 통신
  if(mqttReady) {
    var topics = topic.split('/');
    var key = topics[1] + topics[2];
    var value = message.toString();
    if (topics[0] === TOPIC_PREFIX) {
      if (mqttlog) log('[LOG] HA >> MQTT :', topic + '->' + value);
      if (saveHomeState.hasOwnProperty(key)) {
        var index = topics[1].substring(topics[1].length - 1) - 1;
        var device = topics[1].substring(0,topics[1].length - 1);
        if (device === Thermo) { //온도조절기 전용
          var curTemp = saveHomeState[topics[1]+'curTemp'];
          var setTemp = saveHomeState[topics[1]+'setTemp'];
          if (value === 'off') { // 받은 명령을 코드에 맞게 변경
            value = 'OFF';
          } else if (value === 'heat') {
            value = 'ON'
          }
          if (topics[2] === 'power') { // 온오프 명령을 받은 경우
            if (value === saveHomeState[key]) { // 이미 상태가 변경된 경우
              if (DEBUG)  log('[DEBUG] '+ topics[1] + ' is already ' + value);
            } else {
              var onoff = value;
              var pushcmd = make_hex_temp(index,curTemp,setTemp,onoff);
              var recvcmd = [];
              var lists = ['state'+onoff,'response'+onoff,'responseON2'];

              if (onoff === 'OFF') lists.pop('responseON2')
              lists.forEach((item) => {
                recvcmd.push(make_hex_temp(index,curTemp,setTemp,item));
              });
              if (pushcmd) {
                queue.push({pushcmd: pushcmd, recvcmd: recvcmd, count: 0});
                if (DEBUG)  log('[DEBUG] Queued::: pushcmd: ' + pushcmd + ' , recvcmd: '+recvcmd);
              } else {
              if (DEBUG) log('[DEBUG] There is no command for', topic);
              }
            }
          } else if (topics[2] === 'setTemp') { // 설정 온도 변경 명령을 받은 경우
            if (setTemp == Number(value)) { // 이미 설정된 온도와 같은 경우
              if (DEBUG)  log('[DEBUG] '+ topics[1] + ' is already set:' + setTemp);
            } else {
              setTemp = pad(Number(value),2);
              var onoff = 'ON';
              var pushcmd = make_hex_temp(index,curTemp,setTemp,'CHANGE');
              if (pushcmd) {
                var recvcmd = [];
                var lists = ['state'+onoff,'response'+onoff,'responseON2'];

                lists.forEach((item) => {
                  recvcmd.push(make_hex_temp(index,curTemp,setTemp,item));
                });
                queue.push({pushcmd: pushcmd, recvcmd: recvcmd, count: 0});
                if (DEBUG)  log('[DEBUG] Queued::: pushcmd: ' + pushcmd + ' , recvcmd: '+recvcmd);
              } else {
              if (DEBUG) log('[DEBUG] There is no command for', topic);
              }
            }
          }
        } else { // 일반 장치
          if (topics[2] === 'power') {
            if (value === saveHomeState[key]) {
              if (DEBUG)  log('[DEBUG] '+ topics[1] + ' is already ' + value);
            } else {
              var onoff = value;
              const pushcmd = DEVICE_LISTS[device][index]["command" + onoff];
              if (pushcmd) {
                const recvcmd = [DEVICE_LISTS[device][index]["response" + onoff], DEVICE_LISTS[device][index]["state" + onoff]];
                queue.push({pushcmd: pushcmd, recvcmd: recvcmd, count: 0});

                if (DEBUG)  log('[DEBUG] Queued::: pushcmd: ' + pushcmd + ' , recvcmd: '+recvcmd);
              } else {
                if (DEBUG) log('[DEBUG] There is no command for', topic);
              }
            }
          }
        }
      }
    }
  }
});

const commandProc = () => { // ew11로 신호 전송
  if (queue.length == 0) {
    return;
  } else {
    var delay = (new Date().getTime())-lastReceive;
    if(delay < OPTION.sendDelay) return; //기존 명령과 겹치지 않도록 딜레이

    var cmd = queue.shift();
    let cmdHex = Buffer.alloc(cmd.pushcmd.length/2,cmd.pushcmd,'hex');

    ew11.write(cmdHex, (err) => {if(err) return log('[ERROR] ew11:: Error to send a signal on ew11: ', err.message); });
    lastReceive = new Date().getTime();
    if (DEBUG) log('[DEBUG] ew11:: Send a signal: ' + cmd.pushcmd + ' (delay:'+delay+'ms) ');
    cmd.count = cmd.count + 1;
    if (cmd.count < 20) {
      queue.push(cmd);
    } else { // 20번 이상 같은 신호를 보내면 삭제
      log('[ERROR] ew11:: Send over 20 times. Send Failure. Delete a signal: ' + cmd.pushcmd);
    }

  }
}

const debugProc = () => { // 디버그 출력
  if (DEBUG) {
    log('[DEBUG] saveHomeState: '+ JSON.stringify(saveHomeState));
    log('[DEBUG] queue: '+ JSON.stringify(queue));
  }
}

setTimeout(() => {mqttReady=true; log('ew11:: Ready to receive a signal ...')}, CONFIG.mqtt_receiveDelay);
setInterval(commandProc, 100);
setInterval(debugProc, 10000);
