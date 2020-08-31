# ThingVisor Domus

This ThingVisor creates a vThing whose data are medical measures from the Garmin International.

The data can be sent by POST HTTP Requests in one of these eight endpoints:
- /DeepSleep
- /LightSleep
- /REMSleep
- /AwakePeriods
- /MotionIntensity
- /HeartRate
- /PulseOx
- /Sensor

## How To Run

### Build locally with Docker (optional)

Docker can be used to build locally the image of the ThingVisor and then use it to deploy it.

```bash
docker build -t fed4iot/domus-tv VirIoT/Thingvisors/DockerThingVisor/ThingVisor_Domus/
```

### Local Docker deployment

Use the VirIoT CLI and run the following command to run the ThingVisor. The name of the ThingVisor (domusTV), the vThingName (timestamp) and the vThingType (timestamp) can be customized.

```bash
python3 f4i.py add-thingvisor -i fed4iot/domus-tv -n domusTV -d "domus thingvisor" -p "{'vThingName':'timestamp','vThingType':'timestamp'}"
```

### Kubernetes deployment

Use the VirIoT CLI and run the following command to run the ThingVisor example.  The name of the ThingVisor (domusTV), the vThingName (timestamp) and the vThingType (timestamp) can be customized.

```bash
python3 f4i.py add-thingvisor -c http://[k8s_node_ip]:[NodePort] -y "../yaml/thingVisor-domus.yaml" -n domusTV -d "domus thingvisor" -p "{'vThingName':'timestamp','vThingType':'timestamp'}"
```

### Data injection
Linux http (or similar apps such as curl and Postman) can be used to inject data using the samples provided.

```bash
http POST <thingVisorIP>:<thingVisorPort>/DeepSleep < samples/deep_sleep.json
http POST <thingVisorIP>:<thingVisorPort>/HeartRate < samples/heart_rate.json
http POST <thingVisorIP>:<thingVisorPort>/LightSleep < samples/light_sleep.json
http POST <thingVisorIP>:<thingVisorPort>/MotionIntensity < samples/motion_intensity.json
http POST <thingVisorIP>:<thingVisorPort>/Sensor < samples/sensor.json
```

## NGSI-LD data model
 
The NGSI-LD entity published by the vThings can have different properties and at least one "Relationship". This is an example of the expected output:

```json
{
    "id": "urn:ngsi-ld:<ThingVisorName>:<vThingType>:<summaryID>",
    "type": "<vThingType>",
    "propertyName": {
        "type": "Property",
        "value": <received JSON object>
    },
    .
    .
    .
    .
    "relationshipName": {
        "type": "Relationship",
        "object": <entity-id>
    },
    .
    .
    .
    .
}
```
