# -*- coding: utf-8 -*-
"""
Servidor FastAPI — capa de integracion del asistente (seccion 5.6 TFM).

Expone un unico endpoint POST /consulta que recibe la pregunta del usuario,
la URL de la sede electronica activa y el nombre del campo del formulario
que tiene el foco, y devuelve la respuesta generada por el pipeline completo
(anonimizacion → RAG → LLM).

Arrancar con:
    uvicorn assistant.backend:app --host 127.0.0.1 --port 8000 --reload
o desde la raiz del proyecto:
    python -m uvicorn assistant.backend:app --host 127.0.0.1 --port 8000
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from assistant.pipeline import responder

app = FastAPI(
    title='Asistente Sedes Electronicas',
    description='API local para el asistente de tramites administrativos (TFM UNIR).',
    version='1.0.0',
)

# CORS: la extension Chrome envia peticiones desde chrome-extension://<id>
# Solo se permite localhost para garantizar que ningun dato sale de la maquina.
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'],           # En produccion: limitar a chrome-extension://<id>
    allow_methods=['POST', 'GET'],
    allow_headers=['Content-Type'],
)


class Consulta(BaseModel):
    pregunta: str
    url: str
    campo: Optional[str] = None   # Nombre semantico del campo activo en el formulario


class RespuestaAsistente(BaseModel):
    respuesta: str
    pii_detected: bool
    pii_types: list
    chunks_usados: int
    pregunta_limpia: str


@app.get('/health')
def health():
    """Endpoint de comprobacion: permite que la extension verifique que el servidor esta activo."""
    return {'status': 'ok', 'modelo': 'gemma4:e2b', 'version': '1.0.0'}


@app.post('/consulta', response_model=RespuestaAsistente)
def consulta(body: Consulta):
    """
    Recibe una consulta del ciudadano y devuelve la respuesta del asistente.

    - **pregunta**: texto libre del usuario
    - **url**: URL completa de la sede electronica activa
    - **campo**: etiqueta semantica del campo del formulario con foco (opcional)
    """
    resultado = responder(body.pregunta, body.url, body.campo)
    return resultado
