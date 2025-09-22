import json, random, time
from confluent_kafka import Producer

BOOTSTRAP = "localhost:9092"
TOPIC = "payments"

producer = Producer({
    "bootstrap.servers": BOOTSTRAP,
    "enable.idempotence": True,
    "acks": "all",
    "linger.ms": 5,
    "compression.type": "snappy"
})

def delivery_report(err, msg):
    if err:
        print(f" Delivery failed: {err}")
    else:
        key = msg.key().decode() if msg.key() else None
        print(f" {TOPIC}[p{msg.partition()}] offset={msg.offset()} key={key}")

users = [f"u-{i:03d}" for i in range(6)]
for i in range(30):
    user = random.choice(users)
    event = {"event_id": i, "user_id": user, "amount": round(random.uniform(5, 50), 2)}
    producer.produce(TOPIC, key=user.encode(), value=json.dumps(event).encode(), on_delivery=delivery_report)
    producer.poll(0)
    time.sleep(0.05)

producer.flush()
print("Done.")
