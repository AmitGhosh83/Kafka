# Kafka on Windows (Docker Desktop) — Hands‑On Playbook

**Goal:** Stand up Kafka locally on Windows using Docker Desktop (KRaft mode), validate it end‑to‑end with CLI and Python, and capture the exact troubleshooting we used so you can repeat this on any machine.

---

## What you’ll accomplish

- Run a **single-broker** Kafka on your Windows host at **`localhost:9092`** (plus an internal listener for containers).
- Create a **topic** with **partitions** and understand leaders/replication.
- Produce and consume messages with a **consumer group** and watch **rebalancing**.
- Keep a checklist of **fixes** for common Windows/Docker pitfalls.

> This is a single-node dev setup (replication factor = 1). For HA you’d add brokers; that’s out of scope here.

---

## Prerequisites

- **Windows 10/11** with **Docker Desktop** installed and **WSL 2 backend** enabled.
- Docker Desktop must be in **Linux containers** mode.
- Optional: a terminal with PowerShell 7+.

Check quickly:
```powershell
# Docker Desktop service
Get-Service com.docker.service

# WSL status
wsl --status
```

---

## Quickstart (TL;DR)

1. Create `docker-compose.yml` with the contents below.
2. Start broker:
   ```powershell
   docker compose up -d
   docker ps
   docker logs kafka --tail=100
   ```
3. Test from a container on the same network:
   ```powershell
   docker run -it --rm --network "kafka_default" edenhill/kcat:1.7.1 -b kafka:29092 -L
   echo "hello" | docker run -i --rm --network "kafka_default" edenhill/kcat:1.7.1 -b kafka:29092 -t demo -P
   docker run -it --rm --network "kafka_default" edenhill/kcat:1.7.1 -b kafka:29092 -t demo -C -o beginning -e
   ```
4. (Optional) Test inside the broker container with Kafka CLI tools (see **Validate with Kafka CLI** below).
5. Run the **Python** examples (see **Python environment + examples**).

---

## `docker-compose.yml` (single-broker, dual listeners)

> Put this file in your project folder (e.g., `C:\Users\<you>\source\Docker\Kafka\docker-compose.yml`).

```yaml
services:
  kafka:
    image: bitnami/kafka:3.7
    container_name: kafka
    restart: unless-stopped

    # Expose host listener (apps on Windows use localhost:9092)
    ports:
      - "9092:9092"

    environment:
      # KRaft (no ZooKeeper)
      KAFKA_ENABLE_KRAFT: "yes"
      KAFKA_CFG_PROCESS_ROLES: "broker,controller"
      KAFKA_CFG_NODE_ID: "1"
      KAFKA_CFG_CONTROLLER_QUORUM_VOTERS: "1@kafka:9093"
      KAFKA_CFG_CONTROLLER_LISTENER_NAMES: "CONTROLLER"

      # IMPORTANT when using custom listener names
      KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP: "PLAINTEXT:PLAINTEXT,PLAINTEXT_INTERNAL:PLAINTEXT,CONTROLLER:PLAINTEXT"

      # Dual listeners: external for host, internal for containers
      KAFKA_CFG_LISTENERS: "PLAINTEXT://:9092,PLAINTEXT_INTERNAL://:29092,CONTROLLER://:9093"
      KAFKA_CFG_ADVERTISED_LISTENERS: "PLAINTEXT://localhost:9092,PLAINTEXT_INTERNAL://kafka:29092"
      KAFKA_CFG_INTER_BROKER_LISTENER_NAME: "PLAINTEXT_INTERNAL"

      # Valid 22-char KRaft cluster id
      KAFKA_KRAFT_CLUSTER_ID: "MkU3OEVBNTcwNTJENDM2Qg"

      # QoL for single-node dev
      KAFKA_CFG_AUTO_CREATE_TOPICS_ENABLE: "true"
      KAFKA_CFG_OFFSETS_TOPIC_REPLICATION_FACTOR: "1"
      KAFKA_CFG_TRANSACTION_STATE_LOG_REPLICATION_FACTOR: "1"
      KAFKA_CFG_TRANSACTION_STATE_LOG_MIN_ISR: "1"
```

Start it:
```powershell
docker compose up -d
docker ps
docker logs kafka --tail=100
```

> If Compose warns that `version:` is obsolete, just remove the `version` key from the file (it’s not needed).

---

## Validate with Kafka CLI (inside the container)

Open a shell in the container:
```powershell
docker exec -it kafka bash
```

Create a topic and test:
```bash
kafka-topics.sh --bootstrap-server localhost:9092 --list

# produce
kafka-console-producer.sh --bootstrap-server localhost:9092 --topic demo
>hello
>world

# consume
kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic demo --from-beginning
```

