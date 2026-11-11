"""Genera guion-cdmx-sindicato-metro-linea-a.json (piloto de escenas 3D, 11/11/2026).

La estación (andén, pared, lámparas, vías) se repite en varias escenas: por eso
este plan sale de código y el de Narvarte está escrito a mano.
"""

import json
import math
from pathlib import Path

PI = math.pi


def A(de, a, desde=0, hasta=1):
    return {"de": de, "a": a, "desde": desde, "hasta": hasta}


def estacion(largo=16):
    v = [{"objeto": "Suelo", "color": "#1A1C20", "posicion": [0, -0.62, 0]},
         {"objeto": "Anden", "largo": largo, "fondo": 3, "alto": 0.6},
         {"objeto": "Forma", "forma": "caja", "color": "#BFC5CC", "tamano": [largo, 3.2, 0.2], "posicion": [0, 1.5, -1.65]},
         {"objeto": "Forma", "forma": "caja", "color": "#2E7D4F", "tamano": [largo, 0.12, 0.02], "posicion": [0, 0.9, -1.54]},
         {"objeto": "Vias", "largo": 30, "escala": 1.6, "posicion": [0, -0.6, 2.3]}]
    for x in range(-6, 7, 3):
        v.append({"objeto": "Forma", "forma": "caja", "color": "#FFFFFF", "brillo": 1, "tamano": [1.8, 0.05, 0.18],
                  "posicion": [x, 2.7, 0]})
    return v


def vagon(pos, apagado=0, escala=1.5, rot=None):
    d = {"objeto": "Vagon", "largo": 4, "escala": escala, "posicion": pos, "apagado": apagado}
    if rot is not None:
        d["rotacion"] = [0, rot, 0]
    return d


def deposito():
    """17 trenes en 5 columnas; 6 se apagan (los que no andan) y les ponen un cono."""
    trenes, k = [], 0
    parados = {2, 5, 7, 10, 13, 16}
    for fila in range(4):
        for col in range(5):
            if k >= 17:
                break
            x, z = (col - 2) * 1.1, -fila * 3.0
            trenes.append(vagon([x, 0, z], A(0, 1, 0.3 + 0.03 * (k % 4), 0.45) if k in parados else 0, escala=0.6, rot=PI / 2))
            if k in parados:
                trenes.append({"objeto": "Modelo", "modelo": "calles/construction-cone", "alto": 0.2,
                               "posicion": [x + 0.35, 0, z + 1.4], "escala": A(0.001, 1, 0.42, 0.5)})
            k += 1
    return trenes


E = {}
E["p00"] = {
    "visual": estacion() + [{"objeto": "Multitud", "n": 18, "ancho": 5, "fondo": 2, "semilla": "p00"},
                            vagon(A([-12, -0.6, 2.3], [-0.5, -0.6, 2.3], 0, 0.7))],
    "camara": {"desde": {"pos": [1.2, 2.2, 9.0], "mira": [0, 0.5, 0]}, "hasta": {"pos": [0.6, 1.9, 8.0], "mira": [0, 0.5, 0]}},
    "etiquetas": [{"titulo": "11 trenes", "subtitulo": "para 226 mil pasajeros al día", "desde": 0.05, "hasta": 1}],
    "claves": ["sindicato"]}
E["p01"] = {
    "visual": estacion() + [
        {"objeto": "Personaje", "modelo": "personajes/character-female-b", "animacion": "idle", "giro": 0.5, "posicion": [0.2, 0, 1.0]},
        vagon(A([0.5, -0.6, 2.3], [14, -0.6, 2.3], 0.45, 0.9))],
    "camara": {"desde": {"pos": [-3.8, 1.4, 0.2], "mira": [0.6, 0.4, 1.2]}, "hasta": {"pos": [-3.0, 1.2, 0.4], "mira": [0.6, 0.45, 1.2]}},
    "etiquetas": [{"titulo": "Línea A", "subtitulo": "Iztapalapa, Ciudad de México", "desde": 0.04, "hasta": 0.5},
                  {"titulo": "¿Ya te dejó tirado?", "desde": 0.6, "hasta": 1}],
    "claves": ["tirado"]}
