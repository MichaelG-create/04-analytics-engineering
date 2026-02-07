Quick hack to load files directly to GCS, without Airflow. Downloads csv files from https://nyc-tlc.s3.amazonaws.com/trip+data/ and uploads them to your Cloud Storage Account as parquet files.

1. Install pre-reqs with `uv sync` 
2. Run: `uv run python web_csv_parquet_GCS_FHV.py`

