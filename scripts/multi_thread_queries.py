# BEGIN OTEL INSTRUMENTATION
from opentelemetry.instrumentation.mysql import MySQLInstrumentor
from opentelemetry.instrumentation.threading import ThreadingInstrumentor

# Instrument MySQL and threading so that queries and thread execution produce spans
MySQLInstrumentor().instrument()
ThreadingInstrumentor().instrument()
# END OTEL INSTRUMENTATION

# scripts/multi_thread_queries.py
import threading
import random
import datetime
import os
import mysql.connector

from opentelemetry import trace
from opentelemetry.instrumentation.mysql import MySQLInstrumentor
from opentelemetry.instrumentation.threading import ThreadingInstrumentor
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

resource = Resource.create({"service.name": "climate-test"})
provider = TracerProvider(resource=resource)
span_processor = BatchSpanProcessor(OTLPSpanExporter(endpoint="localhost:4317", insecure=True))
provider.add_span_processor(span_processor)
trace.set_tracer_provider(provider)

MySQLInstrumentor().instrument()
ThreadingInstrumentor().instrument()

# Instrument MySQL and threading
MySQLInstrumentor().instrument()
ThreadingInstrumentor().instrument()


DB_HOST = os.getenv("DB_HOST", "127.0.0.1")
DB_USER = os.getenv("DB_USER", "root")
DB_PASSWORD = os.getenv("DB_PASSWORD", "Secret5555")
DB_NAME = os.getenv("DB_NAME", "project_db")

def get_connection():
    return mysql.connector.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD,
        database=DB_NAME
    )

def insert_record():
    conn = get_connection()
    cur = conn.cursor()
    sql = "INSERT INTO ClimateData (location, record_date, temperature, precipitation, humidity) VALUES (%s, %s, %s, %s, %s)"
    location = random.choice(["Ottawa", "Toronto", "Vancouver", "Montreal"])
    date = datetime.date.today() - datetime.timedelta(days=random.randint(0, 365))
    temperature = round(random.uniform(-10, 35), 2)
    precipitation = round(random.uniform(0, 50), 2)
    humidity = round(random.uniform(20, 100), 2)
    cur.execute(sql, (location, date, temperature, precipitation, humidity))
    conn.commit()
    cur.close()
    conn.close()

def select_records():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM ClimateData WHERE temperature > 20")
    count = cur.fetchone()[0]
    print(f"Records with temperature > 20°C: {count}")
    cur.close()
    conn.close()

def update_records():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("UPDATE ClimateData SET humidity = humidity + 1 WHERE location = 'Ottawa'")
    conn.commit()
    cur.close()
    conn.close()

def run_threads():
    threads = []
    for _ in range(5):
        threads.append(threading.Thread(target=insert_record))
        threads.append(threading.Thread(target=select_records))
        threads.append(threading.Thread(target=update_records))

    for t in threads:
        t.start()
    for t in threads:
        t.join()

if __name__ == "__main__":
    run_threads()