E["p02"] = {
    "visual": estacion() + [vagon(A([-6, -0.6, 2.3], [3, -0.6, 2.3]))],
    "camara": {"desde": {"pos": [2.0, -0.1, 5.6], "mira": [0, -0.3, 2.3]}, "hasta": {"pos": [1.5, -0.2, 5.1], "mira": [0, -0.25, 2.3]}},
    "etiquetas": [{"titulo": "1991", "subtitulo": "de Pantitlán a La Paz", "desde": 0.04, "hasta": 0.5},
                  {"titulo": "Rueda sobre acero", "subtitulo": "la única línea así", "desde": 0.55, "hasta": 1}],
    "claves": ["acero"]}
E["p03"] = {
    "visual": [{"objeto": "Suelo", "color": "#2B2E33"}] + deposito() + [
        {"objeto": "Personaje", "modelo": "personajes/character-worker", "animacion": "idle", "posicion": [-0.6, 0, 2.6]},
        {"objeto": "Personaje", "modelo": "personajes/character-worker", "animacion": "interact-right", "giro": -0.4,
         "posicion": [0.7, 0, 2.3]}],
    "camara": {"desde": {"pos": [0, 6.5, 7.5], "mira": [0, 0, -3.5]}, "hasta": {"pos": [0, 8.0, 6.5], "mira": [0, 0, -4.5]}},
    "etiquetas": [{"titulo": "11 de 17", "subtitulo": "trenes andando, dicen los trabajadores", "desde": 0.35, "hasta": 1}],
    "claves": ["once", "diecisiete"]}
E["p04"] = {
    "visual": [{"objeto": "Suelo", "color": "#1C1F26"},
               {"objeto": "Modelo", "modelo": "ciudad/building-skyscraper-a", "alto": 5.0, "posicion": [0, 0, -4]},
               {"objeto": "Modelo", "modelo": "ciudad/low-detail-building-b", "alto": 4.0, "posicion": [-2.8, 0, -5.5]},
               {"objeto": "Modelo", "modelo": "ciudad/low-detail-building-e", "alto": 3.4, "posicion": [2.8, 0, -5.5]},
               {"objeto": "Modelo", "modelo": "calles/light-square", "alto": 1.9, "posicion": [-1.1, 0, -1]},
               {"objeto": "Modelo", "modelo": "calles/light-square", "alto": 1.9, "posicion": [1.1, 0, -1]},
               {"objeto": "Personaje", "modelo": "personajes/character-worker", "animacion": "walk", "giro": PI,
                "posicion": A([0, 0, 2.8], [0, 0, -1.4], 0, 0.95)}],
    "camara": {"desde": {"pos": [0, 1.3, 6.2], "mira": [0, 1.5, -2]}, "hasta": {"pos": [0, 1.6, 5.2], "mira": [0, 2.0, -3]}},
    "evidencia": {"e": "e2", "desde": 0.42, "hasta": 0.96},
    "etiquetas": [{"titulo": "4 de noviembre", "subtitulo": "oficio a la Jefatura de Gobierno", "desde": 0.04, "hasta": 0.4}],
    "claves": ["oficio", "Brugada"]}
E["p05"] = {
    "visual": estacion() + [
        vagon([0.5, -0.6, 2.3], 0.75),
        {"objeto": "Modelo", "modelo": "calles/construction-barrier", "alto": 0.42, "giro": PI / 2, "posicion": [0.4, 0, 0.9]},
        {"objeto": "Modelo", "modelo": "calles/construction-cone", "alto": 0.22, "posicion": [0.4, 0, 1.3]},
        {"objeto": "Modelo", "modelo": "calles/construction-cone", "alto": 0.22, "posicion": [0.4, 0, 0.3]},
        {"objeto": "Personaje", "modelo": "personajes/character-worker", "animacion": "emote-no", "giro": -1.2, "posicion": [1.3, 0, 0.6]}],
    "camara": {"desde": {"pos": [-3.6, 1.5, 0.3], "mira": [0.5, 0.3, 1.2]}, "hasta": {"pos": [-2.8, 1.3, 0.5], "mira": [0.5, 0.3, 1.2]}},
    "etiquetas": [{"titulo": "Podría suspender", "subtitulo": "el servicio donde no haya seguridad", "desde": 0.04, "hasta": 0.5},
                  {"titulo": "Fernando Espino", "subtitulo": "dirigente del sindicato", "desde": 0.56, "hasta": 1}],
    "claves": ["suspender"]}
