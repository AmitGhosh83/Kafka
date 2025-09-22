from confluent_kafka.admin import AdminClient, NewTopic

BOOTSTRAP = "localhost:9092"
TOPIC = "payments"
PARTITIONS = 3          # ⬅️ increase for more parallelism
REPLICATION = 1         # single-broker dev → must be 1

admin = AdminClient({"bootstrap.servers": BOOTSTRAP})
print("Connecting to:", BOOTSTRAP)

# create topic (idempotent: prints a note if it already exists)
fs = admin.create_topics([NewTopic(TOPIC, num_partitions=PARTITIONS, replication_factor=REPLICATION)])
for t, f in fs.items():
    try:
        f.result()
        print(f"✅ Created topic '{t}' with {PARTITIONS} partitions")
    except Exception as e:
        print(f"ℹ️  Topic '{t}' not created (likely exists): {e}")

# show metadata so you can see broker + partitions
md = admin.list_topics(timeout=10)
print("\n📋 Brokers:")
for b in md.brokers.values():
    print(f"  id={b.id} host={b.host}:{b.port}")

tmd = md.topics.get(TOPIC)
if tmd:
    print(f"\n📦 Topic '{TOPIC}' partitions:")
    for p, meta in tmd.partitions.items():
        print(f"  p{p} leader={meta.leader} replicas={meta.replicas} isrs={meta.isrs}")
