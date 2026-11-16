#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — BOT TELEGRAM v5.1
# Painel Interativo C2 com Menu Persistente
# ============================================================

import os
import json
import urllib.request
from datetime import datetime
from pathlib import Path
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

# ============================================================
# CONFIGURAÇÃO
# ============================================================
BASE = Path.home() / "ARCTURUS_CLIMATIK"
CACHE_FILE = BASE / "cache" / "arcturus_alerta.json"
CIDADES_FILE = BASE / "fontes" / "municipios_sc_coords.json"
LOG_FILE = BASE / "logs" / "bot_acessos.log"
# --- Leitura segura de credenciais (.env) ---
import os
from pathlib import Path

def _load_env():
    """Carrega .env do diretorio do projeto (procura ate 6 niveis acima)."""
    p = Path(__file__).resolve().parent
    for _ in range(6):
        env_file = p / ".env"
        if env_file.exists():
            for line in env_file.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())
            return
        p = p.parent

_load_env()
# --- Fim do bloco .env ---

TOKEN_BOT = os.environ.get("TELEGRAM_TOKEN", "")

# ============================================================
# LOG
# ============================================================
def log(msg):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {msg}\n")
    print(f"[{ts}] {msg}")

# ============================================================
# DADOS
# ============================================================
def ler_cache():
    if not CACHE_FILE.exists():
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        log(f"Erro ao ler cache: {e}")
        return None

def carregar_cidades():
    if not CIDADES_FILE.exists():
        return []
    with open(CIDADES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def dividir_mensagem(texto, limite=4000):
    if len(texto) <= limite:
        return [texto]
    partes, atual = [], ""
    for linha in texto.split("\n"):
        if len(atual) + len(linha) + 1 > limite:
            partes.append(atual)
            atual = linha
        else:
            atual += ("\n" if atual else "") + linha
    if atual:
        partes.append(atual)
    return partes

def escapar_md(texto):
    """Escapa caracteres especiais do Markdown para Telegram."""
    if not texto:
        return ""
    chars = ['_', '*', '[', ']', '(', ')', '~', '`', '>', '#', '+', '-', '=', '|', '{', '}', '.', '!']
    for c in chars:
        texto = texto.replace(c, f"\\{c}")
    return texto

# ============================================================
# BUSCA
# ============================================================
def buscar_cidade_coords(nome):
    cidades = carregar_cidades()
    nome_lower = nome.lower()
    for c in cidades:
        if c["nome"].lower() == nome_lower:
            return c
    for c in cidades:
        if nome_lower in c["nome"].lower():
            return c
    return None

def buscar_no_cache(nome):
    cache = ler_cache()
    if not cache:
        return None
    nome_lower = nome.lower()
    for c in cache.get("cidades_tempestade", []):
        if nome_lower in c["cidade"].lower():
            return {"tipo": "tempestade", "dados": c}
    for c in cache.get("cidades_clima_anormal", []):
        if nome_lower in c["cidade"].lower():
            return {"tipo": "clima", "dados": c}
    return None

def consultar_openmeteo(lat, lon):
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}"
        f"&current=temperature_2m,relative_humidity_2m,"
        f"wind_speed_10m,precipitation,cape,lifted_index"
        f"&timezone=America/Sao_Paulo"
    )
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ARCTURUS/1.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            c = json.loads(r.read().decode("utf-8")).get("current", {})
            return {
                "temperatura": c.get("temperature_2m"),
                "umidade": c.get("relative_humidity_2m"),
                "vento": c.get("wind_speed_10m"),
                "precipitacao": c.get("precipitation"),
                "cape": c.get("cape"),
                "lifted_index": c.get("lifted_index"),
            }
    except Exception as e:
        log(f"Erro Open-Meteo: {e}")
        return None

