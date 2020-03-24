import paho.mqtt.client as mqtt
import socket
import json
import time
import traceback
import asyncio

share_dir = '/share'
config_dir = '/data'
data_dir = '/pycommax'

def log(string):
    date = time.strftime('%Y-%m-%d %p %I:%M:%S', time.localtime())
    print('[{}] {}'.format(date, string))
    return


def find_device(config):
    # 접속 정보 설정
    data_size = 32
    socket_size = int(data_size / 2)
    socket_address = (config['socket_IP'], config['socket_port'])

    # start with a socket at 5-second timeout
    log("Creating the socket to find devices..")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5.0)
    kk = 0
    while kk < 1:
        # check and turn on TCP Keepalive
        x = sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
        if x == 0:
            log('Socket Keepalive off, turning on')
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            x = sock.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE)
            log('setsockopt={}'.format(x))
        else:
            log('Socket Keepalive already on')

        try:
            sock.connect(socket_address)
            kk = 1
        except socket.error:
            log('Socket connect failed! Loop up and try socket again')
            traceback.print_exc()
            time.sleep(5.0)
            kk = 0
            continue

    collect_data = []
    target_time = time.time() + 20
    log('Socket connect worked! Find devices for 20s...')
    while time.time() < target_time:
        try:
            req = sock.recv(socket_size)
        except socket.timeout:
            log('Socket timeout, loop and try recv() again')
            time.sleep(5.0)
            # traceback.print_exc()
            continue
        except:
            traceback.print_exc()
            log('Other Socket err, exit and try creating socket again')
            # break from loop
            break

        data = req.hex().upper()
        if len(data) == data_size:
            collect_data.append(data)

    sock.close()
    collect_data = list(set(collect_data))
    with open(data_dir + '/commax_devinfo.json') as file:
        dev_info = json.load(file)

    collected_list = {}
    for name in dev_info:
        collected_list[name] = sorted(
            list(filter(lambda hex_data: hex_data.startswith(dev_info[name]['statePREFIX']), collect_data)))

    for key in collected_list:
        if key == 'Thermo' or key == 'Light':
            dev_info[key]['Number'] = len(sorted([hex_data[:16] for hex_data in collected_list[key]]))
        elif key == 'LightBreaker' or key == 'Gas':
            if len(collected_list[key]) < 2:
                dev_info[key]['Number'] = len(collected_list[key])
            else:
                dev_info[key]['Number'] = 1
                dev_info[key]['stateOFF'] = collected_list[key][0][16:]
                dev_info[key]['stateON'] = collected_list[key][1][16:]
        elif key == 'Fan' or key == 'EV':
            dev_info[key]['Number'] = 0 if len(collected_list[key]) < 1 else 1

    with open(share_dir + '/commax_found_device.json', 'w', encoding='utf-8') as make_file:
        json.dump(dev_info, make_file, indent="\t")
        log('Writing device_list to : /share/commax_found_device.json')
    return dev_info


