#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Varredura de vento para os 295 municípios de SC usando Open-Meteo.
Salva CSV com rajadas atuais e ranking dos mais ventosos.
"""

import requests
import pandas as pd
import time
from pathlib import Path

BASE = Path(__file__).resolve().parent
OUT_CSV = BASE / "resultados" / "vento_sc_295.csv"

# Lista dos 295 municípios de SC (fonte: IBGE/Atlascidade)
# Para evitar digitar 295 nomes, usamos a API de geocoding da Open-Meteo
# para buscar as coordenadas de cada município.

MUNICIPIOS_SC = [
    "Abdon Batista", "Abelardo Luz", "Agrolândia", "Agronômica", "Água Doce",
    "Águas de Chapecó", "Águas Frias", "Águas Mornas", "Alfredo Wagner",
    "Alto Bela Vista", "Anchieta", "Angelina", "Anita Garibaldi", "Anitápolis",
    "Antônio Carlos", "Apiúna", "Arabutã", "Araquari", "Araranguá", "Armazém",
    "Arroio Trinta", "Arvoredo", "Ascurra", "Atalanta", "Aurora",
    "Balneário Arroio do Silva", "Balneário Barra do Sul", "Balneário Camboriú",
    "Balneário Gaivota", "Balneário Piçarras", "Balneário Rincão", "Bandeirante",
    "Barra Bonita", "Barra Velha", "Bela Vista do Toldo", "Belmonte",
    "Benedito Novo", "Biguaçu", "Blumenau", "Bocaina do Sul", "Bom Jardim da Serra",
    "Bom Jesus", "Bom Jesus do Oeste", "Bom Retiro", "Bombinhas", "Botuverá",
    "Braço do Norte", "Braço do Trombudo", "Brunópolis", "Brusque", "Caçador",
    "Caibi", "Calmon", "Camboriú", "Campo Alegre", "Campo Belo do Sul",
    "Campo Erê", "Campos Novos", "Canelinha", "Canoinhas", "Capão Alto",
    "Capinzal", "Capivari de Baixo", "Catanduvas", "Caxambu do Sul", "Celso Ramos",
    "Cerro Negro", "Chapadão do Lageado", "Chapecó", "Cocal do Sul", "Concórdia",
    "Cordilheira Alta", "Coronel Freitas", "Coronel Martins", "Correia Pinto",
    "Corupá", "Criciúma", "Cunha Porã", "Cunhataí", "Curitibanos", "Descanso",
    "Dionísio Cerqueira", "Dona Emma", "Doutor Pedrinho", "Entre Rios", "Ermo",
    "Erval Velho", "Faxinal dos Guedes", "Flor do Sertão", "Florianópolis",
    "Formosa do Sul", "Forquilhinha", "Fraiburgo", "Frei Rogério", "Galvão",
    "Garopaba", "Garuva", "Gaspar", "Governador Celso Ramos", "Grão-Pará",
    "Gravatal", "Guabiruba", "Guaraciaba", "Guaramirim", "Guarujá do Sul",
    "Guatambú", "Herval d'Oeste", "Ibiam", "Ibicaré", "Ibirama", "Içara",
    "Ilhota", "Imaruí", "Imbituba", "Imbuia", "Indaial", "Iomerê", "Ipira",
    "Iporã do Oeste", "Ipuaçu", "Ipumirim", "Iraceminha", "Irani", "Irati",
    "Irineópolis", "Itá", "Itaiópolis", "Itajaí", "Itapema", "Itapiranga",
    "Itapoá", "Ituporanga", "Jaborá", "Jacinto Machado", "Jaguaruna",
    "Jaraguá do Sul", "Jardinópolis", "Joaçaba", "Joinville", "José Boiteux",
    "Jupiá", "Lacerdópolis", "Lages", "Laguna", "Lajeado Grande", "Laurentino",
    "Lauro Müller", "Lebon Régis", "Leoberto Leal", "Lindóia do Sul", "Lontras",
    "Luiz Alves", "Luzerna", "Macieira", "Mafra", "Major Gercino", "Major Vieira",
    "Maracajá", "Maravilha", "Marema", "Massaranduba", "Matos Costa", "Meleiro",
    "Mirim Doce", "Modelo", "Mondaí", "Monte Carlo", "Monte Castelo",
    "Morro da Fumaça", "Morro Grande", "Navegantes", "Nova Erechim",
    "Nova Itaberaba", "Nova Trento", "Nova Veneza", "Novo Horizonte",
    "Orleans", "Otacílio Costa", "Ouro", "Ouro Verde", "Paial", "Painel",
    "Palhoça", "Palma Sola", "Palmeira", "Palmitos", "Papanduva", "Paraíso",
    "Passo de Torres", "Passos Maia", "Paulo Lopes", "Pedras Grandes", "Penha",
    "Peritiba", "Pescaria Brava", "Petrolândia", "Pinhalzinho", "Pinheiro Preto",
    "Piratuba", "Planalto Alegre", "Pomerode", "Ponte Alta", "Ponte Alta do Norte",
    "Ponte Serrada", "Porto Belo", "Porto União", "Pouso Redondo", "Praia Grande",
    "Presidente Castello Branco", "Presidente Getúlio", "Presidente Nereu",
    "Princesa", "Quilombo", "Rancho Queimado", "Rio das Antas", "Rio do Campo",
    "Rio do Oeste", "Rio do Sul", "Rio dos Cedros", "Rio Fortuna",
    "Rio Negrinho", "Rio Rufino", "Riqueza", "Rodeio", "Romelândia", "Salete",
    "Saltinho", "Salto Veloso", "Sangão", "Santa Cecília", "Santa Helena",
    "Santa Rosa de Lima", "Santa Rosa do Sul", "Santa Terezinha",
    "Santa Terezinha do Progresso", "Santiago do Sul", "Santo Amaro da Imperatriz",
    "São Bento do Sul", "São Bernardino", "São Bonifácio", "São Carlos",
    "São Cristóvão do Sul", "São Domingos", "São Francisco do Sul",
    "São João Batista", "São João do Itaperiú", "São João do Oeste",
    "São João do Sul", "São Joaquim", "São José", "São José do Cedro",
    "São José do Cerrito", "São Lourenço do Oeste", "São Ludgero", "São Martinho",
    "São Miguel da Boa Vista", "São Miguel do Oeste", "São Pedro de Alcântara",
    "Saudades", "Schroeder", "Seara", "Serra Alta", "Siderópolis", "Sombrio",
    "Sul Brasil", "Taió", "Tangará", "Tigrinhos", "Tijucas", "Timbé do Sul",
    "Timbó", "Timbó Grande", "Três Barras", "Treviso", "Treze de Maio",
    "Treze Tílias", "Trombudo Central", "Tubarão", "Tunápolis", "Turvo",
    "União do Oeste", "Urubici", "Urupema", "Urussanga", "Vargeão", "Vargem",
    "Vargem Bonita", "Vidal Ramos", "Videira", "Vitor Meireles", "Witmarsum",
    "Xanxerê", "Xavantina", "Xaxim", "Zortéa"
]

def geocodificar(nome):
    """Busca lat/lon de um município via Open-Meteo Geocoding."""
    url = "https://geocoding-api.open-meteo.com/v1/search"
    params = {"name": nome, "count": 1, "language": "pt", "format": "json", "countryCode": "BR"}
    try:
        resp = requests.get(url, params=params, timeout=15)
        if resp.status_code == 200:
            dados = resp.json()
            if dados.get("results"):
                r = dados["results"][0]
                # Filtra para garantir que é SC (admin1)
                if r.get("admin1") == "Santa Catarina":
                    return r["latitude"], r["longitude"]
    except Exception:
        pass
    return None, None

def main():
    print(f"Total de municípios: {len(MUNICIPIOS_SC)}")
    print("Geocodificando (pode levar alguns minutos)...")
    
    coords = []
    for i, nome in enumerate(MUNICIPIOS_SC):
        if (i + 1) % 20 == 0:
            print(f"  {i+1}/{len(MUNICIPIOS_SC)}...")
        lat, lon = geocodificar(nome)
        if lat and lon:
            coords.append({"municipio": nome, "lat": lat, "lon": lon})
        time.sleep(0.2)  # respeita o rate limit
    
    print(f"Coordenadas obtidas: {len(coords)}")
    
    if not coords:
        print("[ERRO] Nenhuma coordenada obtida.")
        return
    
    # Consulta em lotes de 50 (Open-Meteo aceita múltiplos pontos)
    resultados = []
    lote = 50
    for i in range(0, len(coords), lote):
        chunk = coords[i:i+lote]
        lats = ",".join(str(c["lat"]) for c in chunk)
        lons = ",".join(str(c["lon"]) for c in chunk)
        
        url = "https://api.open-meteo.com/v1/forecast"
        params = {
            "latitude": lats,
            "longitude": lons,
            "current": "wind_speed_10m,wind_gusts_10m",
            "timezone": "America/Sao_Paulo",
        }
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 200:
                dados = resp.json()
                if isinstance(dados, list):
                    for j, d in enumerate(dados):
                        if j < len(chunk):
                            curr = d.get("current", {})
                            resultados.append({
                                "municipio": chunk[j]["municipio"],
                                "vento_kmh": curr.get("wind_speed_10m"),
                                "rajada_kmh": curr.get("wind_gusts_10m"),
                            })
        except Exception as e:
            print(f"  Erro no lote {i//lote + 1}: {e}")
        time.sleep(0.5)
    
    df = pd.DataFrame(resultados)
    if df.empty:
        print("[ERRO] Sem dados de vento.")
        return
    
    df = df.sort_values("rajada_kmh", ascending=False)
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(OUT_CSV, index=False)
    
    print(f"\n[OK] CSV salvo: {OUT_CSV} ({len(df)} municípios)")
    print("\n=== TOP 15 MUNICÍPIOS MAIS VENTOSOS (Rajada) ===")
    print(df.head(15).to_string(index=False))

if __name__ == "__main__":
    main()
