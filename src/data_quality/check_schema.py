import argparse
import os
import sys

import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sisben_config as cfg  # noqa: E402

cfg.load_dotenv()

_parser = argparse.ArgumentParser(description="Revisa el esquema del Parquet y cruza año × estado y año × marca.")
_parser.add_argument("parquet", nargs="?",
                     default=cfg.env("SISBEN_PARQUET_OUT", str(cfg.output_dir() / "sisben_master_final.parquet")),
                     help="Parquet a revisar (por defecto, SISBEN_PARQUET_OUT).")
PARQUET_FILE = _parser.parse_args().parquet

try:
    schema = pq.read_schema(PARQUET_FILE)
    print("Columnas en el parquet:")
    print(schema.names[-20:])  # Las últimas 20 columnas

    # read 1M rows
    pf = pq.ParquetFile(PARQUET_FILE)
    df = next(pf.iter_batches(batch_size=2000000, columns=['anio', 'estado', 'marca'])).to_pandas()
    print("\nCrosstab Año x Estado:")
    print(df.groupby(['anio', 'estado'], dropna=False).size())
    print("\nCrosstab Año x Marca:")
    print(df.groupby(['anio', 'marca'], dropna=False).size())
except Exception as e:
    print(e)
