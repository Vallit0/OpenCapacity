"""
Utilidades de preprocesamiento de archivos DSS.

Centraliza la logica de limpieza para que sea reutilizable tanto desde
DSSEngine como desde las rutas de la API (ej: para reportar advertencias
al usuario antes de compilar).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import List


@dataclass
class PreprocessResult:
    content: str
    warnings: List[str] = field(default_factory=list)


def preprocess_dss(content: str) -> PreprocessResult:
    """
    Aplica todos los pasos de limpieza al contenido de un archivo DSS.

    Pasos:
    1. Eliminar redirect a IEEELineCodes.dss
    2. Eliminar buscoords (no afecta la simulacion)
    3. Eliminar el parametro basekv invalido en linecodes

    Returns PreprocessResult con el contenido limpio y la lista de advertencias
    generadas para informar al usuario.
    """
    warnings: List[str] = []

    # 1. Redirect a IEEELineCodes
    original = content
    content = re.sub(
        r"(?im)^.*redirect\s+.*ieeelinecodes.*\.dss.*$", "", content
    )
    if content != original:
        warnings.append(
            "Se elimino referencia a IEEELineCodes.dss "
            "(se resuelve automaticamente si se adjunta el archivo)."
        )

    # 2. BusCoords
    original = content
    content = re.sub(r"(?im)^.*buscoords.*\.csv.*$", "", content)
    if content != original:
        warnings.append(
            "Se elimino referencia a BusCoords CSV "
            "(no afecta los calculos electricos)."
        )

    # 3. basekv invalido en linecodes
    content, n_subs = re.subn(
        r"(new\s+linecode[^\n]*)\bbasekv\s*=\s*[\d.]+\s*",
        r"\1",
        content,
        flags=re.IGNORECASE,
    )
    if n_subs > 0:
        warnings.append(
            f"Se elimino el parametro 'basekv' de {n_subs} definicion(es) "
            "de linecode (parametro invalido en esta version de OpenDSS)."
        )

    return PreprocessResult(content=content, warnings=warnings)


def extract_redirected_files(content: str) -> List[str]:
    """
    Extrae los nombres de archivos referenciados con 'Redirect' en el DSS.
    Util para informar al usuario que archivos necesita adjuntar.
    """
    pattern = re.compile(r"(?im)^\s*redirect\s+(.+\.dss)\s*$")
    return [m.group(1).strip() for m in pattern.finditer(content)]
