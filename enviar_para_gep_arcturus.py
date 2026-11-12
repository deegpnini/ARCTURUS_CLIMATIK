import os
from fastapi import HTTPException

from fastapi import FastAPI
from fastapi.responses import Response
from lxml import etree
import uvicorn

app = FastAPI()

KML_NS = "http://www.opengis.net/kml/2.2"
NSMAP = {None: KML_NS}

ESTACOES = [
    {"nome": "ANA 84580000 (Rio do Pouso)", "lat": -28.3200, "lon": -49.1000, "desc": "Estacao ancora. Descontinuada (Contrato ANA/IGAM)."},
    {"nome": "SDC Tubarao Guarda", "lat": -28.4500, "lon": -48.9800, "desc": "Substituta oficial da ANA. Defesa Civil SC."},
    {"nome": "SDC Lauro Muller", "lat": -28.3900, "lon": -49.4000, "desc": "Substituta de Orleans."},
    {"nome": "SDC Alfredo Wagner", "lat": -27.7000, "lon": -49.3300, "desc": "Substituta de Saltinho."},
    {"nome": "Estacao Sao Ludgero (Foto)", "lat": -28.322500, "lon": -49.172800, "desc": "Ponte Rosiney da Silva Walter. Sensor com postes curvos."}
]

def gerar_kml():
    kml = etree.Element("kml", nsmap=NSMAP)
    doc = etree.SubElement(kml, "Document")
    nome_doc = etree.SubElement(doc, "name")
    nome_doc.text = "ARCTURUS CLIMATIK"

    for est in ESTACOES:
        pm = etree.SubElement(doc, "Placemark")
        nome = etree.SubElement(pm, "name")
        nome.text = est["nome"]
        desc = etree.SubElement(pm, "description")
        desc.text = est["desc"]
        ponto = etree.SubElement(pm, "Point")
        coord = etree.SubElement(ponto, "coordinates")
        coord.text = f"{est['lon']},{est['lat']},0"

    return etree.tostring(kml, pretty_print=True, xml_declaration=True, encoding="UTF-8")

# Token de acesso (defina uma variável de ambiente ou use um valor fixo)
TOKEN_ACESSO = os.getenv("TRINITY_TOKEN")

def verificar_token(token: str):
    if token != TOKEN_ACESSO:
        raise HTTPException(status_code=401, detail="Token inválido")

@app.get("/loader.kml")
def loader(token: str = ""):
    verificar_token(token)
    return Response(content=gerar_kml(), media_type="application/vnd.google-earth.kml+xml")

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8088)
