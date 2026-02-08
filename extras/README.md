Quick hack to load the FHV 2019 files directly to GCS, without Airflow. 
Downloads csv files from https://nyc-tlc.s3.amazonaws.com/trip+data/ 
and uploads them to your Cloud Storage Account as parquet files.

1. Install pre-reqs with `cd 1_csv_parquet_to_GCS && uv sync` 
2. Run: `uv run python web_csv_parquet_GCS_FHV.py`

Then run this Kestra flow having your google credentials csv path well specified in kestra docker-compose:
3. Run `cd 2_kestra_GCS_to_BQ && docker compose up` 
4. load the flow in kestra `2_GCP_taxi_fhv_scheduled_GCS_to_BQ.yml`
5. backfill from '2019-01-01' to '2019-12-02' (as it triggers the first of each month)

6. Then `dbt debug` your model in dev to check it passes first step of configuration,
7. Then `dbt run` (still dev)
8. Then `dbt build` (still dev)
9. Then `dbt build` now on prod
10. Then go to BQ to check your table stg_fhv_datatrip

Take a break and enjoy ;)