def do_work(config, device_list):
    # 변수 지정
    mqtt_log = config['mqtt_log']
    find_signal = config['save_unregistered_signal']
    debug = config['DEBUG']
    check_signal = config['check_all_received_signal']

    STATE_TOPIC = 'homenet/{}/{}/state'

    def pad(value):
        value = int(value)
        return '0' + str(value) if value < 10 else str(value)

    # checksum 계산
    def checksum(input_hex):
        try:
            input_hex = input_hex[:14]
            s1 = sum([int(input_hex[val], 16) for val in range(0, 14, 2)])
            s2 = sum([int(input_hex[val + 1], 16) for val in range(0, 14, 2)])
            s1 = s1 + int(s2 // 16)
            s1 = s1 % 16
            s2 = s2 % 16
            return input_hex + format(s1, 'X') + format(s2, 'X')
        except:
            return None

    def make_hex(k, input_hex, change):
        if input_hex:
            try:
                change = int(change)
                input_hex = '{}{}{}'.format(input_hex[:change - 1], int(input_hex[change - 1]) + k, input_hex[change:])
                return checksum(input_hex)
            except:
                return input_hex
        else:
            return None

    def make_hex_temp(k, curTemp, setTemp, state):  # 온도조절기 16자리 (8byte) hex 만들기
        if state == 'OFF' or state == 'ON' or state == 'CHANGE':
            tmp_hex = device_list['Thermo'].get('command' + state)
            change = device_list['Thermo'].get('commandNUM')
            tmp_hex = make_hex(k, tmp_hex, change)
            if state == 'CHANGE':
                setT = pad(setTemp)
                chaTnum = OPTION['Thermo'].get('chaTemp')
                tmp_hex = tmp_hex[:chaTnum - 1] + setT + tmp_hex[chaTnum + 1:]
            return checksum(tmp_hex)
        else:
            tmp_hex = device_list['Thermo'].get(state)
            change = device_list['Thermo'].get('stateNUM')
            tmp_hex = make_hex(k, tmp_hex, change)
            setT = pad(setTemp)
            curT = pad(curTemp)
            curTnum = OPTION['Thermo'].get('curTemp')
            setTnum = OPTION['Thermo'].get('setTemp')
            tmp_hex = tmp_hex[:setTnum - 1] + setT + tmp_hex[setTnum + 1:]
            tmp_hex = tmp_hex[:curTnum - 1] + curT + tmp_hex[curTnum + 1:]
            if state == 'stateOFF':
                return checksum(tmp_hex)
            elif state == 'stateON':
                tmp_hex2 = tmp_hex[:3] + str(3) + tmp_hex[4:]
                return [checksum(tmp_hex), checksum(tmp_hex2)]
            return None

    def make_device_info(device):
        num = device.get('Number')
        if num > 0:
            prefix = device.get('statePREFIX')
            arr = {k + 1: {cmd + onoff: make_hex(k, device.get(cmd + onoff), device.get(cmd + 'NUM'))
                           for cmd in ['command', 'state'] for onoff in ['ON', 'OFF']} for k in range(num)}
            if prefix == '76':
                tmp_hex = arr[1]['stateON']
                change = device_list['Fan'].get('speedNUM')
                arr[1]['stateON'] = [make_hex(k, tmp_hex, change) for k in range(3)]
                tmp_hex = device_list['Fan'].get('commandCHANGE')
                arr[1]['CHANGE'] = [make_hex(k, tmp_hex, change) for k in range(3)]

            arr['Num'] = num
            arr['prefix'] = prefix
            return arr
        else:
            return None

    DEVICE_LISTS = {}
    for name in device_list:
        device_info = make_device_info(device_list[name])
        if device_info:
            DEVICE_LISTS[name] = device_info
    prefix_list = {DEVICE_LISTS[name]['prefix']: name for name in DEVICE_LISTS}
    if debug:
        log('[DEBUG] ----------------------')
        log('[DEBUG] Registered device lists..')
        log('DEVICE_LISTS: {}'.format(DEVICE_LISTS))
        log('[DEBUG] ----------------------')

    HOMESTATE = {}
    QUEUE = []

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log("MQTT connection successful!!")
            client.subscribe('homenet/#', 0)
        else:
            errcode = {1: 'Connection refused - incorrect protocol version',
                       2: 'Connection refused - invalid client identifier',
                       3: 'Connection refused - server unavailable',
                       4: 'Connection refused - bad username or password',
                       5: 'Connection refused - not authorised'}
            log(errcode[rc])

    def on_message(client, userdata, msg):
        topics = msg.topic.split('/')
        if topics[-1] == 'command':
            key = topics[1] + topics[2]
            device = topics[1][:-1]
            idx = int(topics[1][-1])
            value = msg.payload.decode('utf-8')
            if mqtt_log:
                log('[LOG] HA >> MQTT : {} -> {}'.format(msg.topic, value))
            if device in DEVICE_LISTS:
                if HOMESTATE.get(key) and value != HOMESTATE.get(key):
                    if device == 'Thermo':
                        curTemp = HOMESTATE.get(topics[1]+'curTemp')
                        setTemp = HOMESTATE.get(topics[1]+'setTemp')
                        if value == 'off':
                            value = 'OFF'
                        elif value == 'heat':
                            value = 'ON'
                        if topics[2] == 'power':
                            sendcmd = make_hex_temp(idx-1, curTemp, setTemp, value)
                            recvcmd = make_hex_temp(idx-1, curTemp, setTemp, 'state'+value)
                            if sendcmd:
                                QUEUE.append({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'count': 0})
                                if debug:
                                    log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}'.format(sendcmd, recvcmd))
                        elif topics[2] == 'setTemp':
                            value = int(float(value))
                            if value == int(setTemp):
                                if debug:
                                    log('[DEBUG] {} is already set: {}'.format(topics[1], value))
                            else:
                                setTemp = value
                                sendcmd = make_hex_temp(idx-1, curTemp, setTemp, 'CHANGE')
                                recvcmd = make_hex_temp(idx-1, curTemp, setTemp, 'stateON')
                                if sendcmd:
                                    QUEUE.append({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'count': 0})
                                    if debug:
                                        log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}'.format(sendcmd, recvcmd))
                    elif device == 'Fan':
                        if value == 'off':
                            value = 'OFF'
                        if topics[2] == 'power':
                            sendcmd = DEVICE_LISTS[device][idx].get('command' + value)
                            recvcmd = DEVICE_LISTS[device][idx].get('state' + value) if value == 'ON' else [DEVICE_LISTS[device][idx].get('state' + value)]
                            QUEUE.append({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'count': 0})
                            if debug:
                                log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}'.format(sendcmd, recvcmd))
                        elif topics[2] == 'speed':
                            speed_list = ['low', 'medium', 'high']
                            if value in speed_list:
                                index = speed_list.index(value)
                                sendcmd = DEVICE_LISTS[device][idx]['CHANGE'][index]
                                recvcmd = [DEVICE_LISTS[device][idx].get('state' + value)]
                                QUEUE.append({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'count': 0})
                                if debug:
                                    log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}'.format(sendcmd, recvcmd))
                    else:
                        sendcmd = DEVICE_LISTS[device][idx].get('command' + value)
                        if sendcmd:
                            recvcmd = [DEVICE_LISTS[device][idx].get('state' + value, 'NULL')]
                            QUEUE.append({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'count': 0})
                            if debug:
                                log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}'.format(sendcmd, recvcmd))
                else:
                    if debug:
                        log('[DEBUG] {} is already set: {}'.format(key, value))
            else:
                if debug:
                    log('[DEBUG] There is no commands for {}'.format(msg.topic))

    mqtt_client = mqtt.Client('homenet-commax-python')
    mqtt_client.username_pw_set(config['mqtt_id'], config['mqtt_password'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect_async(config['mqtt_server'])
    mqtt_client.loop_start()

    def update_state(device, idx, onoff):
        state = 'power'
        deviceID = device + str(idx + 1)
        key = deviceID + state

        if onoff != HOMESTATE.get(key):
            HOMESTATE[key] = onoff
            topic = STATE_TOPIC.format(deviceID, state)
            mqtt_client.publish(topic, onoff.encode())
            if mqtt_log:
                log('[LOG] MQTT >> HA : {} >> {}'.format(topic, onoff))
        else:
            if debug:
                log('[DEBUG] {} is already set: {}'.format(deviceID, onoff))
        return

    def update_fan(device, idx, onoff):
        deviceID = device + str(idx + 1)
        if onoff == 'ON' or onoff == 'OFF':
            state = 'power'
            key = deviceID + state
        else:
            try:
                speed_list = ['low', 'medium', 'high']
                onoff = speed_list[int(onoff)-1]
                state = 'speed'
                key = deviceID + state
            except:
                return
        if onoff != HOMESTATE.get(key):
            HOMESTATE[key] = onoff
            topic = STATE_TOPIC.format(deviceID, state)
            mqtt_client.publish(topic, onoff.encode())
            if mqtt_log:
                log('[LOG] MQTT >> HA : {} >> {}'.format(topic, onoff))
        else:
            if debug:
                log('[DEBUG] {} is already set: {}'.format(deviceID, onoff))
        return

    def update_temperature(idx, curTemp, setTemp):
        deviceID = 'Thermo' + str(idx + 1)
        temperature = {'curTemp': pad(curTemp), 'setTemp': pad(setTemp)}
        for state in temperature:
            key = deviceID + state
            val = temperature[state]
            if val != HOMESTATE.get(key):
                HOMESTATE[key] = val
                topic = STATE_TOPIC.format(deviceID, state)
                mqtt_client.publish(topic, val.encode())
                if mqtt_log:
                    log('[LOG] MQTT >> HA : {} -> {}'.format(topic, val))
            else:
                if debug:
                    log('[DEBUG] {} is already set: {}'.format(key, val))
        return

    async def recv_from_socket():
        data_size = 32
        socket_size = int(data_size / 2)

        COLLECTDATA = []
        fsignal = find_signal
        EVontime = time.time()
        if 'EV' in DEVICE_LISTS:
            update_state('EV', 0, 'OFF')

        while True:
            reader, writer = await asyncio.open_connection(config['socket_IP'], config['socket_port'])
            while True:
                try:
                    req = await reader.read(socket_size)
                    if HOMESTATE.get('EV1power') == 'ON':
                        if EVontime < time.time():
                            update_state('EV', 0, 'OFF')

                    data = req.hex().upper()
                    if check_signal:
                        log('[SIGNAL] receved: {}'.format(data))
                    data_prefix = data[:2]
                    if data_prefix in prefix_list:
                        device_name = prefix_list[data_prefix]
                        if len(data) == 32:
                            data = data[16:]
                            for que in QUEUE:
                                if data in que['recvcmd']:
                                    QUEUE.remove(que)
                                    if debug:
                                        log('[DEBUG] Found matched hex: {}. Delete a queue: {}'.format(data, que))
                            if device_name == 'Thermo' and data.startswith(device_list['Thermo']['stateOFF'][:2]):
                                curTnum = device_list['Thermo']['curTemp']
                                setTnum = device_list['Thermo']['setTemp']
                                curT = data[curTnum - 1:curTnum + 1]
                                setT = data[setTnum - 1:setTnum + 1]
                                onoffNUM = device_list['Thermo']['stateONOFFNUM']
                                staNUM = device_list['Thermo']['stateNUM']
                                index = int(data[staNUM - 1]) - 1
                                onoff = 'ON' if int(data[onoffNUM - 1]) > 0 else 'OFF'

                                update_state(device_name, index, onoff)
                                update_temperature(index, curT, setT)
                            elif device_name == 'Fan':
                                if data in DEVICE_LISTS['Fan']['stateON']:
                                    update_state('Fan', 0, 'ON')
                                    speed = DEVICE_LISTS['Fan']['stateON'].index(data)
                                    update_fan('Fan', 0, speed)
                            else:
                                num = DEVICE_LISTS[device_name]['Num']
                                state = [DEVICE_LISTS[device_name][k+1]['stateOFF'] for k in range(num)] + [DEVICE_LISTS[device_name][k+1]['stateON'] for k in range(num)]
                                if data in state:
                                    index = state.index(data)
                                    onoff, index = ['OFF', index] if index < num else ['ON', index - num]
                                    update_state(device_name, index, onoff)
                        else:
                            if device_name == 'EV':
                                update_state('EV', 0, 'ON')
                                EVontime = time.time() + 1
                    else:
                        if fsignal:
                            if len(COLLECTDATA) < 20:
                                if data not in COLLECTDATA:
                                    log('[FOUND] signal: {}'.format(data))
                                    COLLECTDATA.append(data)
                                    COLLECTDATA = list(set(COLLECTDATA))
                            else:
                                fsignal = False
                                with open(share_dir + '/collected_signal.txt', 'w', encoding='utf-8') as make_file:
                                    json.dump(COLLECTDATA, make_file, indent="\t")
                                    log('[Complete] Collect 20 signals. See : /share/collected_signal.txt')
                                COLLECTDATA = None
                except Exception as err:
                    log('[ERROR] {}'.format(err))
                    writer.close()
                    await writer.wait_closed()
                    break

    async def send_to_socket():
        while True:
            reader, writer = await asyncio.open_connection(config['socket_IP'], config['socket_port'])
            while True:
                try:
                    if QUEUE:
                        send_data = QUEUE.pop(0)
                        if debug:
                            log('[DEBUG] socket:: Send a signal: {}'.format(send_data))
                        writer.write(bytes.fromhex(send_data['sendcmd']))
                        if send_data['count'] < 5:
                            send_data['count'] = send_data['count'] + 1
                            QUEUE.append(send_data)
                            await asyncio.sleep(0.5)
                        else:
                            if debug:
                                log('[ERROR] socket:: Send over 5 times. Send Failure. Delete a queue: {}'.format(send_data))
                except Exception as err:
                    log('[ERROR] {}'.format(err))
                    writer.close()
                    await writer.wait_closed()
                    break
                await asyncio.sleep(0.1)

    loop = asyncio.get_event_loop()
    cors = asyncio.wait([send_to_socket(), recv_from_socket()])
    loop.run_until_complete(cors)
    loop.close()


if __name__ == '__main__':
    with open(config_dir + '/options.json') as file:
        CONFIG = json.load(file)
    try:
        with open(share_dir + '/commax_found_device.json') as file:
            log('Found device data: /share/commax_found_device.json')
            OPTION = json.load(file)
    except IOError:
        OPTION = find_device(CONFIG)

    do_work(CONFIG, OPTION)
