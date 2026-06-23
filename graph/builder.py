# -*- coding: utf-8 -*-
import json
import os
import sys
import networkx as nx
from typing import Optional
from enum import Enum

# Permite ejecutar este script directamente (python graph/builder.py) o
# importarlo desde otro paquete, asegurando que 'assistant' sea importable.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class PageEstado(str, Enum):
    PENDIENTE     = "pendiente"
    EN_CURSO      = "en_curso"
    BLOQUEADA     = "bloqueada"
    COMPLETADA    = "completada"
    CONFIRMACION  = "confirmacion"
    NO_EXPLORADA  = "no_explorada"


# Campos cuyo nombre delata que el dato solicitado ES un documento de
# identidad (o exige tenerlo a mano). Heuristica simple y conservadora:
# solo se usa para generar la arista REQUIERE, no para inventar relaciones
# que no esten respaldadas por el propio texto scrapeado.
PALABRAS_DOCUMENTO_IDENTIDAD = ('NIF', 'NIE', 'DNI')


def _documento_requerido(label: str) -> Optional[str]:
    upper = (label or '').upper()
    if any(palabra in upper for palabra in PALABRAS_DOCUMENTO_IDENTIDAD):
        return 'Documento de identidad en vigor (DNI o NIE)'
    return None


def build_graph(json_path: str, generar_resumenes: bool = True) -> nx.DiGraph:
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    G = nx.DiGraph()

    # Nodo raiz del tramite
    G.add_node('tramite_0', type='tramite',
        titulo=data['tramite'],
        url_inicio=data['url_inicio'],
        total_pasos=data['total_pasos']
    )

    pasos = data['pasos']
    nodos_pagina = []

    # Importacion diferida: solo se necesita ollama si se generan resumenes,
    # y asi el resto del modulo sigue siendo importable sin Ollama corriendo.
    resumir_pagina = None
    if generar_resumenes:
        try:
            from assistant.llm_client import resumir_pagina as _resumir_pagina
            resumir_pagina = _resumir_pagina
        except Exception as e:
            print(f'Aviso: no se pudo cargar el cliente LLM ({e}). Se omiten los llm_resumen.')

    for paso in pasos:
        page_id = f"pagina_{paso['step_num']}"
        nodos_pagina.append(page_id)

        # Clasificar estado
        if paso['step_num'] <= data.get('pasos_scrapeados', 4):
            estado = PageEstado.COMPLETADA
        else:
            estado = PageEstado.PENDIENTE

        es_confirmacion = paso['step_num'] == data['total_pasos']

        campos_requeridos = [
            n['html_id'] for n in paso['nodes']
            if n['node_type'] == 'input' and n.get('required')
        ]
        errores_activos = [
            n['label'][:60] for n in paso['nodes']
            if n['node_type'] == 'error'
        ]
        titulo = paso.get('title', f"Paso {paso['step_num']}")

        # Resumen en lenguaje natural de la pantalla (offline, vía LLM local).
        llm_resumen = ''
        if resumir_pagina is not None:
            elementos = [
                n['label'][:60] for n in paso['nodes']
                if n['node_type'] in ('button', 'input') and n.get('label')
            ]
            try:
                llm_resumen = resumir_pagina(titulo, elementos, errores_activos)
            except Exception as e:
                print(f'Aviso: no se pudo generar llm_resumen para {page_id} ({e}).')

        # Nodo pagina
        G.add_node(page_id,
            type='pagina',
            titulo=titulo,
            url=paso.get('url', ''),
            step_num=paso['step_num'],
            step_total=data['total_pasos'],
            estado=estado.value,
            es_confirmacion=es_confirmacion,
            breadcrumb=paso.get('breadcrumb', []),
            campos_requeridos=campos_requeridos,
            errores_activos=errores_activos,
            llm_resumen=llm_resumen,
        )

        # Arista TIENE_PASO desde tramite raiz
        G.add_edge('tramite_0', page_id, type='TIENE_PASO')

        # Nodos hijo de la pagina (boton, input, help_text, error)
        error_ids = []
        boton_ids = []
        aclara_idx = 0

        for i, node in enumerate(paso['nodes']):
            node_id = f"{page_id}_{node['node_type']}_{i}"
            label = node['label'][:100]
            help_text = node.get('help_text', '') or ''

            G.add_node(node_id,
                type=node['node_type'],
                label=label,
                html_id=node.get('html_id'),
                input_type=node.get('input_type'),
                required=node.get('required', False),
                help_text=help_text
            )
            # Arista CONTIENE
            G.add_edge(page_id, node_id, type='CONTIENE')

            if node['node_type'] == 'error':
                error_ids.append(node_id)
            if node['node_type'] == 'button':
                boton_ids.append((node_id, label))

            # ACLARA: el texto de ayuda de un input/select se modela como un
            # nodo TextoAyuda propio, enlazado al componente que clarifica,
            # en vez de quedar aplanado como simple atributo.
            if node['node_type'] == 'input' and help_text:
                ayuda_id = f"{page_id}_aclara_{aclara_idx}"
                aclara_idx += 1
                G.add_node(ayuda_id, type='help_text', label=help_text[:200])
                G.add_edge(ayuda_id, node_id, type='ACLARA')

            # REQUIERE: campos que piden un documento de identidad quedan
            # enlazados a un nodo TextoAyuda que describe la documentacion
            # necesaria (no se introduce un tipo de nodo nuevo: la memoria
            # define exactamente siete tipos, y TextoAyuda ya cubre este caso).
            documento = _documento_requerido(label)
            if node['node_type'] == 'input' and documento:
                doc_id = f"{page_id}_requiere_{i}"
                G.add_node(doc_id, type='help_text', label=documento)
                G.add_edge(node_id, doc_id, type='REQUIERE')

        # BLOQUEA: un mensaje de error activo inhabilita el boton de avance
        # (se excluye 'Volver', que no es la accion que el error bloquea).
        for error_id in error_ids:
            for boton_id, boton_label in boton_ids:
                if boton_label.strip().lower() == 'volver':
                    continue
                G.add_edge(error_id, boton_id, type='BLOQUEA')

        # Aristas PRECEDE entre paginas consecutivas
        if len(nodos_pagina) > 1:
            anterior = nodos_pagina[-2]
            G.add_edge(anterior, page_id, type='PRECEDE')

        # Arista especial para bifurcacion en paso 3
        if paso['step_num'] == 3:
            G.nodes[page_id]['es_bifurcacion'] = True
            G.nodes[page_id]['opciones'] = ['SOLO SEPE', 'AMBOS']

            # LLEVA_A: cada boton de la bifurcacion apunta a su pagina de
            # destino. La rama "SOLO SEPE" es la que se scrapeo (lleva al
            # paso 4); la rama "AMBOS" no se exploro, así que se enlaza a un
            # nodo Pagina marcado explícitamente como no explorado, en vez
            # de inventar contenido que no se llegó a scrapear.
            stub_id = f"{page_id}_ambos_no_explorada"
            G.add_node(stub_id,
                type='pagina',
                titulo='Rama "AMBOS" (no explorada)',
                estado=PageEstado.NO_EXPLORADA.value,
                step_num=None,
                es_confirmacion=False,
            )
            for boton_id, boton_label in boton_ids:
                etiqueta = boton_label.strip().upper()
                if etiqueta == 'SOLO SEPE':
                    # El destino real (pagina_4) aún no existe en este punto
                    # del bucle; se resuelve en una segunda pasada más abajo.
                    G.nodes[boton_id]['_lleva_a_siguiente_paso'] = True
                elif etiqueta == 'AMBOS':
                    G.add_edge(boton_id, stub_id, type='LLEVA_A')

    # Segunda pasada: resolver LLEVA_A de "SOLO SEPE" -> pagina siguiente,
    # una vez que todas las paginas ya existen en el grafo.
    for node_id, attrs in list(G.nodes(data=True)):
        if attrs.get('_lleva_a_siguiente_paso'):
            pagina_origen = node_id.split('_button_')[0]
            step_num = G.nodes[pagina_origen].get('step_num')
            destino = f"pagina_{step_num + 1}" if step_num is not None else None
            if destino and destino in G.nodes:
                G.add_edge(node_id, destino, type='LLEVA_A')
            del G.nodes[node_id]['_lleva_a_siguiente_paso']

    return G


