# Asistente inteligente para sedes electrónicas

TFM del Máster Universitario en Inteligencia Artificial — UNIR  

Septiembre 2026

## Descripción

Asistente conversacional basado en GraphRAG y LLM local (Gemma 3:4B via Ollama) que ayuda a ciudadanos mayores a realizar trámites administrativos en sedes electrónicas de la Administración Pública española. El sistema extrae información de las webs oficiales, construye un grafo de conocimiento y responde consultas en lenguaje sencillo, con reconocimiento y síntesis de voz y anonimización de datos personales.

## Trámites implementados

- Cita previa del SEPE
- Alta en el Programa de Turismo del IMSERSO
- Informe de vida laboral en Import@ss
- Borrador de la Renta en la AEAT
- Cita médica en Madrid Salud

## Tecnologías

- **LLM:** Gemma 3:4B (Ollama)
- **Embeddings:** `intfloat/multilingual-e5-small`
- **Base de datos vectorial:** ChromaDB
- **Grafo de conocimiento:** NetworkX
- **Scraping:** Playwright
- **Backend:** FastAPI
- **Interfaz:** Extensión de navegador Chromium

## Estructura del proyecto

```
tfm-asistente-sedes/
├── scraper/        # Extracción de contenido de sedes electrónicas
├── graph/          # Construcción del grafo de conocimiento
├── rag/            # Indexación y recuperación semántica
├── privacy/        # Anonimización de datos personales (regex + NER)
├── assistant/      # Pipeline de respuesta y cliente LLM
├── extension/      # Extensión de navegador
└── data/           # Grafos y base de datos vectorial
```
