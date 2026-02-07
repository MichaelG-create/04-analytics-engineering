import os
import requests
import pandas as pd
from google.cloud import storage
from dotenv import load_dotenv
from tqdm import tqdm
from io import BytesIO
import pyarrow as pa
import pyarrow.parquet as pq

# 1) Load env
load_dotenv()
BUCKET = os.environ.get("GCP_GCS_BUCKET", "dtc-datalake-nyc-bucket")

BASE_URL = "https://github.com/DataTalksClub/nyc-tlc-data/releases/download"

# 2) Common dtypes + parse_dates for FHV
FHV_DTYPES = {
    "dispatching_base_num": "string",
    "PUlocationID": "Int64",
    "DOlocationID": "Int64",
    "SR_Flag": "string",
    "Affiliated_base_number": "string",
}

FHV_PARSE_DATES = ["pickup_datetime", "dropOff_datetime"]


def download_csv_stream(url: str, desc: str = "") -> bytes:
    """Download gzipped CSV as bytes with a progress bar."""
    with requests.get(url, stream=True, timeout=60) as r:
        r.raise_for_status()
        total = int(r.headers.get("content-length", 0))
        chunks = []
        with tqdm(
            total=total,
            unit="B",
            unit_scale=True,
            unit_divisor=1024,
            desc=desc or "Downloading",
        ) as bar:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if not chunk:
                    continue
                chunks.append(chunk)
                bar.update(len(chunk))
    return b"".join(chunks)


def csv_bytes_to_parquet_bytes(csv_bytes: bytes) -> bytes:
    """Convert gzipped CSV bytes → Parquet bytes (single file) with correct schema."""
    reader = pd.read_csv(
        BytesIO(csv_bytes),
        dtype=FHV_DTYPES,
        parse_dates=FHV_PARSE_DATES,
        compression="gzip",
        low_memory=False,
        chunksize=100_000,
    )

    sink = pa.BufferOutputStream()
    writer = None

    total_rows = 0
    for chunk in reader:
        table = pa.Table.from_pandas(chunk)
        total_rows += len(chunk)
        if writer is None:
            writer = pq.ParquetWriter(sink, table.schema)
        else:
            table = table.cast(writer.schema)
        writer.write_table(table)

    if writer is not None:
        writer.close()

    return sink.getvalue().to_pybytes(), total_rows


def upload_bytes_to_gcs(bucket: str, object_name: str, data: bytes):
    client = storage.Client()
    bucket_obj = client.bucket(bucket)
    blob = bucket_obj.blob(object_name)

    if blob.exists(client):
        print(f"Skipping upload, already in GCS: gs://{bucket}/{object_name}")
        return

    size = len(data)
    with tqdm(
        total=size,
        unit="B",
        unit_scale=True,
        unit_divisor=1024,
        desc=f"Uploading {object_name}",
    ) as bar:
        # Stream from memory
        from io import BytesIO

        buf = BytesIO(data)
        def read_chunk(chunk_size):
            while True:
                chunk = buf.read(chunk_size)
                if not chunk:
                    break
                yield chunk

        # Manual upload with progress
        chunk_size = 5 * 1024 * 1024
        client = storage.Client()
        blob = bucket_obj.blob(object_name)
        blob.chunk_size = chunk_size
        with blob.open("wb") as f:
            for chunk in read_chunk(chunk_size):
                f.write(chunk)
                bar.update(len(chunk))

    print(f"Uploaded to GCS: gs://{bucket}/{object_name}")


def fhv_web_to_gcs(year: str):
    service = "fhv"
    for i in tqdm(range(12), desc=f"{service} {year}", unit="month"):
        month = f"{i + 1:02d}"

        csv_file_name = f"{service}_tripdata_{year}-{month}.csv.gz"
        parquet_file_name = csv_file_name.replace(".csv.gz", ".parquet")
        object_name = f"{service}/{parquet_file_name}"  # gs://bucket/fhv/fhv_tripdata_2019-01.parquet

        # 1) Skip if already in GCS
        client = storage.Client()
        bucket_obj = client.bucket(BUCKET)
        blob = bucket_obj.blob(object_name)
        if blob.exists(client):
            print(f"Already in GCS, skipping: gs://{BUCKET}/{object_name}")
            continue

        # 2) Download CSV.gz (stream, with progress; all local)
        url = f"{BASE_URL}/{service}/{csv_file_name}"
        print(f"\n=== {url} ===")
        csv_bytes = download_csv_stream(url, desc=f"Downloading {csv_file_name}")

        # 3) Convert to Parquet (in memory, chunked)
        parquet_bytes, total_rows = csv_bytes_to_parquet_bytes(csv_bytes)
        print(f"Parquet {parquet_file_name} rows: {total_rows}")

        # 4) Upload Parquet to GCS
        upload_bytes_to_gcs(BUCKET, object_name, parquet_bytes)


# Example: full FHV year locally from VSCode
fhv_web_to_gcs("2019")
