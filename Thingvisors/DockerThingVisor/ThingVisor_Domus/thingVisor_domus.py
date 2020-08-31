# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

# Fed4IoT ThingVisor copying data from a oneM2M (Mobius) container

import sys
import traceback
import paho.mqtt.client as mqtt
import time
import os
import socket
import json
from datetime import datetime
from threading import Thread
from pymongo import MongoClient
from context import Context
from flask import Flask
from flask import request
sys.path.insert(0, 'PyLib/')

# Mqtt settings
tv_control_prefix = "TV"  # prefix name for controller communication topic
v_thing_prefix = "vThing"  # prefix name for virtual Thing data and control topics
data_out_suffix = "data_out"
control_in_suffix = "c_in"
control_out_suffix = "c_out"
v_silo_prefix = "vSilo"
v_thing_contexts = ["https://raw.githubusercontent.com/easy-global-market/ngsild-api-data-models/master/apic/jsonld-contexts/apic-compound.jsonld",
                    "https://fiware.github.io/data-models/context.jsonld",
                    "https://uri.etsi.org/ngsi-ld/v1/ngsi-ld-core-context.jsonld"]


app = Flask(__name__)
flask_port = 8089
routes = ['PulseOx','HeartRate','REMSleep','LightSleep','DeepSleep','AwakePeriods','MotionIntensity','Sensor']
users_emails = {
    0: "test0@email.com",
    1: "test1@email.com",
    2: "test2@email.com",
    3: "test3@email.com",
    4: "test4@email.com",
    5: "test5@email.com",
    6: "test6@email.com",
    7: "test7@email.com",
    8: "test8@email.com",
    9: "test9@email.com",
    10: "test10@email.com",
    11: "test11@email.com",
    12: "test12@email.com",
    13: "test13@email.com",
    14: "test14@email.com"
}

#used to sort by StartTimeInSeconds
def startTimeOrder(e):
  return e["startTimeInSeconds"]

#this method rebuilds all the sleeps measures into a dict
def compact_post_measures_sleeps(measures):
    output = [{'endTimeInSeconds': int(measure['value']['endTimeInSeconds']),
            'startTimeInSeconds': int(measure['value']['startTimeInSeconds'])} for measure in measures]
    output.sort(key=lambda measure: measure['startTimeInSeconds'])#ascending sort by startTimeInSeconds
    return output

#this method rebuilds all the heartrate/pulseox measures into a single list of dicts
def compact_post_measures_hr_po(measures):
    output = {key: value for measure in measures for key, value in measure['value'].items()}
    output = {tuple[0]: int(tuple[1]) for tuple in sorted(output.items())} #ascending sort by key (offset time)
    return output

def create_sensor_entity(sensor, v_thing_type):
    entity = {"@context": v_thing_contexts}
    entity['id'] = "urn:ngsi-ld:DomusSapiens:Sensor"+sensor['id']
    entity['type'] = v_thing_type
    entity['address'] = {"type" : "Property","value" : sensor['address']}
    entity['geoPosition'] = {"type" : "Property","value" : sensor['geoPosition']}
    entity['owner'] = {"type" : "Property","value" : sensor['owner']}
    return entity


def create_motion_intensity_entity(measure, v_thing_ID_LD, v_thing_type):
    entity = {"@context": v_thing_contexts, "id": "{}:{}".format(v_thing_ID_LD, measure['summary_id']),"type": v_thing_type}
    entity['userEmail'] = {"type": 'Property', 'value': users_emails[measure['user_id']]}
    entity['startTimeInSeconds'] = {"type": 'Property', 'value': int(measure['startTimeInSeconds'])}
    entity['durationInSeconds'] = {"type": 'Property', 'value': int(measure['durationInSeconds'])}
    entity['meanMotionIntensity'] = {'type': 'Property', 'value': float(measure['mean_motion_intensity'])}
    entity['maxMotionIntensity'] = {'type': 'Property', 'value': float(measure['max_motion_intensity'])}
    entity['intensity'] = {'type': 'Property', 'value': measure['intensity']}
    entity['distanceInMeters'] = {'type': 'Property', 'value': measure['distance_in_meters']}
    entity['steps'] = {'type': 'Property', 'value': int(measure['steps'])}
    entity['activityType'] = {'type': 'Property', 'value': measure['activity_type']}
    entity['measuredBySensor'] = {'type': 'Relationship', 'object': "urn:ngsi-ld:DomusSapiens:Sensor:1"}
    return entity