def save_graph(G: nx.DiGraph, output_path: str):
    data = nx.node_link_data(G, edges="edges")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f'Grafo guardado en {output_path}')


def print_summary(G: nx.DiGraph):
    print(f'\n=== RESUMEN DEL GRAFO ===')
    print(f'Nodos totales: {G.number_of_nodes()}')
    print(f'Aristas totales: {G.number_of_edges()}')

    tipos = {}
    for _, data in G.nodes(data=True):
        t = data.get('type', 'desconocido')
        tipos[t] = tipos.get(t, 0) + 1
    print(f'\nNodos por tipo:')
    for t, c in tipos.items():
        print(f'  {t}: {c}')

    aristas = {}
    for _, _, data in G.edges(data=True):
        t = data.get('type', 'desconocido')
        aristas[t] = aristas.get(t, 0) + 1
    print(f'\nAristas por tipo:')
    for t, c in aristas.items():
        print(f'  {t}: {c}')

    print(f'\nSecuencia de paginas:')
    paginas = [(n, d) for n, d in G.nodes(data=True) if d.get('type') == 'pagina']
    paginas.sort(key=lambda x: (x[1].get('step_num') is None, x[1].get('step_num', 0)))
    for nid, d in paginas:
        estado = d.get('estado', '')
        titulo = d.get('titulo', '')
        errores = d.get('errores_activos', [])
        campos = d.get('campos_requeridos', [])
        paso_str = d.get('step_num', '-')
        print(f'  Paso {paso_str}: {titulo} [{estado}]')
        if campos:
            print(f'    campos requeridos: {campos}')
        if errores:
            print(f'    errores: {errores}')
        if d.get('llm_resumen'):
            print(f'    resumen LLM: {d["llm_resumen"]}')

    print(f'\nContexto LLM - Paso 2:')
    if 'pagina_2' in G.nodes:
        d = G.nodes['pagina_2']
        print(f'  Pagina: {d["titulo"]}')
        print(f'  Estado: {d["estado"]}')
        hijos = list(G.successors('pagina_2'))
        for h in hijos:
            hd = G.nodes[h]
            print(f'  [{hd["type"]}] {hd.get("label","")[:60]}')


if __name__ == '__main__':
    os.makedirs('data/graphs', exist_ok=True)

    print('Construyendo grafo desde JSON...')
    G = build_graph('data/graphs/sepe_completo.json')

    save_graph(G, 'data/graphs/sepe_grafo.json')
    print_summary(G)
