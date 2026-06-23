from rag.ingestion import get_collection, ingest_from_graph

col = get_collection()

ids_existentes = col.get(
    where={'tramite': 'Borrador / Declaración de la Renta IRPF — AEAT'}
)['ids']
if ids_existentes:
    col.delete(ids=ids_existentes)
    print(f'Eliminados {len(ids_existentes)} chunks previos')

ingest_from_graph('data/graphs/aeat_renta_completo.json')

# Resumen total
total = col.count()
print(f'\nTotal chunks en ChromaDB: {total}')