---

## kcat tests from another container (Windows-safe)

Docker Desktop on Windows **does not support `--network=host`**. Use the Compose network and the **internal listener**:

```powershell
# List compose networks and find something like kafka_default
docker network ls

# Metadata
docker run -it --rm --network "kafka_default" edenhill/kcat:1.7.1 -b kafka:29092 -L

# Produce
echo "hello world" | docker run -i --rm --network "kafka_default" edenhill/kcat:1.7.1 -b kafka:29092 -t demo -P

# Consume
docker run -it --rm --network "kafka_default" edenhill/kcat:1.7.1 -b kafka:29092 -t demo -C -o beginning -e
```

---

## Python environment + examples

> These run on **Windows host** using `localhost:9092`. Use a **virtual environment**.

Create/activate venv (PowerShell safe option):
```powershell
python -m venv .venv

# If execution policy blocks activation:
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass

# Activate
. .\.venv\Scripts\Activate.ps1

# Install client
pip install --upgrade pip
pip install confluent-kafka
```

### `create_topic.py` (Admin API, verbose)

```python
# create_topic.py
import sys
from confluent_kafka.admin import AdminClient, NewTopic

BOOTSTRAP = "localhost:9092"
TOPIC = "payments"
PARTITIONS = 3         # scale parallelism here
REPL = 1               # single-broker dev

print(f"[INFO] Using bootstrap: {BOOTSTRAP}")
print(f"[INFO] Ensuring topic '{TOPIC}' with {PARTITIONS} partitions...")

try:
    admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
    md = admin.list_topics(timeout=5)
    print("[INFO] Connected to cluster.")
    print("[INFO] Brokers:")
    for b in md.brokers.values():
        print(f"  - id={b.id} host={b.host}:{b.port}")
except Exception as e:
    print("[ERROR] Could not connect to Kafka:", repr(e))
    sys.exit(1)

try:
    fs = admin.create_topics([NewTopic(TOPIC, num_partitions=PARTITIONS, replication_factor=REPL)])
    f = fs[TOPIC]
    try:
        f.result()
        print(f"[OK] Created topic '{TOPIC}'")
    except Exception as e:
        print(f"[INFO] Topic create skipped (likely exists): {e}")
except Exception as e:
    print("[ERROR] create_topics call failed:", repr(e))

try:
    tmd = admin.list_topics(timeout=5).topics.get(TOPIC)
    if not tmd:
        print(f"[ERROR] Topic '{TOPIC}' not found after create.")
        sys.exit(2)
    print(f"[INFO] Topic '{TOPIC}' has {len(tmd.partitions)} partitions:")
    for pnum, pmeta in sorted(tmd.partitions.items()):
        print(f"  - p{pnum} leader={pmeta.leader} replicas={list(pmeta.replicas)} isrs={list(pmeta.isrs)}")
    print("[DONE]")
except Exception as e:
    print("[ERROR] Could not describe topic:", repr(e))
    sys.exit(3)
```

Run:
```powershell
python .\create_topic.py
```

### `producer.py` (keyed messages → per‑key ordering)

```python
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
        print(f"❌ Delivery failed: {err}")
    else:
        key = msg.key().decode() if msg.key() else None
        print(f"✅ {TOPIC}[p{msg.partition()}] offset={msg.offset()} key={key}")

users = [f"u-{i:03d}" for i in range(6)]
for i in range(30):
    user = random.choice(users)
    event = {"event_id": i, "user_id": user, "amount": round(random.uniform(5, 50), 2)}
    producer.produce(TOPIC, key=user.encode(), value=json.dumps(event).encode(), on_delivery=delivery_report)
    producer.poll(0)
    time.sleep(0.05)

producer.flush()
print("Done.")
```

### `consumer.py` (single group, observe rebalancing)

```python
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
    "auto.offset.reset": "earliest",
})

def on_assign(consumer, partitions):
    print("🎯 Assigned:", [f"p{p.partition}" for p in partitions])
    consumer.assign(partitions)

def on_revoke(consumer, partitions):
    print("↩️  Revoked:", [f"p{p.partition}" for p in partitions])

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
        print(f"📥 {TOPIC}[p{msg.partition()}] offset={msg.offset()} key={key} -> {payload}")
        c.commit(message=msg, asynchronous=False)
finally:
    print("Closing…")
    c.close()
```

Run:
```powershell
# Produce
python .\producer.py

# Open two terminals and run the same consumer twice (same GROUP)
python .\consumer.py
python .\consumer.py
```

Inspect group/partitions:
```powershell
docker exec -it kafka bash -lc "kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group payments-readers"
docker exec -it kafka bash -lc "kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic payments"
```

