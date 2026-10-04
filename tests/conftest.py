import sys
from pathlib import Path

# Permette a pytest di importare calcoli.py dalla cartella del progetto.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
