"""
generate_synthetic_sample.py — muestra SINTÉTICA para correr el pipeline de punta a punta.

Todas las filas son inventadas con un generador aleatorio de semilla fija. No salen de ningún
registro real del Sisbén: solo copian el esquema de la tabla de hechos (sus 111 columnas base)
y los rangos de códigos que usa el ETL. Los códigos de municipio son los públicos de la DIVIPOLA.

Cómo reconocer que una fila es sintética:
  - Source.Name vale "SINTETICO_NO_REAL_<año>.csv" en todas las filas;
  - NOM_BARRIO vale "BARRIO SINTETICO <n>";
  - en la muestra de población, la columna FUENTE vale "SINTETICO";
  - los nombres de archivo dicen "synthetic".

Uso:
  # Regenerar las muestras versionadas en data/sample/ (mismo resultado con la misma semilla)
  python scripts/generate_synthetic_sample.py \
      --csv-out data/sample/sisben_synthetic_sample.csv \
      --poblacion-csv-out data/sample/poblacion_synthetic_sample.csv

  # Convertir la muestra versionada en el Parquet maestro de entrada del ETL
  python scripts/generate_synthetic_sample.py \
      --from-csv data/sample/sisben_synthetic_sample.csv --parquet-out out/sisben_master.parquet
"""
from __future__ import annotations

import argparse
import os

import numpy as np
import pandas as pd

SEED = 2026
MUNICIPIOS = ["05001", "05045", "05154", "05615", "05837"]  # códigos DIVIPOLA públicos (DANE)
ANIOS = [2021, 2022, 2023, 2024, 2025, 2026]                # seis cortes anuales
HOGARES_POR_MUNICIPIO_ANIO = 3
GRUPOS = {"A": 5, "B": 7, "C": 18, "D": 21}                  # grupos y subgrupos del Sisbén IV

# Las 111 columnas base de la tabla de hechos (model/tmdl_sisben/tables/fct_Sisben.tmdl), en orden.
COLUMNS = [
    "cod_mpio", "Cod_clase", "NOM_BARRIO", "tip_vivienda", "tip_mat_paredes", "tip_mat_pisos",
    "ind_tiene_energia", "ind_tiene_alcantarillado", "ind_tiene_gas", "ind_tiene_recoleccion", "ind_tiene_acueducto", "num_cuartos_vivienda",
    "num_hogares_vivienda", "ide_hogar", "tip_ocupa_vivienda", "num_cuartos_dormir", "tip_sanitario", "tip_ubi_sanitario",
    "tip_uso_sanitario", "tip_origen_agua", "ind_agua_llega_7dias", "ind_agua_llega_24horas", "tip_uso_agua_beber", "tip_elimina_basura",
    "ind_tiene_cocina", "tip_prepara_alimentos", "tip_uso_cocina", "tip_energia_cocina", "ind_tiene_nevera", "ind_tiene_lavadora",
    "ind_tiene_pc", "ind_tiene_internet", "ind_tiene_moto", "ind_tiene_tractor", "ind_tiene_carro", "ind_tiene_bien_raiz",
    "ind_gasto_alimento", "vlr_gasto_alimento", "ind_gasto_transporte", "vlr_gasto_transporte", "ind_gasto_educacion", "vlr_gasto_educacion",
    "ind_gasto_salud", "vlr_gasto_salud", "ind_gasto_serv_publicos", "vlr_gasto_serv_publicos", "ind_gasto_celular", "vlr_gasto_celular",
    "ind_gasto_arriendo", "vlr_gasto_arriendo", "ind_gasto_otros", "vlr_gasto_otros", "vlr_total_gastos", "ind_evento_inundacion",
    "num_evento_inundacion", "ind_evento_avalancha", "num_evento_avalancha", "ind_evento_terremoto", "num_evento_terremoto", "ind_evento_incendio",
    "num_evento_incendio", "ind_evento_vendaval", "ind_evento_hundimiento", "num_evento_hundimiento", "num_personas_hogar", "sexo_persona",
    "tip_parentesco", "ind_discap_ver", "ind_discap_oir", "ind_discap_hablar", "ind_discap_moverse", "ind_discap_bañarse",
    "ind_discap_salir", "ind_discap_entender", "ind_discap_ninguna", "tip_seg_social", "ind_acudio_salud", "ind_fue_atendido_salud",
    "tip_cuidado_niños", "ind_recibe_comida", "ind_leer_escribir", "ind_estudia", "niv_educativo", "grado_alcanzado",
    "ind_fondo_pensiones", "tip_actividad_mes", "H_5", "I1", "I2", "I3",
    "I4", "I5", "I6", "I7", "I8", "I9",
    "I10", "I11", "I12", "I13", "I14", "I15",
    "Clasificacion", "anio", "grupo_sisben", "Fec_digitacion", "Edad", "marca",
    "estado", "Source.Name", "Num_evento_vendaval",
]
STR_COLUMNS = ["cod_mpio", "NOM_BARRIO", "Clasificacion", "grupo_sisben", "Fec_digitacion", "marca", "estado", "Source.Name"]
INT_COLUMNS = [c for c in COLUMNS if c not in STR_COLUMNS]

