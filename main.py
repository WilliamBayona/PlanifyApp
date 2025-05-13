import uvicorn
import sys
from pathlib import Path

# Añadir directorio padre al path
BASE_DIR = Path(__file__).resolve().parent
sys.path.append(str(BASE_DIR.parent))

# Importar desde el paquete
from PlanifyApp.model.model import app

if __name__ == "__main__":
    uvicorn.run(
        "PlanifyApp.model.model:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        workers=1
    )