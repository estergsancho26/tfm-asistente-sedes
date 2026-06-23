# -*- coding: utf-8 -*-
import json
import chromadb
from sentence_transformers import SentenceTransformer
from typing import Optional

EMBED_MODEL = 'intfloat/multilingual-e5-small'
COLLECTION  = 'tramites_es'
DB_PATH     = './data/chroma_db'

def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(
        name=COLLECTION,
        metadata={'hnsw:space': 'cosine'}
    )

def ingest_from_graph(json_path: str):
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    model = SentenceTransformer(EMBED_MODEL)
    col   = get_collection()

    chunks    = []
    metadatas = []
    ids       = []

    tramite = data['tramite']

    for paso in data['pasos']:
        step_num = paso['step_num']
        url_base = paso.get('url', data['url_inicio'])
        titulo   = paso.get('title', f'Paso {step_num}')

        for i, node in enumerate(paso['nodes']):
            texto = node.get('label', '').strip()
            if not texto or len(texto) < 5:
                continue

            # Enriquecer con contexto del paso
            chunk = (
                f"Tramite: {tramite}. "
                f"Paso {step_num}: {titulo}. "
                f"Elemento [{node['node_type']}]: {texto}"
            )
            if node.get('help_text'):
                chunk += f". Ayuda: {node['help_text']}"

            chunks.append(chunk)
            metadatas.append({
                'tramite':    tramite,
                'url_base':   url_base,
                'paso_num':   step_num,
                'node_type':  node['node_type'],
                'elemento_id': node.get('html_id') or f'node_{i}',
                'tipo_fuente': 'scraping_sede'
            })
            ids.append(f"{tramite}_{step_num}_{i}".replace(' ', '_'))

    if not chunks:
        print('No hay chunks para indexar')
        return

    print(f'Generando embeddings para {len(chunks)} chunks...')
    embeddings = model.encode(
        [f'passage: {c}' for c in chunks],
        normalize_embeddings=True,
        show_progress_bar=True
    ).tolist()

    col.add(documents=chunks, embeddings=embeddings,
            metadatas=metadatas, ids=ids)
    print(f'Indexados {len(chunks)} chunks en ChromaDB')
    return len(chunks)

def test_query(pregunta: str, url_base: Optional[str] = None):
    model = SentenceTransformer(EMBED_MODEL)
    col   = get_collection()

    vec = model.encode(
        [f'query: {pregunta}'],
        normalize_embeddings=True
    ).tolist()[0]

    filtro = {'url_base': {'': url_base}} if url_base else None

    results = col.query(
        query_embeddings=[vec],
        n_results=3,
        where=filtro,
        include=['documents', 'distances', 'metadatas']
    )

    print(f'\nConsulta: "{pregunta}"')
    print(f'Resultados:')
    for doc, dist, meta in zip(
        results['documents'][0],
        results['distances'][0],
        results['metadatas'][0]
    ):
        print(f'  score={1-dist:.2f} paso={meta["paso_num"]} [{meta["node_type"]}]')
        print(f'  {doc[:100]}')

if __name__ == '__main__':
    import os
    os.makedirs('data/chroma_db', exist_ok=True)

    print('Indexando tramite SEPE...')
    n = ingest_from_graph('data/graphs/sepe_completo.json')

    print('\nProbando busqueda semantica:')
    test_query('que documento de identidad necesito')
    test_query('como seleccionar el tipo de tramite')
    test_query('donde elijo la fecha de la cita')