DISCAPACIDADES = ["ind_discap_ver", "ind_discap_oir", "ind_discap_hablar", "ind_discap_moverse",
                  "ind_discap_bañarse", "ind_discap_salir", "ind_discap_entender"]
GASTOS = {"alimento": (200, 1500), "transporte": (20, 300), "educacion": (10, 400), "salud": (10, 300),
          "serv_publicos": (50, 400), "celular": (20, 150), "arriendo": (100, 1200), "otros": (10, 300)}  # miles de pesos
BIENES = [("nevera", 0.75), ("lavadora", 0.45), ("pc", 0.25), ("internet", 0.4),
          ("moto", 0.3), ("tractor", 0.01), ("carro", 0.1), ("bien_raiz", 0.08)]


def _si_no(rng: np.random.Generator, p_si: float) -> int:
    """Código de la ficha: 1 = sí, 2 = no."""
    return 1 if rng.random() < p_si else 2


def _hogar(rng: np.random.Generator, cod_mpio: str, anio: int, n: int) -> list[dict]:
    """Un hogar inventado, con una fila por persona."""
    cuartos = int(rng.integers(1, 7))
    vivienda = {
        "cod_mpio": cod_mpio,
        "Cod_clase": int(rng.choice([1, 2, 3], p=[0.6, 0.15, 0.25])),
        "NOM_BARRIO": f"BARRIO SINTETICO {n:02d}",
        "tip_vivienda": int(rng.choice([1, 2, 3, 4, 5], p=[0.6, 0.25, 0.1, 0.03, 0.02])),
        "tip_mat_paredes": int(rng.integers(0, 8)),
        "tip_mat_pisos": int(rng.integers(1, 7)),
        "ind_tiene_energia": _si_no(rng, 0.95),
        "ind_tiene_alcantarillado": _si_no(rng, 0.7),
        "ind_tiene_gas": _si_no(rng, 0.5),
        "ind_tiene_recoleccion": _si_no(rng, 0.75),
        "ind_tiene_acueducto": _si_no(rng, 0.85),
        "num_cuartos_vivienda": cuartos,
        "num_hogares_vivienda": 1,
        "ide_hogar": 1,
        "tip_ocupa_vivienda": int(rng.integers(1, 6)),
        "num_cuartos_dormir": int(rng.integers(1, cuartos + 1)),
        "tip_sanitario": int(rng.integers(1, 6)),
        "tip_ubi_sanitario": int(rng.integers(1, 3)),
        "tip_uso_sanitario": int(rng.integers(1, 3)),
        "tip_origen_agua": int(rng.integers(1, 8)),
        "ind_agua_llega_7dias": _si_no(rng, 0.8),
        "ind_agua_llega_24horas": _si_no(rng, 0.7),
        "tip_uso_agua_beber": int(rng.integers(1, 7)),
        "tip_elimina_basura": int(rng.integers(1, 6)),
        "ind_tiene_cocina": _si_no(rng, 0.9),
        "tip_prepara_alimentos": int(rng.integers(1, 4)),
        "tip_uso_cocina": int(rng.integers(1, 3)),
        "tip_energia_cocina": int(rng.integers(1, 7)),
    }
    vivienda.update({f"ind_tiene_{bien}": _si_no(rng, p) for bien, p in BIENES})

    gastos, total = {}, 0
    for nombre, (lo, hi) in GASTOS.items():
        si = _si_no(rng, 0.7)
        valor = int(rng.integers(lo, hi + 1)) * 1000 if si == 1 else 0
        gastos[f"ind_gasto_{nombre}"] = si
        gastos[f"vlr_gasto_{nombre}"] = valor
        total += valor
    gastos["vlr_total_gastos"] = total

    eventos = {}
    for evento in ["inundacion", "avalancha", "terremoto", "incendio", "hundimiento"]:
        si = _si_no(rng, 0.08)
        eventos[f"ind_evento_{evento}"] = si
        eventos[f"num_evento_{evento}"] = int(rng.integers(1, 4)) if si == 1 else 0
    si = _si_no(rng, 0.08)
    eventos["ind_evento_vendaval"] = si
    eventos["Num_evento_vendaval"] = int(rng.integers(1, 4)) if si == 1 else 0

    tam = int(rng.choice([1, 2, 3, 4, 5, 6], p=[0.15, 0.2, 0.25, 0.2, 0.12, 0.08]))
    letra = str(rng.choice(list(GRUPOS), p=[0.15, 0.27, 0.38, 0.20]))
    privaciones = {f"I{i}": int(rng.random() < 0.25) for i in range(1, 16)}
    hogar = {
        "num_personas_hogar": tam,
        "H_5": int(sum(privaciones.values()) >= 5),  # regla ilustrativa, no es el cálculo oficial del IPM
        **privaciones,
        "Clasificacion": f"{letra}{int(rng.integers(1, GRUPOS[letra] + 1))}",
        "grupo_sisben": letra,
        "anio": anio,
        "Fec_digitacion": f"{anio - 1}-{int(rng.integers(1, 13)):02d}-{int(rng.integers(1, 29)):02d}",
        "marca": str(rng.choice(["0", "10", "20"], p=[0.9, 0.05, 0.05])),
        "estado": str(rng.choice(["0", "30", "60", "70"], p=[0.9, 0.04, 0.03, 0.03])),
        "Source.Name": f"SINTETICO_NO_REAL_{anio}.csv",
    }

    filas = []
    for orden in range(1, tam + 1):
        jefe = orden == 1
        edad = int(rng.integers(18, 91)) if jefe else int(rng.integers(0, 91))
        discapacidad = int(rng.integers(0, len(DISCAPACIDADES))) if rng.random() < 0.08 else None
        persona = {
            "sexo_persona": int(rng.integers(1, 3)),
            "tip_parentesco": 1 if jefe else int(rng.integers(2, 10)),
            **{c: (1 if discapacidad == i else 2) for i, c in enumerate(DISCAPACIDADES)},
            "ind_discap_ninguna": 1 if discapacidad is None else 2,
            "tip_seg_social": int(rng.choice([0, 1, 2, 3, 9], p=[0.05, 0.35, 0.03, 0.55, 0.02])),
            "ind_acudio_salud": _si_no(rng, 0.3),
            "ind_fue_atendido_salud": _si_no(rng, 0.9),
            "tip_cuidado_niños": int(rng.integers(1, 7)) if edad < 6 else None,
            "ind_recibe_comida": _si_no(rng, 0.5) if edad < 6 else None,
            "ind_leer_escribir": _si_no(rng, 0.92) if edad >= 5 else None,
            "ind_estudia": _si_no(rng, 0.8 if edad < 18 else 0.1) if edad >= 5 else None,
            "niv_educativo": int(rng.integers(0, 10)) if edad >= 5 else None,
            "grado_alcanzado": int(rng.integers(0, 12)) if edad >= 5 else None,
            "ind_fondo_pensiones": _si_no(rng, 0.2) if edad >= 15 else None,
            "tip_actividad_mes": int(rng.integers(0, 8)) if edad >= 10 else None,
            "Edad": edad,
        }
        filas.append({**vivienda, **gastos, **eventos, **hogar, **persona})
    return filas


