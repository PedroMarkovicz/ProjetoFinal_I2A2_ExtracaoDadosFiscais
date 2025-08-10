import os
import sys
from pathlib import Path

# Garante que a raiz do projeto (onde está a pasta src/) esteja no PYTHONPATH
PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if SRC_DIR.exists() and str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

# Evita que variáveis de ambiente sensíveis quebrem os testes
os.environ.setdefault("PYTHONWARNINGS", "ignore")