from rag.ingestion import get_collection, ingest_from_graph

col = get_collection()

ids_existentes = col.get(
    where={'tramite': 'Cita Sanitaria Atención Primaria — Comunidad de Madrid'}
)['ids']
if ids_existentes:
    col.delete(ids=ids_existentes)
    print(f'Eliminados {len(ids_existentes)} chunks previos')

ingest_from_graph('data/graphs/madrid_salud_completo.json')
