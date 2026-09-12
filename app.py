from __future__ import annotations

import json
from datetime import datetime, timezone

import streamlit as st

from ai_service import analyze_cv, audit_cv, optimize_cv, send_webhook
from core import demo_analyze, demo_optimize, extract_text, validate_lengths


st.set_page_config(page_title="CV Clarity AI", page_icon="◈", layout="wide")
st.markdown("""
<style>
.block-container {max-width: 1120px; padding-top: 2rem;}
[data-testid="stMetric"] {background:#F4F7FF; border:1px solid #DCE5FF; padding:18px; border-radius:14px;}
.small-note {color:#596273; font-size:.9rem;}
</style>
""", unsafe_allow_html=True)

st.title("CV Clarity AI")
st.caption("Diagnóstico y optimización responsable de CV para una vacante concreta")

with st.sidebar:
    st.header("Configuración")
    mode = st.radio("Modo", ["Demo sin API", "IA con Gemini"], help="El modo demo permite probar todo el flujo sin credenciales.")
    api_key = st.text_input("Gemini API Key", type="password", disabled=mode == "Demo sin API")
    webhook = st.text_input("Webhook de Make opcional", type="password", help="Envía solo resumen y timestamp; nunca el CV completo.")
    st.markdown('<p class="small-note">Los textos se procesan en la sesión y no se guardan en una base de datos.</p>', unsafe_allow_html=True)

left, right = st.columns([1, 1])
with left:
    st.subheader("1  Puesto objetivo")
    target_role = st.text_input("Nombre del puesto", placeholder="Analista de Datos Junior")
    job_text = st.text_area("Descripción de la vacante", height=260, placeholder="Pegá requisitos, responsabilidades y herramientas solicitadas...")
with right:
    st.subheader("2  Currículum")
    input_method = st.radio("Forma de ingreso", ["Pegar texto", "Subir archivo"], horizontal=True)
    cv_text = ""
    if input_method == "Pegar texto":
        cv_text = st.text_area("Contenido del CV", height=260, placeholder="Pegá el CV completo...")
    else:
        uploaded = st.file_uploader("PDF, DOCX o TXT", type=["pdf", "docx", "txt"])
        if uploaded:
            try:
                cv_text = extract_text(uploaded.getvalue(), uploaded.name)
                st.success(f"Texto extraído: {len(cv_text):,} caracteres")
                with st.expander("Revisar texto extraído"):
                    st.text(cv_text[:6000])
            except Exception as exc:
                st.error(str(exc))

run = st.button("Analizar y optimizar", type="primary", use_container_width=True)

if run:
    try:
        validate_lengths(cv_text, target_role, job_text)
        if mode == "IA con Gemini" and not api_key:
            raise ValueError("Ingresá una API Key o seleccioná el modo demo.")

        with st.spinner("Procesando información..."):
            if mode == "IA con Gemini":
                analysis = analyze_cv(api_key, cv_text, target_role, job_text)
                draft = optimize_cv(api_key, cv_text, target_role, job_text, analysis)
                audit = audit_cv(api_key, cv_text, draft)
                optimized = audit.cv_corregido_markdown
            else:
                analysis = demo_analyze(cv_text, job_text)
                optimized = demo_optimize(cv_text, target_role, analysis)
                audit = None

        st.session_state["analysis"] = analysis.to_dict()
        st.session_state["optimized"] = optimized
        st.session_state["audit"] = audit.model_dump() if audit else None

        if webhook:
            try:
                send_webhook(webhook, {
                    "event": "cv_analysis_completed",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "target_role": target_role,
                    "score": analysis.score_compatibilidad,
                    "mode": analysis.modo,
                })
                st.toast("Resumen enviado al workflow de Make")
            except Exception:
                st.warning("El análisis terminó, pero el webhook no respondió.")
    except Exception as exc:
        st.error(str(exc))

if "analysis" in st.session_state:
    result = st.session_state["analysis"]
    st.divider()
    st.subheader("3  Resultado")
    m1, m2, m3 = st.columns(3)
    m1.metric("Compatibilidad orientativa", f"{result['score_compatibilidad']} / 100")
    m2.metric("Coincidencias", len(result["coincidencias"]))
    m3.metric("Brechas detectadas", len(result["palabras_clave_faltantes"]))

    tab1, tab2, tab3 = st.tabs(["Diagnóstico", "CV optimizado", "Control de calidad"])
    with tab1:
        a, b = st.columns(2)
        with a:
            st.markdown("#### Puntos fuertes")
            for item in result["puntos_fuertes"]:
                st.write("- " + item)
            st.markdown("#### Coincidencias")
            st.write(", ".join(result["coincidencias"]) or "Sin coincidencias explícitas")
        with b:
            st.markdown("#### Palabras o capacidades a revisar")
            for item in result["palabras_clave_faltantes"]:
                st.write("- " + item)
            st.markdown("#### Próximos pasos")
            for item in result["recomendaciones"]:
                st.write("- " + item)
    with tab2:
        st.markdown(st.session_state["optimized"])
        st.download_button("Descargar CV en Markdown", st.session_state["optimized"], "cv_optimizado.md", "text/markdown")
    with tab3:
        audit_data = st.session_state.get("audit")
        if audit_data:
            status = "Aprobado" if audit_data["aprobado"] else "Revisado con correcciones"
            st.write(f"**Estado de auditoría:** {status}")
            if audit_data["afirmaciones_no_respaldadas"]:
                st.write("Afirmaciones detectadas:")
                for item in audit_data["afirmaciones_no_respaldadas"]:
                    st.write("- " + item)
        else:
            st.info("En modo demo se conserva el texto original y no se agregan afirmaciones nuevas.")
        for warning in result["advertencias"]:
            st.warning(warning)
        st.download_button("Descargar diagnóstico JSON", json.dumps(result, ensure_ascii=False, indent=2), "diagnostico.json", "application/json")
