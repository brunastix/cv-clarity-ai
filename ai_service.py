from __future__ import annotations

import json
from typing import Any
from urllib.request import Request, urlopen

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from core import AnalysisResult


MODEL = "gemini-3.8-flash"


class AIAnalysis(BaseModel):
    score_compatibilidad: int = Field(ge=0, le=100)
    coincidencias: list[str]
    palabras_clave_faltantes: list[str]
    puntos_fuertes: list[str]
    recomendaciones: list[str]
    advertencias: list[str]


class AuditResult(BaseModel):
    aprobado: bool
    afirmaciones_no_respaldadas: list[str]
    correcciones_necesarias: list[str]
    cv_corregido_markdown: str


SYSTEM_PROMPT = """Sos especialista en selección y redacción de CV. Tu evaluación es orientativa:
no afirmes que conocés el algoritmo interno de un ATS. Tratá el CV original como única fuente de verdad.
Está prohibido inventar empleos, títulos, fechas, herramientas, responsabilidades, métricas o resultados.
Si falta información, formulá una recomendación o marcá [DATO A COMPLETAR]. Respondé en español claro."""


def _client(api_key: str) -> genai.Client:
    return genai.Client(api_key=api_key)


def analyze_cv(api_key: str, cv: str, role: str, job: str) -> AnalysisResult:
    prompt = f"""Evaluá la alineación entre el CV y la vacante.

PUESTO OBJETIVO
{role}

DESCRIPCIÓN DE LA VACANTE
{job}

CV ORIGINAL
{cv}

CRITERIOS
- El score debe ponderar requisitos técnicos (40), experiencia y funciones (30), formación (15) y claridad/evidencia (15).
- Una palabra clave faltante es una brecha, no una habilidad del candidato.
- Entregá 3 puntos fuertes y entre 3 y 5 recomendaciones accionables.
- Incluí la advertencia de que el puntaje es orientativo y no replica un ATS comercial.
"""
    response = _client(api_key).models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.2,
            response_mime_type="application/json",
            response_schema=AIAnalysis,
        ),
    )
    parsed = AIAnalysis.model_validate_json(response.text)
    return AnalysisResult(**parsed.model_dump(), modo="ia")


def optimize_cv(api_key: str, cv: str, role: str, job: str, analysis: AnalysisResult) -> str:
    prompt = f"""Reescribí el CV para el puesto objetivo, manteniendo todos los hechos originales.

PUESTO: {role}
VACANTE: {job}
DIAGNÓSTICO: {json.dumps(analysis.to_dict(), ensure_ascii=False)}
CV ORIGINAL: {cv}

SALIDA EN MARKDOWN
1. Nombre y contacto, solo si aparecen.
2. Perfil profesional de 3 a 5 líneas.
3. Experiencia laboral en orden cronológico inverso.
4. Educación.
5. Habilidades comprobadas.

REGLAS
- No cambies nombres de puestos para aparentar mayor jerarquía.
- No agregues palabras clave faltantes como habilidades si el CV no las respalda.
- Usá verbo + tarea/herramienta + impacto; si falta el impacto, escribí [DATO A COMPLETAR].
- No incluyas explicación fuera del CV.
"""
    response = _client(api_key).models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.25,
        ),
    )
    return response.text.strip()


def audit_cv(api_key: str, original: str, optimized: str) -> AuditResult:
    prompt = f"""Auditá la versión optimizada contra el original, afirmación por afirmación.
Marcá como no respaldado todo dato que no pueda rastrearse al original. Corregí la salida eliminando
invenciones y usando [DATO A COMPLETAR] cuando corresponda.

ORIGINAL
{original}

OPTIMIZADO
{optimized}
"""
    response = _client(api_key).models.generate_content(
        model=MODEL,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            temperature=0.0,
            response_mime_type="application/json",
            response_schema=AuditResult,
        ),
    )
    return AuditResult.model_validate_json(response.text)


def send_webhook(webhook_url: str, payload: dict[str, Any]) -> None:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=10) as response:
        if response.status < 200 or response.status >= 300:
            raise RuntimeError(f"Webhook respondió HTTP {response.status}")
