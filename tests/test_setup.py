import sys

def test_ollama():
    import ollama
    r = ollama.chat(model='gemma4:e2b', messages=[{
        'role': 'user',
        'content': 'Di solo: OK en espanol'
    }])
    text = r['message']['content']
    print(f'\n✅ Gemma 4 E2B: {text[:80]}')
    assert len(text) > 0

def test_chromadb():
    import chromadb
    client = chromadb.EphemeralClient()
    col = client.create_collection('test')
    col.add(documents=['tramite de prueba'], ids=['1'])
    r = col.query(query_texts=['tramite'], n_results=1)
    doc = r['documents'][0][0]
    print(f'\n✅ ChromaDB: {doc}')
    assert doc == 'tramite de prueba'

def test_embeddings():
    from sentence_transformers import SentenceTransformer
    m = SentenceTransformer('intfloat/multilingual-e5-small')
    v = m.encode(['query: padron municipal'])
    print(f'\n✅ Embeddings: dimension {v.shape[1]}')
    assert v.shape[1] > 0

def test_playwright():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = p.chromium.launch(headless=True)
        page = b.new_page()
        page.goto('https://google.com', timeout=15000)
        title = page.title()
        b.close()
    print(f'\n✅ Playwright: {title}')
    assert len(title) > 0

def test_spacy():
    import spacy
    nlp = spacy.load('es_core_news_sm')
    doc = nlp('Juan Garcia tiene el DNI 12345678Z')
    ents = [e.text for e in doc.ents if e.label_ == 'PER']
    print(f'\n✅ spaCy NER: {ents}')
    assert len(ents) > 0

if __name__ == '__main__':
    print('=== Test de configuracion TFM ===')
    tests = [test_chromadb, test_embeddings, test_playwright, test_spacy, test_ollama]
    errores = []
    for t in tests:
        try:
            t()
        except Exception as e:
            errores.append(f'❌ {t.__name__}: {e}')
    if errores:
        print('\n=== ERRORES ===')
        [print(e) for e in errores]
        sys.exit(1)
    else:
        print('\n=== ✅ Entorno listo. Semana 1 completada ===')
