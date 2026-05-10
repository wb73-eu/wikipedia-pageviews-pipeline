import requests
from google.cloud import storage, bigquery
from datetime import datetime, timedelta, timezone

PROJECT_ID = "cloud-portfolio-project-495513"
BUCKET_NAME = "wikipedia-pageviews"
GCS_FOLDER = "raw"
DATASET = "wikipedia_raw"
TABLE = "pageviews"


def get_latest_available_hour() -> datetime:
    dt = datetime.now(timezone.utc).replace(minute=0, second=0, microsecond=0)

    for hours_back in range(1, 24):
        candidate = dt - timedelta(hours=hours_back)
        filename = f"pageviews-{candidate.year}{candidate.month:02d}{candidate.day:02d}-{candidate.hour:02d}0000.gz"
        url = (
            f"https://dumps.wikimedia.org/other/pageviews/"
            f"{candidate.year}/{candidate.year}-{candidate.month:02d}/{filename}"
        )
        response = requests.head(url)
        if response.status_code == 200:
            return candidate

    raise Exception("Could not find a recent available pageview file")


def get_pageview_url(dt: datetime) -> str:
    return (
        f"https://dumps.wikimedia.org/other/pageviews/"
        f"{dt.year}/{dt.year}-{dt.month:02d}/"
        f"pageviews-{dt.year}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}0000.gz"
    )


def ingest(dt: datetime):
    url = get_pageview_url(dt)
    filename = url.split("/")[-1]
    destination = f"{GCS_FOLDER}/{dt.year}/{dt.month:02d}/{dt.day:02d}/{filename}"

    print(f"Downloading {url}...")
    response = requests.get(url, stream=True)
    response.raise_for_status()

    print(f"Uploading to gs://{BUCKET_NAME}/{destination}...")
    client = storage.Client(project=PROJECT_ID)
    bucket = client.bucket(BUCKET_NAME)
    blob = bucket.blob(destination)
    blob.upload_from_file(response.raw, content_type="application/gzip")
    print("Upload done!")


def load(dt: datetime):
    client = bigquery.Client(project=PROJECT_ID)
    table_id = f"{PROJECT_ID}.{DATASET}.{TABLE}"
    table_ref = client.dataset(DATASET).table(TABLE)

    try:
        client.get_table(table_ref)
    except Exception:
        table = bigquery.Table(table_ref, schema=[
            bigquery.SchemaField("language_code", "STRING"),
            bigquery.SchemaField("page_title", "STRING"),
            bigquery.SchemaField("view_count", "INTEGER"),
            bigquery.SchemaField("response_size", "INTEGER"),
            bigquery.SchemaField("viewed_at", "TIMESTAMP"),
        ])
        table.time_partitioning = bigquery.TimePartitioning(
            type_=bigquery.TimePartitioningType.HOUR,
            field="viewed_at",
        )
        client.create_table(table)
        print("Table created.")

    filename = f"pageviews-{dt.year}{dt.month:02d}{dt.day:02d}-{dt.hour:02d}0000.gz"
    gcs_uri = f"gs://{BUCKET_NAME}/{GCS_FOLDER}/{dt.year}/{dt.month:02d}/{dt.day:02d}/{filename}"

    job_config = bigquery.LoadJobConfig(
        schema=[
            bigquery.SchemaField("language_code", "STRING"),
            bigquery.SchemaField("page_title", "STRING"),
            bigquery.SchemaField("view_count", "INTEGER"),
            bigquery.SchemaField("response_size", "INTEGER"),
        ],
        source_format=bigquery.SourceFormat.CSV,
        field_delimiter=" ",
        skip_leading_rows=1,
        quote_character="",
        write_disposition=bigquery.WriteDisposition.WRITE_APPEND,
    )

    print(f"Loading {gcs_uri} into {table_id}...")
    load_job = client.load_table_from_uri(gcs_uri, table_id, job_config=job_config)
    load_job.result()

    print(f"Updating viewed_at to {dt}...")
    client.query(f"""
        UPDATE `{table_id}`
        SET viewed_at = TIMESTAMP('{dt.isoformat()}')
        WHERE viewed_at IS NULL
    """).result()

    print(f"Loaded {load_job.output_rows} rows successfully!")


def main():
    dt = get_latest_available_hour()
    print(f"Latest available hour: {dt}")

    ingest(dt)
    load(dt)


if __name__ == "__main__":
    main()