def create_entity_from_measures(garmin_measures, v_thing_ID_LD, v_thing_type, summary_id):
    entity = {"@context":v_thing_contexts, "id": "{}:{}".format(v_thing_ID_LD,summary_id),"type": v_thing_type}
    entity['userEmail'] = {"type": 'Property', 'value': users_emails[garmin_measures[0]['user_id']]}
    entity['startTimeInSeconds'] = {"type": 'Property', 'value': int(garmin_measures[0]['startTimeInSeconds'])}
    entity['durationInSeconds'] = {"type": 'Property', 'value': int(garmin_measures[0]['durationInSeconds'])}

    if v_thing_type in ['PulseOx', 'HeartRate']: #Heart and Pulse
        
        compact_measures = compact_post_measures_hr_po(garmin_measures) #compact json/list of jsons containing all the measures with the same summary_id
        map_prop_names = {'PulseOx' : {"prop_name": 'timeOffsetSleepSpo2'},
                            'HeartRate' : {"prop_name": 'timeOffsetHeartRateSamples'}}
        entity[map_prop_names[v_thing_type]['prop_name']] = {"type": 'Property', "observedAt": datetime.fromtimestamp(int(entity['startTimeInSeconds']['value'])).isoformat(), 'value': compact_measures }
            
    elif v_thing_type in ['REMSleep','LightSleep','DeepSleep','AwakePeriods']: #Sleeps times

            compact_measures = compact_post_measures_sleeps(garmin_measures) #compact json/list of jsons containing all the measures with the same summary_id
            map_prop_names = {'REMSleep' : {"map_name": 'remSleepMap', "prop_name": 'remSleepInSeconds'},
                                'LightSleep' : {"map_name": 'lightSleepMap', "prop_name": 'lightSleepInSeconds'},
                                'DeepSleep' : {"map_name": 'deepSleepMap', "prop_name": 'deepSleepInSeconds'},
                                'AwakePeriods' : {"map_name": 'awakeMap', "prop_name": 'awakeInSeconds'}}
 
            entity[ map_prop_names[v_thing_type]['prop_name'] ] = {'type': 'Property', 'value': garmin_measures[0][ map_prop_names[v_thing_type]['prop_name'] ]} #sum of each measure
            entity[ map_prop_names[v_thing_type]['map_name'] ] = {"type": 'Property', 'value': compact_measures }

    entity['measuredBySensor'] = {'type': 'Relationship', 'object': "DomusSapiens:Sensor:1"}
    return entity


#this method build all the entities dividing data by summaryID
def get_ngsi_ld_entity(v_thing_ID_LD, v_thing_type, data):
    ngsi_LD_entities = []

    if v_thing_type == 'MotionIntensity':
        data.sort(key=startTimeOrder)
        for measure in data:
            try:
                entity = create_motion_intensity_entity(measure, v_thing_ID_LD, v_thing_type)
                ngsi_LD_entities.append(entity)
            except ValueError as err:
                print(err)
        
    elif v_thing_type == "Sensor":
        for sensor in data:
            try:
                entity = create_sensor_entity(sensor, v_thing_type)
                ngsi_LD_entities.append(entity)
            except ValueError as err:
                print(err)

    else: #Not a MotionIntensity measure or a Sensor

        summary_IDs = list(set(map(lambda e: e['summary_id'], data))) #list of distinct summary_ids in this group of measures
        for summary_id in summary_IDs:
            try:
                garmin_measures = list(filter(lambda e: e['summary_id'] == summary_id, data)) #list of measures with the same summary_id
                entity = create_entity_from_measures(garmin_measures, v_thing_ID_LD, v_thing_type, summary_id)
                ngsi_LD_entities.append(entity)
            except ValueError as err:
                print(err)
    return ngsi_LD_entities