---

## Scaling knobs (preview)

- **Partitions = parallelism** (max active consumers per group). Increase:
  ```powershell
  docker exec -it kafka bash -lc "kafka-topics.sh --bootstrap-server localhost:9092 --alter --topic payments --partitions 6"
  ```
- **More consumers** = start more `consumer.py` processes with the same `GROUP`.
- **Producer** throughput/durability: tune `linger.ms`, `batch.size`, `compression.type`, keep `enable.idempotence=True` and `acks=all`.
- **Consumer** semantics: manual commit (**at-least-once**) vs `enable.auto.commit=True` (**at-most-once** trade-offs).

---

## Troubleshooting (what we actually fixed)

### 1) Docker client can’t reach Desktop Linux engine
**Symptom:**  
`open //./pipe/dockerDesktopLinuxEngine: The system cannot find the file specified.`

**Fix:**  
- Launch **Docker Desktop** and ensure **Linux containers** mode.  
- Start service: `Start-Service com.docker.service` (PowerShell as Admin).  
- Verify context: `docker context use desktop-linux`.  
- Ensure **WSL 2** is installed and integration enabled in Docker Desktop.

### 2) `--network=host` doesn’t work on Windows
**Symptom:**  
`kcat ... -b localhost:9092 ...` from a container fails; connect refused.

**Fix:**  
- Use Compose network + internal listener: `kafka:29092`.  
- Add **dual listeners** in Compose (`PLAINTEXT` for host, `PLAINTEXT_INTERNAL` for containers).

### 3) Container name vs. Compose naming
**Symptom:**  
`docker logs kafka` → “No such container” because Compose created `kafka-kafka-1`.

**Fix:**  
- Set `container_name: kafka` in Compose for stable commands.

### 4) Broker exits immediately (Exit 1)
**Causes & Fixes:**  
- Missing `KAFKA_CFG_LISTENER_SECURITY_PROTOCOL_MAP` when using custom listener names → **add it**.  
- Invalid/empty `KAFKA_KRAFT_CLUSTER_ID` → set a valid 22‑char id like `MkU3OEVBNTcwNTJENDM2Qg`.  
- After config changes, start clean: `docker compose down -v` then `docker compose up -d`.

### 5) PowerShell execution policy blocks venv activation
**Symptom:**  
`Activate.ps1 cannot be loaded because running scripts is disabled...`

**Fix:**  
- Temporary per-session: `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass` then activate.  
- Or use the venv interpreter directly: `.\.venv\Scripts\python.exe ...`

### 6) “Non‑UTF‑8 code starting with '\x90'” when running Python
**Symptom:**  
`python .\.venv\Scripts\python.exe create_topic.py`

**Fix:**  
- Don’t pass the **EXE** to Python. Either:  
  - `.\.venv\Scripts\python.exe create_topic.py` **or**  
  - Activate venv and run `python create_topic.py`.

### 7) Consumers both show same partitions
**Causes:**  
- Topic has fewer partitions than expected.  
- Consumers are in **different groups**.  
- Rebalance not observed yet.

**Fix:**  
- Describe topic; increase partitions if needed.  
- Ensure both use `GROUP = "payments-readers"`.  
- Start/stop one consumer to trigger rebalance; `kafka-consumer-groups.sh --describe` to verify assignments.

---

## Useful commands (cheat sheet)

```powershell
# Start/stop
docker compose up -d
docker compose down
docker compose down -v   # also remove volumes (fresh state)

# Inspect
docker ps
docker logs kafka --tail=200
docker network ls
docker network inspect kafka_default

# Topics & groups (inside container)
docker exec -it kafka bash -lc "kafka-topics.sh --bootstrap-server localhost:9092 --list"
docker exec -it kafka bash -lc "kafka-topics.sh --bootstrap-server localhost:9092 --describe --topic payments"
docker exec -it kafka bash -lc "kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group payments-readers"
docker exec -it kafka bash -lc "kafka-consumer-groups.sh --bootstrap-server localhost:9092 --reset-offsets --group payments-readers --topic payments --to-earliest --execute"
```

---

## What you just accomplished

- Brought up a **Kafka broker** on Windows using Docker (KRaft, no ZooKeeper).  
- Exposed **two listeners**: `localhost:9092` for host apps and `kafka:29092` for containers.  
- Created a **topic** with **3 partitions**; saw **leader** and ISR info.  
- Produced **keyed messages** and consumed them with a **consumer group**, observing **partition assignment** and **rebalance**.

You now have the foundation to explore **observability** (metrics/lag/offsets) and **scaling knobs** (partitions, multiple consumers, batching/acks/idempotence). Keep this playbook in your repo for repeatable setup.
