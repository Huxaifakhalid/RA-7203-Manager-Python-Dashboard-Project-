from snmp_client import client

oids = [
    ("Description", "1.3.6.1.2.1.1.1.0"),
    ("Location", "1.3.6.1.2.1.1.6.0"),
    ("Frequency", "1.3.6.1.4.1.22154.3.1.2.3.4.0"),
    ("RSSI", "1.3.6.1.4.1.22154.3.1.2.5.2.5.4.0"),
    ("CarrierNoise", "1.3.6.1.4.1.22154.3.1.2.5.2.5.10.0"),
    ("Offset", "1.3.6.1.4.1.22154.3.1.2.5.2.5.9.0"),
    ("Alarm", "1.3.6.1.4.1.22154.3.1.2.5.2.7.0"),
    ("OpState", "1.3.6.1.4.1.22154.3.1.2.3.2.0"),
    ("OpMode", "1.3.6.1.4.1.22154.3.1.2.3.1.0"),
]

for name, oid in oids:

    value, error = client.read(oid)

    print()

    print(name)

    print("OID :", oid)

    print("Value :", value)

    print("Error :", error)

    print("-" * 60)
