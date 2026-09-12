from __future__ import annotations

import io
import re
from dataclasses import asdict, dataclass
from typing import Iterable

from docx import Document
from pypdf import PdfReader


STOPWORDS = {
    "para", "como", "con", "del", "las", "los", "una", "uno", "por", "que",
    "sus", "este", "esta", "desde", "hasta", "sobre", "entre", "trabajo", "puesto",
    "buscamos", "ser", "tener", "años", "experiencia", "perfil", "equipo", "nivel",
}


@dataclass
class AnalysisResult:
    score_compatibilidad: int
    coincidencias: list[str]
    palabras_clave_faltantes: list[str]
    puntos_fuertes: list[str]
    recomendaciones: list[str]
    advertencias: list[str]
    modo: str = "demo"

    def to_dict(self) -> dict:
        return asdict(self)


def clean_text(text: str) -> str:
    """Normaliza el texto sin alterar su contenido semántico."""
    text = text.replace("\x00", " ").replace("\r", "\n")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text(file_bytes: bytes, filename: str) -> str:
    suffix = filename.lower().rsplit(".", 1)[-1]
    if suffix == "pdf":
        reader = PdfReader(io.BytesIO(file_bytes))
        text = "\n".join((page.extract_text() or "") for page in reader.pages)
    elif suffix == "docx":
        document = Document(io.BytesIO(file_bytes))
        text = "\n".join(p.text for p in document.paragraphs)
    elif suffix == "txt":
        text = file_bytes.decode("utf-8", errors="replace")
    else:
        raise ValueError("Formato no admitido. Usá PDF, DOCX o TXT.")
    text = clean_text(text)
    if len(text) < 80:
        raise ValueError("No se pudo extraer texto suficiente del archivo.")
    return text


def _tokens(text: str) -> list[str]:
    words = re.findall(r"[a-záéíóúñ0-9+#.]{3,}", text.lower())
    return [w for w in words if w not in STOPWORDS and not w.isdigit()]


def _unique(items: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(items))


def demo_analyze(cv_text: str, job_text: str) -> AnalysisResult:
    """Evaluación reproducible para demostrar el flujo sin enviar datos a una API."""
    cv_tokens = set(_tokens(cv_text))
    job_tokens = _unique(_tokens(job_text))
    matched = [token for token in job_tokens if token in cv_tokens]
    missing = [token for token in job_tokens if token not in cv_tokens]
    denominator = max(len(job_tokens), 1)
    score = round(100 * len(matched) / denominator)
    score = max(0, min(100, score))

    strengths = []
    if matched:
        strengths.append("Coincidencia explícita en: " + ", ".join(matched[:5]) + ".")
    if re.search(r"\b(power bi|sql|excel|python)\b", cv_text, re.I):
        strengths.append("El CV declara herramientas técnicas relevantes.")
    if re.search(r"\b(implement|analiz|gestion|coordin|optim|automat)\w*", cv_text, re.I):
        strengths.append("La experiencia incluye verbos de acción.")
    while len(strengths) < 3:
        strengths.append("La información puede reorganizarse para facilitar la lectura del reclutador.")

    recommendations = [
        "Incorporar solo las palabras clave faltantes que representen experiencia real.",
        "Reescribir cada tarea con verbo de acción, herramienta utilizada y resultado comprobable.",
        "Agregar métricas únicamente cuando exista un dato verificable para respaldarlas.",
    ]
    warnings = [
        "El puntaje es orientativo y no reproduce un ATS comercial.",
        "El modo demo usa coincidencia léxica; la evaluación semántica requiere la API de IA.",
    ]
    return AnalysisResult(
        score_compatibilidad=score,
        coincidencias=matched[:12],
        palabras_clave_faltantes=missing[:12],
        puntos_fuertes=strengths[:3],
        recomendaciones=recommendations,
        advertencias=warnings,
    )


def demo_optimize(cv_text: str, target_role: str, analysis: AnalysisResult) -> str:
    missing = ", ".join(analysis.palabras_clave_faltantes[:8]) or "ninguna prioritaria"
    return f"""# CV orientado a {target_role}

## Perfil profesional

Perfil interesado en el rol de **{target_role}**. La versión definitiva debe resumir aquí la experiencia y las herramientas que ya estén respaldadas por el CV original.

## Contenido original normalizado

{clean_text(cv_text)}

## Recomendaciones de adaptación

- Revisar estas palabras clave: {missing}.
- Integrar únicamente aquellas que sean verdaderas y comprobables.
- Convertir tareas en logros con la estructura: verbo + tarea o herramienta + resultado verificable.

> Resultado generado en modo demo. No se agregaron empleos, estudios, herramientas ni métricas nuevas.
"""


def validate_lengths(cv_text: str, target_role: str, job_text: str) -> None:
    if len(target_role.strip()) < 3:
        raise ValueError("Ingresá un puesto objetivo válido.")
    if len(cv_text.strip()) < 120:
        raise ValueError("El CV debe contener al menos 120 caracteres.")
    if len(job_text.strip()) < 80:
        raise ValueError("La descripción del puesto debe contener al menos 80 caracteres.")
    if len(cv_text) > 50_000 or len(job_text) > 20_000:
        raise ValueError("El texto supera el límite de esta versión del prototipo.")
