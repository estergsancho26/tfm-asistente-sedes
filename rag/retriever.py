# -*- coding: utf-8 -*-
from sentence_transformers import SentenceTransformer
import chromadb
from typing import Optional

EMBED_MODEL = 'intfloat/multilingual-e5-small'
DB_PATH     = './data/chroma_db'
COLLECTION  = 'tramites_es'
_model      = None

def get_model():
    global _model
    if _model is None:
        _model = SentenceTransformer(EMBED_MODEL)
    return _model

def retrieve(
    pregunta: str,
    url_base: Optional[str] = None,
    paso_num: Optional[int] = None,
    k: int = 3,
    score_min: float = 0.75
) -> list:
    model  = get_model()
    client = chromadb.PersistentClient(path=DB_PATH)
    col    = client.get_or_create_collection(COLLECTION)

    vec = model.encode(
        [f'query: {pregunta}'],
        normalize_embeddings=True
    ).tolist()[0]

    # Sin filtro where — filtramos en Python despues
    results = col.query(
        query_embeddings=[vec],
        n_results=min(k * 3, 19),
        include=['documents', 'distances', 'metadatas']
    )

    chunks = []
    for doc, dist, meta in zip(
        results['documents'][0],
        results['distances'][0],
        results['metadatas'][0]
    ):
        score = 1 - dist
        if score < score_min:
            continue
        if url_base and meta.get('url_base') != url_base:
            continue
        if paso_num and meta.get('paso_num') != paso_num:
            continue
        chunks.append({
            'texto':       doc,
            'score':       round(score, 3),
            'paso_num':    meta.get('paso_num'),
            'node_type':   meta.get('node_type'),
            'elemento_id': meta.get('elemento_id'),
        })
        if len(chunks) >= k:
            break

    return chunks
