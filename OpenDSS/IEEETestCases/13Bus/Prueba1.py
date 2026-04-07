import json
import sys

# Simular algunos datos de ejemplo
datos = {
    "voltajes": [
        {"barra": "634", "voltaje": 1.02},
        {"barra": "635", "voltaje": 1.03},
        {"barra": "636", "voltaje": 1.01}
    ]
}

# Imprimir los datos en formato JSON
print(json.dumps(datos))
