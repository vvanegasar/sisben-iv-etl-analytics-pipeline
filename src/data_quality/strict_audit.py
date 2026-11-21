import argparse
import json
import os
import re
import sys
import pyarrow.parquet as pq

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import sisben_config as cfg  # noqa: E402

cfg.load_dotenv()

_parser = argparse.ArgumentParser(
    description="Compara, columna por columna, el Parquet contra la tabla de hechos del modelo de Power BI."
)
_parser.add_argument("--parquet",
                     default=cfg.env("SISBEN_PARQUET_OUT", str(cfg.output_dir() / "sisben_master_final.parquet")),
                     help="Parquet a auditar (por defecto, SISBEN_PARQUET_OUT).")
_src = _parser.add_mutually_exclusive_group()
_src.add_argument("--pbi-columns-json",
                  help='JSON exportado del modelo con la forma {"data": [{"columns": [{"name": ...}]}]}.')
_src.add_argument("--tmdl-table",
                  default=str(cfg.REPO_ROOT / "model" / "tmdl_sisben" / "tables" / "fct_Sisben.tmdl"),
                  help="Archivo .tmdl de la tabla de hechos (por defecto, el del repositorio).")
_args = _parser.parse_args()


def _columnas_tmdl(path):
    """Nombres de columna declarados en un archivo .tmdl de tabla."""
    with open(path, "r", encoding="utf-8") as fh:
        texto = fh.read()
    nombres = re.findall(r"^\tcolumn (.+?)\s*$", texto, flags=re.M)
    return [n.split(" = ")[0].strip().strip("'") for n in nombres]


# 1. Columnas de Power BI
if _args.pbi_columns_json:
    with open(_args.pbi_columns_json, 'r', encoding='utf-8') as f:
        pbi_data = json.load(f)
    pbi_cols = [col["name"] for col in pbi_data["data"][0]["columns"]]
else:
    pbi_cols = _columnas_tmdl(_args.tmdl_table)

# 2. Columnas del Parquet
pf = pq.ParquetFile(_args.parquet)
pq_cols = [f.name for f in pf.schema]

print(f"PBI count: {len(pbi_cols)}")
print(f"PQ count: {len(pq_cols)}")

# Comparación exacta
missing_in_pq = [c for c in pbi_cols if c not in pq_cols]
extra_in_pq = [c for c in pq_cols if c not in pbi_cols]

print("\n--- FALTAN EN PARQUET (Exacto) ---")
for c in missing_in_pq:
    # Ver si es solo un tema de mayusculas
    match_case_insensitive = [p for p in pq_cols if p.lower() == c.lower()]
    if match_case_insensitive:
        print(f"CASE MISMATCH: '{c}' (PBI) vs '{match_case_insensitive[0]}' (PQ)")
    else:
        print(f"MISSING: '{c}'")

print("\n--- SOBRAN EN PARQUET (Exacto) ---")
for c in extra_in_pq:
    match_case_insensitive = [p for p in pbi_cols if p.lower() == c.lower()]
    if not match_case_insensitive:
        print(f"EXTRA: '{c}'")
