from rag.ingestion import get_collection, ingest_from_graph

col = get_collection()

# Limpiar chunks anteriores si los hubiera
ids_existentes = col.get(where={'tramite': 'Programa de Turismo del IMSERSO (Alta)'})['ids']
if ids_existentes:
    col.delete(ids=ids_existentes)
    print(f'Eliminados {len(ids_existentes)} chunks IMSERSO previos')

ingest_from_graph('data/graphs/imserso_completo.json')