class httpRxThread(Thread):

    def __init__(self):
        Thread.__init__(self)

    def run(self):
        print("Thread Rx HTTP started")
        app.run(host='0.0.0.0', port=flask_port)
        print("Thread '" + self.name + " closed")

    @app.route('/<string:endpoint>', methods=['POST'])
    def recv_notify(endpoint):
        try:
            if endpoint not in routes:
                raise ValueError('Only accepted routes are ', routes)
            jres = request.get_json(force=True)

            #this allows us to have as many vThing as the endpoints
            identifier = thing_visor_ID + "/" + endpoint
            v_thing_topic = v_thing_prefix + "/" + identifier
            v_thing_ID = thing_visor_ID + "/" + endpoint # e.g. domus/DeepSleep
            v_thing_ID_LD = "urn:ngsi-ld:"+thing_visor_ID+":"+endpoint

            #it will return a list of entities
            ngsi_LD_entity_list = get_ngsi_ld_entity(v_thing_ID_LD, endpoint, jres)

            #if type(ngsi_LD_entity_list) != list:
            #    ngsi_LD_entity_list = [ngsi_LD_entity_list]  

            for entity in ngsi_LD_entity_list:
                context_vThing[identifier].update([entity])
                message = {"data": [entity], "meta": {"vThingID": v_thing_ID}}
                print("topic name: " + v_thing_topic + '/' + data_out_suffix + " ,message: " + json.dumps(message) +"\n\n")
                mqtt_data_client.publish(v_thing_topic + '/' + data_out_suffix, json.dumps(message))
            return 'OK', 201
        except ValueError as err:
            print('Requested URL /{} was not found in this server.'.format(endpoint), err)
            return 'Requested URL /{} was not found in this server', 404


class mqttDataThread(Thread):
    # mqtt client used for sending data
    def __init__(self):
        Thread.__init__(self)

    def run(self):
        print("Thread mqtt data started")
        global mqtt_data_client
        mqtt_data_client.connect(MQTT_data_broker_IP, MQTT_data_broker_port, 30)
        mqtt_data_client.loop_forever()
        print("Thread '" + self.name + "' terminated")


class mqttControlThread(Thread):

    def on_message_get_thing_context(self, jres):
        silo_id = jres["vSiloID"]
        print(v_thing_ID)
        msg = {"command": "getContextResponse", "data": context_vThing[v_thing_ID].get_all(), "meta": {"vThingID": v_thing_ID}}
        mqtt_control_client.publish(v_silo_prefix + "/" + silo_id + "/" + control_in_suffix, json.dumps(msg))

    def send_destroy_v_thing_message(self):
        msg = {"command": "deleteVThing", "vThingID": v_thing_ID, "vSiloID": "ALL"}
        mqtt_control_client.publish(v_thing_prefix + "/" + v_thing_ID + "/" + control_out_suffix, json.dumps(msg))
        return

    def send_destroy_thing_visor_ack_message(self):
        msg = {"command": "destroyTVAck", "thingVisorID": thing_visor_ID}
        mqtt_control_client.publish(tv_control_prefix + "/" + thing_visor_ID + "/" + control_out_suffix, json.dumps(msg))
        return

    def on_message_destroy_thing_visor(self, jres):
        global db_client
        db_client.close()
        self.send_destroy_v_thing_message()
        self.send_destroy_thing_visor_ack_message()
        print("Shutdown completed")

    # handler for mqtt control topics
    def __init__(self):
        Thread.__init__(self)

    def on_message_in_control_vThing(self, mosq, obj, msg):
        payload = msg.payload.decode("utf-8", "ignore")
        print(msg.topic + " " + str(payload))
        jres = json.loads(payload.replace("\'", "\""))
        try:
            command_type = jres["command"]
            if command_type == "getContextRequest":
                self.on_message_get_thing_context(jres)
        except Exception as ex:
            traceback.print_exc()
        return


    def on_message_in_control_TV(self, mosq, obj, msg):
        payload = msg.payload.decode("utf-8", "ignore")
        print(msg.topic + " " + str(payload))
        jres = json.loads(payload.replace("\'", "\""))
        try:
            command_type = jres["command"]
            if command_type == "destroyTV":
                self.on_message_destroy_thing_visor(jres)
        except Exception as ex:
            traceback.print_exc()
        return 'invalid command'

    def run(self):
        print("Thread mqtt control started")
        global mqtt_control_client
        mqtt_control_client.connect(MQTT_control_broker_IP, MQTT_control_broker_port, 30)
        
        # Publish on the thingVisor out_control topic, the createVThing command and other parameters for each vThing
        for v_thing in v_things:
            v_thing_topic = v_thing["topic"]
            v_thing_message = {"command": "createVThing",
                               "thingVisorID": thing_visor_ID,
                               "vThing": v_thing["vThing"]}
            mqtt_control_client.publish(tv_control_prefix + "/" + thing_visor_ID + "/" + control_out_suffix,
                                        json.dumps(v_thing_message))

            # Add message callbacks that will only trigger on a specific subscription match
            mqtt_control_client.message_callback_add(v_thing_topic + "/" + control_in_suffix,
                                                     self.on_message_in_control_vThing)
            mqtt_control_client.message_callback_add(tv_control_prefix + "/" + thing_visor_ID + "/" + control_in_suffix,
                                                     self.on_message_in_control_TV)
            mqtt_control_client.subscribe(v_thing_topic + '/' + control_in_suffix)
            mqtt_control_client.subscribe(tv_control_prefix + "/" + thing_visor_ID + "/" + control_in_suffix)
            time.sleep(0.1)
        
        mqtt_control_client.loop_forever()
        print("Thread '" + self.name + "' terminated")


