# -*- coding: utf-8 -*-
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from privacy.anonymizer import safe_payload
from rag.retriever import retrieve
from assistant.llm_client import ask

SEPE_URL = 'https://citaprevia-sede.sepe.gob.es/citapreviasepe/?origen=sepe&codidioma=es'

def responder(user_message: str, url_base: str, node_label: str = None) -> dict:
    # 1. Anonimizar
    payload = safe_payload(user_message, url_base, node_label)

    # 2. Recuperar chunks RAG
    chunks = retrieve(payload['question'], url_base=url_base, k=3)
    context = '\n---\n'.join([c['texto'] for c in chunks]) if chunks else 'Sin contexto disponible'

    # 3. Generar respuesta con LLM
    respuesta = ask(context, payload['question'], node_label)

    return {
        'respuesta':    respuesta,
        'pii_detected': payload['pii_detected'],
        'pii_types':    payload['pii_types'],
        'chunks_usados': len(chunks),
        'pregunta_limpia': payload['question'],
    }

if __name__ == '__main__':
    print('=== Test pipeline completo ===\n')

    casos = [
        {
            'mensaje':    'Mi DNI es 12345678Z, que tengo que poner en el campo de NIF',
            'node_label': 'NIF/NIE(*)'
        },
        {
            'mensaje':    'No entiendo que es el subtramite, para que sirve',
            'node_label': 'Subtramite(*)'
        },
        {
            'mensaje':    'Que canal debo elegir si quiero ir en persona a la oficina',
            'node_label': 'Canal(*)'
        },
    ]

    for caso in casos:
        print(f'Usuario: {caso["mensaje"]}')
        print(f'Campo activo: {caso["node_label"]}')
        resultado = responder(caso['mensaje'], SEPE_URL, caso['node_label'])
        print(f'PII detectada: {resultado["pii_detected"]} {resultado["pii_types"]}')
        print(f'Pregunta limpia: {resultado["pregunta_limpia"]}')
        print(f'Chunks RAG: {resultado["chunks_usados"]}')
        print(f'Respuesta: {resultado["respuesta"]}')
        print('-' * 60)