def _tipar(df: pd.DataFrame) -> pd.DataFrame:
    """Enteros como Int64 (con nulos) y textos como string, en el orden del esquema."""
    df = df[COLUMNS].copy()
    for c in INT_COLUMNS:
        df[c] = pd.to_numeric(df[c], errors="coerce").astype("Int64")
    for c in STR_COLUMNS:
        df[c] = df[c].astype("string")
    return df


def generar_sisben(seed: int = SEED) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    filas = []
    for anio in ANIOS:
        for cod_mpio in MUNICIPIOS:
            for n in range(1, HOGARES_POR_MUNICIPIO_ANIO + 1):
                filas.extend(_hogar(rng, cod_mpio, anio, n))
    return _tipar(pd.DataFrame(filas))


def generar_poblacion(seed: int = SEED) -> pd.DataFrame:
    """Proyección de población inventada, con las columnas que espera src/etl/etl_poblacion_cobertura.py."""
    rng = np.random.default_rng(seed + 1)
    filas = []
    for cod_mpio in MUNICIPIOS:
        for anio in ANIOS:
            for genero in ("Hombres", "Mujeres"):
                for area in ("Cabecera Municipal", "Centro Poblado y Rural Disperso"):
                    for edad in range(0, 81, 10):
                        filas.append({"DPMP": int(cod_mpio), "AÑO": anio, "Genero": genero, "ÁREA GEOGRÁFICA": area,
                                      "EDAD_NUM": edad, "Pob": int(rng.integers(50, 3000)), "FUENTE": "SINTETICO"})
    return pd.DataFrame(filas)


