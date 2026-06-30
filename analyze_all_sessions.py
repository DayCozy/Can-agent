import pandas as pd, pathlib, json, datetime

DATA_DIR = pathlib.Path('data/logs')
OUT_CSV  = 'data/session_summary.csv'
OUT_JSON = 'data/session_summary.json'

# Alle nicht-leeren CSVs laden
csv_files = [f for f in sorted(DATA_DIR.glob('session_*.csv'), key=lambda p: p.stat().st_mtime) if f.stat().st_size > 500]
print(f"Verarbeite {len(csv_files)} nicht-leere Sessions...")

frames = []
for f in csv_files:
    df = pd.read_csv(f, parse_dates=['timestamp'], low_memory=False)
    df['_session_file'] = f.name
    frames.append(df)

all_df = pd.concat(frames, ignore_index=True)
print(f"Rows gesamt: {len(all_df)}")

# Numerische Spalten
num_cols = ['rpm','coolant_temp','vehicle_speed','throttle_position','engine_load','maf_rate']

# Statistik pro PID über alle Sessions
stats = {}
for col in num_cols:
    if col in all_df.columns:
        series = pd.to_numeric(all_df[col], errors='coerce').dropna()
        if len(series) > 0:
            stats[col] = {
                'count':  int(len(series)),
                'min':    round(float(series.min()), 2),
                'max':    round(float(series.max()), 2),
                'median': round(float(series.median()), 2),
                'mean':   round(float(series.mean()), 2),
                'std':    round(float(series.std()), 2),
            }

# Per-Session-Statistik
session_stats = []
for f in csv_files:
    df = pd.read_csv(f, low_memory=False)
    row = {'session': f.name, 'rows': len(df)}
    for col in num_cols:
        if col in df.columns:
            s = pd.to_numeric(df[col], errors='coerce').dropna()
            row[f'{col}_min']  = round(float(s.min()), 1) if len(s) > 0 else None
            row[f'{col}_max']  = round(float(s.max()), 1) if len(s) > 0 else None
            row[f'{col}_med']  = round(float(s.median()), 1) if len(s) > 0 else None
    session_stats.append(row)

session_df = pd.DataFrame(session_stats)

# Speichern
session_df.to_csv(OUT_CSV, index=False)
with open(OUT_JSON, 'w') as jf:
    json.dump({'overall': stats, 'generated': datetime.datetime.now().isoformat()}, jf, indent=2)

print(f"\n=== Gesamtstatistik über alle Sessions ({len(csv_files)} Dateien) ===\n")
for col, s in stats.items():
    print(f"{col:20s}  count={s['count']:6}  min={s['min']:8.2f}  max={s['max']:8.2f}  median={s['median']:8.2f}  mean={s['mean']:8.2f}  std={s['std']:8.2f}")

print(f"\nPer-Session-Statistik gespeichert: {OUT_CSV}")
print(f"JSON-Zusammenfassung gespeichert:  {OUT_JSON}")