# ============================================================
# MENU INTERATIVO
# ============================================================
def menu_principal():
    keyboard = [
        [InlineKeyboardButton("🚨 Tempestades Severas", callback_data='menu_tempestades')],
        [InlineKeyboardButton("⚠️ Anomalias Climáticas", callback_data='menu_anomalias')],
        [InlineKeyboardButton("🟢 Cidades Normais", callback_data='menu_normais')],
        [InlineKeyboardButton("📊 Status Geral", callback_data='menu_status')],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_voltar():
    keyboard = [[InlineKeyboardButton("🔙 Voltar ao Menu", callback_data='menu_inicio')]]
    return InlineKeyboardMarkup(keyboard)

def msg_inicial():
    return """🟣 *ARCTURUS CLIMATIK*
_Sistema de Alerta Antecipado — SC_

Selecione uma opção no painel abaixo.

🔍 Para consultar uma cidade, digite o nome dela diretamente.
_Ex: Criciúma, Blumenau, Florianópolis..._

🔬 Onde a dúvida vira investigação."""

# ============================================================
# HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"START de {user.first_name} ({user.id})")
    
    await update.message.reply_text(
        msg_inicial(),
        reply_markup=menu_principal(),
        parse_mode="Markdown"
    )

async def click_botao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    comando = query.data
    
    try:
        if comando == 'menu_inicio':
            await query.edit_message_text(
                msg_inicial(),
                reply_markup=menu_principal(),
                parse_mode="Markdown"
            )
            return
        
        elif comando == 'menu_status':
            cache = ler_cache()
            if not cache:
                await query.edit_message_text(
                    "⚠️ Cache indisponível.",
                    reply_markup=menu_voltar()
                )
                return
            resumo = cache.get("resumo", {})
            msg = f"""📊 *STATUS GERAL DE SC*

📅 Atualizado: {cache.get('ultima_atualizacao', '?')}
📍 Municípios monitorados: {cache.get('total_municipios', 0)}

🚨 *Status geral:* {cache.get('status_geral', '?')}

*Resumo:*
• 🟢 Normais: {resumo.get('normais', 0)}
• 🟡 Anomalias: {resumo.get('atencao_clima', 0)}
• ⛈️ Tempestades: {resumo.get('tempestades', 0)}

📡 Fonte: Open-Meteo + NASA POWER"""
            await query.edit_message_text(
                msg, reply_markup=menu_voltar(), parse_mode="Markdown"
            )
            return
        
        elif comando == 'menu_tempestades':
            cache = ler_cache()
            lista = cache.get("cidades_tempestade", []) if cache else []
            if not lista:
                await query.edit_message_text(
                    "✅ Nenhuma tempestade severa detectada.",
                    reply_markup=menu_voltar()
                )
                return
            msg = f"🚨 *TEMPESTADES SEVERAS ({len(lista)})*\n\n"
            for i, t in enumerate(lista, 1):
                cape = t.get('cape', 'N/D')
                li = t.get('lifted_index', 'N/D')
                msg += f"{i}. *{t['cidade']}*\n   CAPE: {cape} | LI: {li}\n"
            msg += f"\n📅 {cache.get('ultima_atualizacao', '?')}"
            
            # Truncar se muito longo
            if len(msg) > 3800:
                msg = msg[:3700] + "\n\n_...lista truncada_"
            
            await query.edit_message_text(
                msg, reply_markup=menu_voltar(), parse_mode="Markdown"
            )
            return
        
        elif comando == 'menu_anomalias':
            cache = ler_cache()
            lista = cache.get("cidades_clima_anormal", []) if cache else []
            if not lista:
                await query.edit_message_text(
                    "✅ Nenhuma anomalia climática detectada.",
                    reply_markup=menu_voltar()
                )
                return
            msg = f"⚠️ *ANOMALIAS CLIMÁTICAS ({len(lista)})*\n\n"
            for i, a in enumerate(lista, 1):
                temp = a.get('temperatura', '?')
                desvio = a.get('desvio_temp', 0)
                msg += f"{i}. *{a['cidade']}*\n   {temp}°C ({desvio:+.1f}°C)\n"
            msg += f"\n📅 {cache.get('ultima_atualizacao', '?')}"
            
            if len(msg) > 3800:
                msg = msg[:3700] + "\n\n_...lista truncada_"
            
            await query.edit_message_text(
                msg, reply_markup=menu_voltar(), parse_mode="Markdown"
            )
            return
        
        elif comando == 'menu_normais':
            cache = ler_cache()
            cidades = carregar_cidades()
            ids_alerta = set()
            if cache:
                ids_alerta.update(str(c.get("codigo_ibge", "")) for c in cache.get("cidades_tempestade", []))
                ids_alerta.update(str(c.get("codigo_ibge", "")) for c in cache.get("cidades_clima_anormal", []))
            
            normais = [c for c in cidades if str(c["codigo_ibge"]) not in ids_alerta]
            
            msg = f"🟢 *CIDADES SEM ALERTA ({len(normais)})*\n\n"
            for i, c in enumerate(normais, 1):
                msg += f"{i}. {c['nome']}\n"
            
            if len(msg) > 3800:
                msg = msg[:3700] + "\n\n_...lista truncada_"
            
            await query.edit_message_text(
                msg, reply_markup=menu_voltar(), parse_mode="Markdown"
            )
            return
    
    except Exception as e:
        log(f"Erro em click_botao: {e}")
        try:
            await query.edit_message_text(
                "⚠️ Erro ao processar. Tente novamente.",
                reply_markup=menu_voltar()
            )
        except:
            pass

# ============================================================
# BUSCA LIVRE (LUPA)
# ============================================================
async def busca_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    if nome.startswith('/') or len(nome) < 3:
        return
    
    user = update.effective_user
    log(f"Busca livre: '{nome}' de {user.first_name}")
    
    # 1. Tentar cache (tempestade ou anomalia)
    resultado = buscar_no_cache(nome)
    
    if resultado:
        dados = resultado["dados"]
        if resultado["tipo"] == "tempestade":
            msg = f"""🚨 *{dados['cidade']} — TEMPESTADE SEVERA*

*Status:* {dados.get('status_tempestade', '?')}
🌡️ Temperatura: {dados.get('temperatura')}°C
💧 Umidade: {dados.get('umidade')}%
🌧️ Chuva: {dados.get('chuva')} mm
🌬️ Vento: {dados.get('vento')} km/h
⚡ CAPE: {dados.get('cape', 'N/D')} J/kg
📉 Lifted Index: {dados.get('lifted_index', 'N/D')}

*⚠️ Alertas:*"""
            for al in dados.get("alertas_tempestade", []):
                msg += f"\n• {al}"
        else:
            msg = f"""⚠️ *{dados['cidade']} — ANOMALIA CLIMÁTICA*

*Status:* {dados.get('status_clima', '?')}
🌡️ Temperatura: {dados.get('temperatura')}°C
📊 Média climatológica: {dados.get('temp_media_clim')}°C
📉 Desvio: {dados.get('desvio_temp'):+.1f}°C
💧 Umidade: {dados.get('umidade')}%
🌧️ Chuva: {dados.get('chuva')} mm

*⚠️ Alertas:*"""
            for al in dados.get("alertas", []):
                msg += f"\n• {al}"
        
        await update.message.reply_text(
            msg,
            reply_markup=menu_voltar(),
            parse_mode="Markdown"
        )
        return
    
    # 2. Não está no cache → Open-Meteo em tempo real
    coords = buscar_cidade_coords(nome)
    if not coords:
        await update.message.reply_text(
            f"⚠️ Município *{escapar_md(nome)}* não encontrado na base de SC.",
            reply_markup=menu_voltar(),
            parse_mode="Markdown"
        )
        return
    
    dados = consultar_openmeteo(coords["lat"], coords["lon"])
    if not dados:
        await update.message.reply_text(
            f"⚠️ Não foi possível consultar {coords['nome']}.",
            reply_markup=menu_voltar()
        )
        return
    
    cape = dados.get("cape")
    if cape and cape >= 2500:
        status_temp = "🔴 ALERTA VERMELHO"
    elif cape and cape >= 1500:
        status_temp = "🟠 ALERTA LARANJA"
    elif cape and cape >= 1000:
        status_temp = "🟡 ATENÇÃO"
    else:
        status_temp = "🟢 SEM RISCO"
    
    msg = f"""🟣 *ARCTURUS — {coords['nome']}*

🌡️ *CONDIÇÕES ATUAIS*
• Temperatura: {dados['temperatura']}°C
• Umidade: {dados['umidade']}%
• Vento: {dados['vento']} km/h
• Chuva: {dados['precipitacao']} mm

⚡ *INSTABILIDADE ATMOSFÉRICA*
• CAPE: {cape if cape else 'N/D'} J/kg
• Lifted Index: {dados['lifted_index'] if dados['lifted_index'] else 'N/D'}
• Status: {status_temp}

📊 *INTERPRETAÇÃO*
A cidade está dentro da normalidade climatológica.
Nenhuma anomalia detectada para o período.

📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}
📡 Fonte: Open-Meteo em tempo real"""
    
    await update.message.reply_text(
        msg,
        reply_markup=menu_voltar(),
        parse_mode="Markdown"
    )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    log(f"❌ Erro: {context.error}")

# ============================================================
# MAIN
# ============================================================
def main():
    print("=" * 60)
    print("🟣 ARCTURUS CLIMATIK — BOT TELEGRAM v5.1")
    print("=" * 60)
    print(f"📡 Cache: {CACHE_FILE}")
    print(f"🔍 Cache existe: {CACHE_FILE.exists()}")
    print(f"📍 Cidades cadastradas: {len(carregar_cidades())}")
    print("=" * 60)
    
    log("Bot v5.1 iniciado")
    
    app = Application.builder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(click_botao))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, busca_livre))
    app.add_error_handler(error_handler)
    
    print("✅ Bot rodando. Aguardando comandos no Telegram...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
