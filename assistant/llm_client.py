# -*- coding: utf-8 -*-
import ollama
from typing import Optional

MODEL = 'gemma4:e2b'

SYSTEM_PROMPT = """Eres un asistente que ayuda a personas mayores a realizar
tramites en la administracion publica espanola. Usa un lenguaje muy claro y
sencillo, sin tecnicismos. Responde siempre en 2-3 frases cortas. Si el
usuario necesita un documento, dile exactamente cual es. No inventes
informacion que no este en el contexto."""

def ask(context: str, question: str, node_label: Optional[str] = None) -> str:
    node_ctx = f'El usuario esta en el campo: {node_label}.' if node_label else ''
    prompt = f"""{node_ctx}

Informacion oficial sobre este tramite:
{context}

Pregunta del usuario: {question}

Responde en 2-3 frases cortas y claras."""

    response = ollama.chat(
        model=MODEL,
        messages=[
            {'role': 'system', 'content': SYSTEM_PROMPT},
            {'role': 'user',   'content': prompt}
        ]
    )
    return response['message']['content']


RESUMEN_SYSTEM_PROMPT = """Resumes pantallas de un formulario administrativo
para uso interno de otro sistema, no para el usuario final. No uses
tecnicismos ni introducciones. Responde unicamente con el resumen, en 1 o 2
frases muy cortas, sin comillas."""

def resumir_pagina(titulo: str, elementos: Optional[list] = None, errores: Optional[list] = None) -> str:
    """Genera una sintesis de 1-2 frases sobre el objetivo operativo de una
    pantalla del tramite, a partir de su titulo y los elementos detectados
    por el scraper. Usada por graph/builder.py para poblar el atributo
    llm_resumen de cada nodo Pagina (seccion 5.3.1 de la memoria)."""
    elementos_txt = ', '.join(elementos) if elementos else 'sin campos relevantes'
    errores_txt = f' Errores activos: {", ".join(errores)}.' if errores else ''
    prompt = (
        f'Pantalla del tramite: "{titulo}". '
        f'Campos y elementos: {elementos_txt}.{errores_txt} '
        f'Resume en 1-2 frases que debe hacer el usuario en esta pantalla.'
    )
    response = ollama.chat(
        model=MODEL,
        messages=[
            {'role': 'system', 'content': RESUMEN_SYSTEM_PROMPT},
            {'role': 'user',   'content': prompt}
        ]
    )
    return response['message']['content'].strip()
