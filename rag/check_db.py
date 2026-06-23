# -*- coding: utf-8 -*-
from rag.ingestion import get_collection

col = get_collection()
result = col.get(include=['metadatas'])
urls = set(m['url_base'] for m in result['metadatas'])
print('URLs en ChromaDB:')
for u in urls:
    print(f'  {repr(u)}')
print(f'Total chunks: {len(result["metadatas"])}')
