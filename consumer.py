import json, signal
from confluent_kafka import Consumer, KafkaException

BOOTSTRAP = "localhost:9092"
TOPIC = "payments"
GROUP = "payments-readers"

running = True
def handle_sig(*_):
    global running
    running = False

signal.signal(signal.SIGINT, handle_sig)
signal.signal(signal.SIGTERM, handle_sig)

c = Consumer({
    "bootstrap.servers": BOOTSTRAP,
    "group.id": GROUP,
    "enable.auto.commit": False,         # at-least-once
    "auto.offset.reset": "earliest",     # start from beginning on first run
})

def on_assign(consumer, partitions):
    print(" Assigned:", [f"p{p.partition}" for p in partitions])
    consumer.assign(partitions)

def on_revoke(consumer, partitions):
    print("  Revoked:", [f"p{p.partition}" for p in partitions])

c.subscribe([TOPIC], on_assign=on_assign, on_revoke=on_revoke)

try:
    while running:
        msg = c.poll(1.0)
        if msg is None:
            continue
        if msg.error():
            raise KafkaException(msg.error())

        key = msg.key().decode() if msg.key() else None
        payload = json.loads(msg.value().decode())
        print(f" {TOPIC}[p{msg.partition()}] offset={msg.offset()} key={key} -> {payload}")
        c.commit(message=msg, asynchronous=False)
finally:
    print("Closing")
    c.close()
