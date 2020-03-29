import paho.mqtt.client as mqtt
import json
import time
import asyncio

share_dir = '/share'
config_dir = '/data'
data_dir = '/pycommax'

HA_TOPIC = 'homenet'
STATE_TOPIC = HA_TOPIC + '/{}/{}/state'
ELFIN_TOPIC = 'ew11'
ELFIN_SEND_TOPIC = ELFIN_TOPIC + '/send'


def log(string):
    date = time.strftime('%Y-%m-%d %p %I:%M:%S', time.localtime(time.time()+9*60*60))
    print('[{}] {}'.format(date, string))
    return


def find_device(config):
    collect_data = []
    target_time = time.time() + 20

    def on_connect(client, userdata, flags, rc):
        userdata = time.time() + 20
        if rc == 0:
            log("MQTT connection successful!!")
            log("Find devices for 20s..")
            client.subscribe('ew11/#', 0)
        else:
            errcode = {1: 'Connection refused - incorrect protocol version',
                       2: 'Connection refused - invalid client identifier',
                       3: 'Connection refused - server unavailable',
                       4: 'Connection refused - bad username or password',
                       5: 'Connection refused - not authorised'}
            log(errcode[rc])

    def on_message(client, userdata, msg):
        data = msg.payload.hex().upper()
        if len(data) == 32:
            collect_data.append(data)

    mqtt_client = mqtt.Client('commax-mqtt2elfin-python')
    mqtt_client.username_pw_set(config['mqtt_id'], config['mqtt_password'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect_async(config['mqtt_server'])
    mqtt_client.user_data_set(target_time)
    mqtt_client.loop_start()

    while time.time() < target_time:
        pass

    mqtt_client.loop_stop()

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
    mqtt_log = config['mqtt_log']
    find_signal = config['save_unregistered_signal']
    debug = config['DEBUG']
    elfin_log = config['elfin_log']

    def pad(value):
        value = int(value)
        return '0' + str(value) if value < 10 else str(value)

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
    log('----------------------')
    log('Registered device lists..')
    log('DEVICE_LISTS: {}'.format(DEVICE_LISTS))
    log('----------------------')

    HOMESTATE = {}
    QUEUE = []
    COLLECTDATA = {'cond': find_signal, 'data': [], 'EVtime': time.time(), 'LastRecv': time.time_ns()}

    async def recv_from_HA(topics, value):
        key = topics[1] + topics[2]
        device = topics[1][:-1]
        idx = int(topics[1][-1])
        if mqtt_log:
            log('[LOG] HA >> MQTT : {} -> {}'.format('/'.join(topics), value))
        try:
            if device in DEVICE_LISTS:
                if HOMESTATE.get(key) and value != HOMESTATE.get(key):
                    if device == 'Thermo':
                        curTemp = HOMESTATE.get(topics[1] + 'curTemp')
                        setTemp = HOMESTATE.get(topics[1] + 'setTemp')
                        if value == 'off':
                            value = 'OFF'
                        elif value == 'heat':
                            value = 'ON'
                        if topics[2] == 'power':
                            sendcmd = make_hex_temp(idx - 1, curTemp, setTemp, value)
                            recvcmd = [make_hex_temp(idx - 1, curTemp, setTemp, 'state' + value)]
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
                                sendcmd = make_hex_temp(idx - 1, curTemp, setTemp, 'CHANGE')
                                recvcmd = [make_hex_temp(idx - 1, curTemp, setTemp, 'stateON')]
                                if sendcmd:
                                    QUEUE.append({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'count': 0})
                                    if debug:
                                        log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}'.format(sendcmd, recvcmd))
                    elif device == 'Fan':
                        if value == 'off':
                            value = 'OFF'
                        if topics[2] == 'power':
                            sendcmd = DEVICE_LISTS[device][idx].get('command' + value)
                            recvcmd = DEVICE_LISTS[device][idx].get('state' + value) if value == 'ON' else [
                                DEVICE_LISTS[device][idx].get('state' + value)]
                            QUEUE.append({'sendcmd': sendcmd, 'recvcmd': recvcmd, 'count': 0})
                            if debug:
                                log('[DEBUG] Queued ::: sendcmd: {}, recvcmd: {}'.format(sendcmd, recvcmd))
                        elif topics[2] == 'speed':
                            speed_list = ['low', 'medium', 'high']
                            if value in speed_list:
                                index = speed_list.index(value)
                                sendcmd = DEVICE_LISTS[device][idx]['CHANGE'][index]
                                recvcmd = [DEVICE_LISTS[device][idx]['stateON'][index]]
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
                    log('[DEBUG] There is no commands for {}'.format('/'.join(topics)))
        except Exception as err:
            log('[ERROR] mqtt_on_message(): {}'.format(err))

    async def recv_from_elfin(data):
        COLLECTDATA['LastRecv'] = time.time_ns()
        if data:
            if HOMESTATE.get('EV1power') == 'ON':
                if COLLECTDATA['EVtime'] < time.time():
                    await update_state('EV', 0, 'OFF')
            OutBreak = False
            for que in QUEUE:
                for recvcmd in que['recvcmd']:
                    if recvcmd in data:
                        QUEUE.remove(que)
                        if debug:
                            log('[DEBUG] Found matched hex: {}. Delete a queue: {}'.format(data, que))
                        OutBreak = True
                        break
                if OutBreak:
                    break

            if elfin_log:
                log('[SIGNAL] receved: {}'.format(data))
            data_prefix = data[:2]
            if data_prefix in prefix_list:
                device_name = prefix_list[data_prefix]
                if len(data) == 32:
                    data = data[16:]
                    if device_name == 'Thermo' and data.startswith(device_list['Thermo']['stateOFF'][:2]):
                        curTnum = device_list['Thermo']['curTemp']
                        setTnum = device_list['Thermo']['setTemp']
                        curT = data[curTnum - 1:curTnum + 1]
                        setT = data[setTnum - 1:setTnum + 1]
                        onoffNUM = device_list['Thermo']['stateONOFFNUM']
                        staNUM = device_list['Thermo']['stateNUM']
                        index = int(data[staNUM - 1]) - 1
                        onoff = 'ON' if int(data[onoffNUM - 1]) > 0 else 'OFF'

                        await update_state(device_name, index, onoff)
                        await update_temperature(index, curT, setT)
                    elif device_name == 'Fan':
                        if data in DEVICE_LISTS['Fan'][1]['stateON']:
                            await update_state('Fan', 0, 'ON')
                            speed = DEVICE_LISTS['Fan'][1]['stateON'].index(data)
                            await update_fan('Fan', 0, speed)
                    else:
                        num = DEVICE_LISTS[device_name]['Num']
                        state = [DEVICE_LISTS[device_name][k+1]['stateOFF'] for k in range(num)] + [DEVICE_LISTS[device_name][k+1]['stateON'] for k in range(num)]
                        if data in state:
                            index = state.index(data)
                            onoff, index = ['OFF', index] if index < num else ['ON', index - num]
                            await update_state(device_name, index, onoff)
                else:
                    if device_name == 'EV':
                        await update_state('EV', 0, 'ON')
                        COLLECTDATA['EVtime'] = time.time() + 3
            else:
                if COLLECTDATA['cond']:
                    if len(COLLECTDATA['data']) < 20:
                        if data not in COLLECTDATA['data']:
                            log('[FOUND] signal: {}'.format(data))
                            COLLECTDATA['data'].append(data)
                            COLLECTDATA['data'] = list(set(COLLECTDATA['data']))
                    else:
                        COLLECTDATA['cond'] = False
                        with open(share_dir + '/collected_signal.txt', 'w', encoding='utf-8') as make_file:
                            json.dump(COLLECTDATA['data'], make_file, indent="\t")
                            log('[Complete] Collect 20 signals. See : /share/collected_signal.txt')
                        COLLECTDATA['data'] = None

    async def update_state(device, idx, onoff):
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

    async def update_fan(device, idx, onoff):
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

    async def update_temperature(idx, curTemp, setTemp):
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

    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            log("MQTT connection successful!!")
            client.subscribe([(HA_TOPIC + '/#', 0), (ELFIN_TOPIC + '/recv', 0), (ELFIN_TOPIC + '/send', 1)])
        else:
            errcode = {1: 'Connection refused - incorrect protocol version',
                       2: 'Connection refused - invalid client identifier',
                       3: 'Connection refused - server unavailable',
                       4: 'Connection refused - bad username or password',
                       5: 'Connection refused - not authorised'}
            log(errcode[rc])

    def on_message(client, userdata, msg):
        topics = msg.topic.split('/')
        try:
            if topics[0] == HA_TOPIC and topics[-1] == 'command':
                asyncio.run(recv_from_HA(topics, msg.payload.decode('utf-8')))
            elif topics[0] == ELFIN_TOPIC and topics[-1] == 'recv':
                asyncio.run(recv_from_elfin(msg.payload.hex().upper()))
        except:
            pass

    mqtt_client = mqtt.Client('commax-mqtt2elfin-python')
    mqtt_client.username_pw_set(config['mqtt_id'], config['mqtt_password'])
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect_async(config['mqtt_server'])
    mqtt_client.loop_start()

    async def send_to_elfin():
        while True:
            try:
                if QUEUE and time.time_ns() - COLLECTDATA['LastRecv'] > 100000000:
                    send_data = QUEUE.pop(0)
                    if elfin_log:
                        log('[SIGNAL] Send a signal: {}'.format(send_data))
                    mqtt_client.publish(ELFIN_SEND_TOPIC, bytes.fromhex(send_data['sendcmd']))
                    await asyncio.sleep(0.1)
                    if send_data['count'] < 5:
                        send_data['count'] = send_data['count'] + 1
                        QUEUE.append(send_data)
                    else:
                        if elfin_log:
                            log('[SIGNAL] Send over 5 times. Send Failure. Delete a queue: {}'.format(send_data))
            except Exception as err:
                log('[ERROR] send_to_elfin(): {}'.format(err))
                return True
            await asyncio.sleep(0.1)
        # return

    loop = asyncio.get_event_loop()
    loop.run_until_complete(send_to_elfin())
    loop.close()
    mqtt_client.loop_stop()

if __name__ == '__main__':
    with open(config_dir + '/options.json') as file:
        CONFIG = json.load(file)
    try:
        with open(share_dir + '/commax_found_device.json') as file:
            log('Found device data: /share/commax_found_device.json')
            OPTION = json.load(file)
    except IOError:
        OPTION = find_device(CONFIG)
    while True:
        do_work(CONFIG, OPTION)
