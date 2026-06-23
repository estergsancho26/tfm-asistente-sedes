# -*- coding: utf-8 -*-
import re
from dataclasses import dataclass

@dataclass
class AnonymizationResult:
    safe_text: str
    detected: list
    was_modified: bool

PATTERNS = {
    'dni_nie':  r'\b[0-9]{8}[A-Za-z]\b|\b[XYZxyz][0-9]{7}[A-Za-z]\b',
    'nss':      r'\b[0-9]{2}[/ -]?[0-9]{8}[/ -]?[0-9]{2}\b',
    'iban':     r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{4}[0-9]{7}([A-Z0-9]?){0,16}\b',
    'telefono': r'\b(?:\+34|0034)?[6789][0-9]{8}\b',
    'email':    r'\b[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}\b',
    'fecha_nac':r'\b(0?[1-9]|[12][0-9]|3[01])[/\-\.](0?[1-9]|1[0-2])[/\-\.]([12][0-9]{3})\b',
}

REPLACEMENTS = {
    'dni_nie':  '[DNI/NIE]',
    'nss':      '[NUM-SEG-SOCIAL]',
    'iban':     '[IBAN]',
    'telefono': '[TELEFONO]',
    'email':    '[EMAIL]',
    'fecha_nac':'[FECHA-NAC]',
}

def anonymize(text: str) -> AnonymizationResult:
    result   = text
    detected = []
    modified = False

    for entity, pattern in PATTERNS.items():
        matches = re.findall(pattern, result, re.IGNORECASE)
        if matches:
            detected.append(f'{entity}:{len(matches)}')
            result = re.sub(pattern, REPLACEMENTS[entity], result, flags=re.IGNORECASE)
            modified = True

    return AnonymizationResult(safe_text=result, detected=detected, was_modified=modified)

def safe_payload(user_msg: str, url_base: str, node_label: str = None) -> dict:
    anon = anonymize(user_msg)
    question = anon.safe_text.strip() or 'Como relleno este campo'
    return {
        'question':     question,
        'url_base':     url_base,
        'node_label':   node_label,
        'pii_detected': anon.was_modified,
        'pii_types':    anon.detected,
    }

if __name__ == '__main__':
    casos = [
        'Mi DNI es 12345678Z y no se que poner',
        'Mi telefono es 612345678 y no encuentro donde poner mis datos',
        'Mi email es juan@ejemplo.com y mi IBAN es ES9121000418450200051332',
        'Naci el 15/03/1958 y mi NSS es 28 12345678 32',
        'No entiendo que significa tramite asociado',
    ]

    print('=== Test anonimizador ===\n')
    for caso in casos:
        r = anonymize(caso)
        print(f'ANTES:   {caso}')
        print(f'DESPUES: {r.safe_text}')
        print(f'Detectado: {r.detected}')
        print()
