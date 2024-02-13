
import json
import time
import random

import paho.mqtt.client as mqtt

broker = '192.168.5.18'
port = 1883
topic = "enocean-dev/pilote_lab/req"
client_id = f'python-mqtt-{random.randint(0, 1000)}'



def connect_mqtt():
    def on_connect(client, userdata, flags, rc):
        if rc == 0:
            print("Connected to MQTT Broker!")
        else:
            print("Failed to connect, return code %d\n", rc)
    # Set Connecting Client ID
    client = mqtt.Client(client_id)
    # client.username_pw_set(username, password)
    client.on_connect = on_connect
    client.connect(broker, port)
    return client

def publish_json(client):
    msg_count = 1

    result = client.publish(f"{topic}", json.dumps(dict(CMD=8, PM=1)))
    time.sleep(0.1)
    # result: [0, 1]
    status = result[0]
    if status == 0:
        print(f"Send `message")
    else:
        print(f"Failed to send message to topic {topic}")

def publish(client):
    msg_count = 1

    result = client.publish(f"{topic}/CMD", "8")
    time.sleep(0.1)
    result = client.publish(f"{topic}/PM", "1")
    time.sleep(0.1)
    result = client.publish(f"{topic}/send", "clear")
    time.sleep(0.1)
    # result: [0, 1]
    status = result[0]
    if status == 0:
        print(f"Send `message")
    else:
        print(f"Failed to send message to topic {topic}")


if __name__ == "__main__":
    c = connect_mqtt()

    publish_json(c)