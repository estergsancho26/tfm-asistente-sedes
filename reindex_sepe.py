from rag.ingestion import get_collection, ingest_from_graph

col = get_collection()
ids = col.get(where={'tramite': 'Cita Previa SEPE'})['ids']
if ids:
    col.delete(ids=ids)
    print(f'Eliminados {len(ids)} chunks SEPE')

ingest_from_graph('data/graphs/sepe_completo.json')
