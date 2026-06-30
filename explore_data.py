import pandas as pd, pathlib, matplotlib.pyplot as plt

DATA_DIR = pathlib.Path('data/logs')

# Nur nicht-leere CSV-Dateien nach Datum filtern
csv_files = [f for f in sorted(DATA_DIR.glob('session_*.csv'), key=lambda p: p.stat().st_mtime) if f.stat().st_size > 500]
print(f"Gefundene nicht-leere CSV-Logs: {len(csv_files)}")

# Neueste nicht-leere Datei
latest = csv_files[-1]
print(f"Lade: {latest.name} ({latest.stat().st_size} bytes)")

df = pd.read_csv(latest, parse_dates=['timestamp'])

print("\n--- Kopf der Daten ---")
print(df.head(10))
print(f"\nZeilen: {len(df)}")
print("\n--- Fehlende Werte in % ---")
print(df.isna().mean().round(2) * 100)
print("\n--- Grundstatistik ---")
print(df.describe())

# Plot als PNG speichern statt show()
fig, ax1 = plt.subplots(figsize=(12, 4))
ax1.set_xlabel('Zeit')
ax1.set_ylabel('RPM', color='red')
ax1.plot(df['timestamp'], df['rpm'], color='red', label='RPM')
ax1.tick_params(axis='y', labelcolor='red')

ax2 = ax1.twinx()
ax2.set_ylabel('km/h', color='blue')
ax2.plot(df['timestamp'], df['vehicle_speed'], color='blue', label='Geschwindigkeit')
ax2.tick_params(axis='y', labelcolor='blue')

fig.suptitle(f'RPM & Geschwindigkeit – {latest.stem}')
fig.tight_layout()

out = f"explore_{latest.stem}.png"
plt.savefig(out)
print(f"\nPlot gespeichert: {out}")