# main
if __name__ == '__main__':
    resources_ip = "127.0.0.1"

    thing_visor_ID = os.environ["thingVisorID"] #domus
    parameters = os.environ["params"]
    if parameters:
        try:
            params = json.loads(parameters.replace("'", '"'))
        except json.decoder.JSONDecodeError:
            # TODO manage exception
            print("error on params (JSON) decoding")
            os._exit(1)
        except KeyError:
            print(Exception.with_traceback())
            os._exit(1)
        except Exception as err:
            print("ERROR on params (JSON)", err)

    if 'vThingName' in params.keys():
        v_thing_name = params['vThingName']
    else:
        v_thing_name = "vThingDomus"
    if 'vThingType' in params.keys():
        v_thing_type_attr = params['vThingType']
    else:
        v_thing_type_attr = "message"
    #v_thing_label = v_thing_name
    #v_thing_description = "Pass Through vThing"
    
    v_thing_ID = thing_visor_ID + "/" + v_thing_name

    MQTT_data_broker_IP = os.environ["MQTTDataBrokerIP"]
    MQTT_data_broker_port = int(os.environ["MQTTDataBrokerPort"])
    MQTT_control_broker_IP = os.environ["MQTTControlBrokerIP"]
    MQTT_control_broker_port = int(os.environ["MQTTControlBrokerPort"])


    #creating all the vthings
    v_things = []
    context_vThing = {}
    for sensor in routes:
        thing = 'garmin_sensor'
        label = 'garmin_sensor which measures ' + str(sensor)
        identifier = thing_visor_ID + '/' + str(sensor)

        topic = v_thing_prefix + "/" + identifier
        v_things.append({"vThing": {"label": label, "id": identifier, "description": str(sensor) + " Garmin measures about an user"},
                             "topic": topic, "type": sensor,
                             "dataType": sensor, "thing": thing})
        context_vThing[identifier] = Context()

    # mapping of virtual thing with its context object. Useful in case of multiple virtual things
    contexts = {v_thing_ID: context_vThing}

    # Mongodb settings
    time.sleep(1.5)  # wait before query the system database
    db_name = "viriotDB"  # name of system database
    thing_visor_collection = "thingVisorC"
    db_IP = os.environ['systemDatabaseIP']  # IP address of system database
    db_port = os.environ['systemDatabasePort']  # port of system database
    db_client = MongoClient('mongodb://' + db_IP + ':' + str(db_port) + '/')
    db = db_client[db_name]
    port_mapping = db[thing_visor_collection].find_one({"thingVisorID": thing_visor_ID}, {"port": 1, "_id": 0})
    poa_IP_dict = db[thing_visor_collection].find_one({"thingVisorID": thing_visor_ID}, {"IP": 1, "_id": 0})
    poa_IP = str(poa_IP_dict['IP'])
    print("poa_IP->", poa_IP)
    poa_port = port_mapping['port'][str(flask_port)+'/tcp']
    if not poa_IP:
        poa_IP = socket.gethostbyname(socket.gethostname())
    if not poa_port:
        poa_port = flask_port

    mqtt_control_client = mqtt.Client()
    mqtt_data_client = mqtt.Client()

    rxThread = httpRxThread()  # http server used to receive JSON messages from external producer
    rxThread.start()

    mqtt_control_thread = mqttControlThread()       # mqtt VirIoT control thread
    mqtt_control_thread.start()

    mqtt_data_thread = mqttDataThread()       # mqtt VirIoT data thread
    mqtt_data_thread.start()

    time.sleep(2)
    while True:
        try:
            time.sleep(3)
        except:
            print("KeyboardInterrupt")
            time.sleep(1)
            os._exit(1)