def leer_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, dtype={c: "string" for c in STR_COLUMNS}, encoding="utf-8")
    return _tipar(df)


def main() -> None:
    p = argparse.ArgumentParser(description="Genera o convierte la muestra sintética del Sisbén IV (sin datos reales).")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--from-csv", help="Usa esta muestra CSV en vez de generar una nueva.")
    p.add_argument("--csv-out", help="Dónde escribir la muestra de personas en CSV.")
    p.add_argument("--parquet-out", help="Dónde escribir la muestra como Parquet maestro de entrada del ETL.")
    p.add_argument("--poblacion-csv-out", help="Dónde escribir la muestra de proyección de población en CSV.")
    args = p.parse_args()
    if not (args.csv_out or args.parquet_out or args.poblacion_csv_out):
        p.error("indique al menos una salida: --csv-out, --parquet-out o --poblacion-csv-out")

    df = leer_csv(args.from_csv) if args.from_csv else generar_sisben(args.seed)
    for destino in (args.csv_out, args.parquet_out, args.poblacion_csv_out):
        if destino:
            os.makedirs(os.path.dirname(os.path.abspath(destino)), exist_ok=True)
    if args.csv_out:
        df.to_csv(args.csv_out, index=False, encoding="utf-8", lineterminator="\n")
        print(f"Muestra sintética: {len(df)} filas × {df.shape[1]} columnas → {args.csv_out}")
    if args.parquet_out:
        df.to_parquet(args.parquet_out, index=False)
        print(f"Parquet maestro sintético: {len(df)} filas → {args.parquet_out}")
    if args.poblacion_csv_out:
        pob = generar_poblacion(args.seed)
        pob.to_csv(args.poblacion_csv_out, index=False, encoding="utf-8", lineterminator="\n")
        print(f"Proyección de población sintética: {len(pob)} filas → {args.poblacion_csv_out}")


if __name__ == "__main__":
    main()