E["p06"] = {
    "visual": [{"objeto": "Suelo", "color": "#1A1C20"},
               {"objeto": "Forma", "forma": "caja", "color": "#7A8696", "tamano": [0.9, 0.41, 0.9], "posicion": [-0.7, 0.205, 0]},
               {"objeto": "Forma", "forma": "caja", "color": "#F26B1D", "brillo": 0.15,
                "tamano": A([0.9, 0.05, 0.9], [0.9, 2.8, 0.9], 0.42, 0.7), "posicion": A([0.7, 0.025, 0], [0.7, 1.4, 0], 0.42, 0.7)},
               {"objeto": "Multitud", "n": 2, "ancho": 0.6, "fondo": 0.5, "alto": 0.5, "semilla": "p06a", "posicion": [-0.7, 0.41, 0]},
               {"objeto": "Multitud", "n": 9, "ancho": 0.75, "fondo": 0.6, "alto": 0.5, "semilla": "p06b",
                "posicion": A([0.7, 0.05, 0], [0.7, 2.8, 0], 0.42, 0.7), "aparece": A(0.2, 1, 0.42, 0.75)}],
    "camara": {"desde": {"pos": [0, 1.6, 10.4], "mira": [0, 1.0, 0]}, "hasta": {"pos": [0, 1.7, 9.8], "mira": [0, 1.05, 0]}},
    "etiquetas": [{"titulo": "13 millones", "subtitulo": "en su primer año", "desde": 0.04, "hasta": 0.4},
                  {"titulo": "88 millones", "subtitulo": "en 2022 · El Universal", "desde": 0.45, "hasta": 0.8},
                  {"titulo": "Y menos trenes", "desde": 0.82, "hasta": 1}],
    "claves": ["ochenta", "millones"]}
E["p07"] = {
    "visual": estacion() + [{"objeto": "Multitud", "n": 34, "ancho": 8, "fondo": 2.4, "semilla": "p07"}],
    "camara": {"desde": {"pos": [0, 1.2, 6.8], "mira": [0, 0.6, 0]}, "hasta": {"pos": [0, 5.5, 6.5], "mira": [0, 0, -0.5]}, "entre": [0, 0.6]},
    "evidencia": {"e": "e1", "desde": 0.5, "hasta": 0.97},
    "etiquetas": [{"titulo": "226 mil", "subtitulo": "personas cada día", "desde": 0.04, "hasta": 0.46}],
    "claves": ["firma"]}
E["p08"] = {
    "visual": estacion() + [
        {"objeto": "Personaje", "modelo": "personajes/character-male-c", "animacion": "idle", "giro": 0.5, "posicion": [0.2, 0, 1.0]},
        vagon(A([0.5, -0.6, 2.3], [14, -0.6, 2.3], 0, 0.6))],
    "camara": {"desde": {"pos": [-3.0, 1.2, 0.4], "mira": [0.6, 0.45, 1.2]}, "hasta": {"pos": [-4.2, 1.7, 0.1], "mira": [0.6, 0.4, 1.2]}},
    "etiquetas": [{"titulo": "¿En qué línea?", "subtitulo": "te dejaron tirado", "desde": 0.1, "hasta": 1}]}

if __name__ == "__main__":
    salida = Path(__file__).with_name("guion-cdmx-sindicato-metro-linea-a.json")
    salida.write_text(json.dumps({"ambiente": "anden", "escenas": E}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(E)} escenas -> {salida}")
