#!/usr/bin/env python3
# ============================================================
# ARCTURUS CLIMATIK — BOT TELEGRAM v6.0
# Com módulos climático + hidrológico + sísmico
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

BASE = Path.home() / "ARCTURUS_CLIMATIK"
CACHE_CLIMA = BASE / "cache" / "arcturus_alerta.json"
CACHE_HIDRO = BASE / "cache" / "arcturus_hidro.json"
CACHE_SISMICO = BASE / "cache" / "arcturus_sismico.json"
CIDADES_FILE = BASE / "fontes" / "municipios_sc_coords.json"
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

def ler_json(path):
    if not path.exists():
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None

def carregar_cidades():
    if not CIDADES_FILE.exists():
        return []
    with open(CIDADES_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

# ============================================================
# MENU PRINCIPAL
# ============================================================
def menu_principal():
    keyboard = [
        [InlineKeyboardButton("🌡️ CLIMA", callback_data='menu_clima'),
         InlineKeyboardButton("📊 STATUS", callback_data='menu_status')],
        [InlineKeyboardButton("🌊 RIOS / HIDROLOGIA", callback_data='menu_hidro')],
        [InlineKeyboardButton("🌍 SISMOS EM SC", callback_data='menu_sismico')],
        [InlineKeyboardButton("📡 SOBRE O ARCTURUS", callback_data='menu_sobre')],
    ]
    return InlineKeyboardMarkup(keyboard)

def menu_voltar():
    return InlineKeyboardMarkup([[
        InlineKeyboardButton("🔙 Menu Principal", callback_data='menu_inicio')
    ]])

def msg_inicial():
    return """🟣 *ARCTURUS CLIMATIK*
_Sistema de Alerta Antecipado — SC_

Selecione um módulo no painel:

🌡️ *Clima:* tempestades, anomalias, cidades
🌊 *Rios:* monitoramento hidrológico
🌍 *Sismos:* atividade sísmica em SC

🔍 Para consultar uma cidade, digite o nome dela diretamente.

🔬 Onde a dúvida vira investigação."""

# ============================================================
# HANDLERS
# ============================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        msg_inicial(),
        reply_markup=menu_principal(),
        parse_mode="Markdown"
    )

async def click_botao(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    cmd = query.data
    
    try:
        # ===== VOLTAR =====
        if cmd == 'menu_inicio':
            await query.edit_message_text(
                msg_inicial(),
                reply_markup=menu_principal(),
                parse_mode="Markdown"
            )
            return
        
        # ===== CLIMA =====
        elif cmd == 'menu_clima':
            keyboard = [
                [InlineKeyboardButton("🚨 Tempestades Severas", callback_data='clima_temp')],
                [InlineKeyboardButton("⚠️ Anomalias Climáticas", callback_data='clima_anom')],
                [InlineKeyboardButton("🟢 Cidades Normais", callback_data='clima_normais')],
                [InlineKeyboardButton("🔙 Menu Principal", callback_data='menu_inicio')],
            ]
            await query.edit_message_text(
                "🌡️ *MÓDULO CLIMA*\n\nEscolha uma opção:",
                reply_markup=InlineKeyboardMarkup(keyboard),
                parse_mode="Markdown"
            )
            return
        
        elif cmd == 'clima_temp':
            cache = ler_json(CACHE_CLIMA)
            lista = cache.get("cidades_tempestade", []) if cache else []
            if not lista:
                await query.edit_message_text(
                    "✅ Nenhuma tempestade severa no momento.",
                    reply_markup=menu_voltar()
                )
                return
            msg = f"🚨 *TEMPESTADES SEVERAS ({len(lista)})*\n\n"
            for i, t in enumerate(lista[:30], 1):
                msg += f"{i}. *{t['cidade']}* — CAPE: {t.get('cape','N/D')} | LI: {t.get('lifted_index','N/D')}\n"
            if len(lista) > 30:
                msg += f"\n_...e mais {len(lista) - 30}_"
            await query.edit_message_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
            return
        
        elif cmd == 'clima_anom':
            cache = ler_json(CACHE_CLIMA)
            lista = cache.get("cidades_clima_anormal", []) if cache else []
            if not lista:
                await query.edit_message_text(
                    "✅ Nenhuma anomalia climática no momento.",
                    reply_markup=menu_voltar()
                )
                return
            msg = f"⚠️ *ANOMALIAS CLIMÁTICAS ({len(lista)})*\n\n"
            for i, a in enumerate(lista[:30], 1):
                desvio = a.get('desvio_temp', 0)
                msg += f"{i}. *{a['cidade']}* — {a.get('temperatura')}°C ({desvio:+.1f}°C)\n"
            if len(lista) > 30:
                msg += f"\n_...e mais {len(lista) - 30}_"
            await query.edit_message_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
            return
        
        elif cmd == 'clima_normais':
            cache = ler_json(CACHE_CLIMA)
            cidades = carregar_cidades()
            ids_alerta = set()
            if cache:
                ids_alerta.update(str(c.get("codigo_ibge","")) for c in cache.get("cidades_tempestade", []))
                ids_alerta.update(str(c.get("codigo_ibge","")) for c in cache.get("cidades_clima_anormal", []))
            normais = [c for c in cidades if str(c["codigo_ibge"]) not in ids_alerta]
            msg = f"🟢 *CIDADES NORMAIS ({len(normais)})*\n\n"
            for i, c in enumerate(normais[:40], 1):
                msg += f"{i}. {c['nome']}\n"
            if len(normais) > 40:
                msg += f"\n_...e mais {len(normais) - 40}_"
            await query.edit_message_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
            return
        
        # ===== HIDROLOGIA =====
        elif cmd == 'menu_hidro':
            cache = ler_json(CACHE_HIDRO)
            if not cache:
                await query.edit_message_text(
                    "⚠️ Cache hidrológico indisponível.",
                    reply_markup=menu_voltar()
                )
                return
            
            dc = cache.get("defesa_civil", {})
            ep = cache.get("epagri", {})
            
            msg = f"""🌊 *MÓDULO HIDROLÓGICO*

📅 Atualizado: {cache.get('ultima_atualizacao', '?')}

*Fontes monitoradas:*

🛡️ *Defesa Civil SC*
Status: {dc.get('status', '?')}
Alertas: {len(dc.get('alertas', []))}

🌡️ *Epagri/Ciram*
Status: {ep.get('status', '?')}

📝 *Nota:*
{cache.get('nota', 'Sem nota')}

*Aguardando token ANA para cotas exatas.*"""
            await query.edit_message_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
            return
        
        # ===== SISMOS =====
        elif cmd == 'menu_sismico':
            cache = ler_json(CACHE_SISMICO)
            if not cache:
                await query.edit_message_text(
                    "⚠️ Cache sísmico indisponível.",
                    reply_markup=menu_voltar()
                )
                return
            
            eventos = cache.get("eventos", [])
            msg = f"""🌍 *MÓDULO SÍSMICO*

📅 Atualizado: {cache.get('ultima_atualizacao', '?')}
📊 Período: {cache.get('periodo', '?')}
📡 Fonte: USGS

*Eventos detectados:* {len(eventos)}
*Status:* {cache.get('status', '?')}
"""
            if eventos:
                msg += "\n*Últimos eventos:*\n"
                for e in eventos[:5]:
                    msg += f"• M{e['magnitude']} em {e['data']}\n"
                msg += f"\n📍 {eventos[0]['localizacao']}"
            else:
                msg += "\n✅ Nenhum evento detectado nos últimos 12 meses.\nSC é região tectonicamente estável."
            
            await query.edit_message_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
            return
        
        # ===== STATUS =====
        elif cmd == 'menu_status':
            clima = ler_json(CACHE_CLIMA)
            hidro = ler_json(CACHE_HIDRO)
            sismico = ler_json(CACHE_SISMICO)
            
            msg = "📊 *STATUS GERAL DO ARCTURUS*\n\n"
            
            if clima:
                resumo = clima.get("resumo", {})
                msg += f"""🌡️ *CLIMA*
📅 {clima.get('ultima_atualizacao', '?')}
• Tempestades: {resumo.get('tempestades', 0)}
• Anomalias: {resumo.get('atencao_clima', 0)}
• Normais: {resumo.get('normais', 0)}

"""
            
            if hidro:
                msg += f"""🌊 *HIDROLOGIA*
📅 {hidro.get('ultima_atualizacao', '?')}
• Status: monitoramento ativo

"""
            
            if sismico:
                msg += f"""🌍 *SÍSMICO*
📅 {sismico.get('ultima_atualizacao', '?')}
• Eventos: {sismico.get('total_eventos', 0)}
• Status: {sismico.get('status', '?')}
"""
            
            await query.edit_message_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
            return
        
        # ===== SOBRE =====
        elif cmd == 'menu_sobre':
            msg = """📡 *SOBRE O ARCTURUS*

🟣 *Sistema de Alerta Antecipado de SC*

*Missão:*
Prever o caos antes que ele toque o solo e salvar vidas.

*Módulos:*
🌡️ Clima (CAPE, Lifted Index)
🌊 Hidrologia (rios, cotas)
🌍 Sísmico (USGS)

*Fontes:*
• Open-Meteo
• NASA POWER
• USGS
• Defesa Civil SC
• Epagri/Ciram

*Projeto:*
• 100% open source
• Roda em celular Android (Termux)
• Custo operacional: R$ 0,00

🔬 _Onde a dúvida vira investigação._"""
            await query.edit_message_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
            return
    
    except Exception as e:
        print(f"❌ Erro: {e}")
        try:
            await query.edit_message_text(
                "⚠️ Erro ao processar. Tente novamente.",
                reply_markup=menu_voltar()
            )
        except:
            pass

# ============================================================
# BUSCA LIVRE
# ============================================================
async def busca_livre(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nome = update.message.text.strip()
    if nome.startswith('/') or len(nome) < 3:
        return
    
    # Buscar no cache de clima
    cache = ler_json(CACHE_CLIMA)
    nome_lower = nome.lower()
    
    if cache:
        for c in cache.get("cidades_tempestade", []):
            if nome_lower in c["cidade"].lower():
                msg = f"🚨 *{c['cidade']} — TEMPESTADE*\n\n"
                msg += f"CAPE: {c.get('cape','?')} J/kg\n"
                msg += f"Lifted Index: {c.get('lifted_index','?')}\n"
                msg += f"Status: {c.get('status_tempestade','?')}\n"
                await update.message.reply_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
                return
        
        for c in cache.get("cidades_clima_anormal", []):
            if nome_lower in c["cidade"].lower():
                msg = f"⚠️ *{c['cidade']} — ANOMALIA*\n\n"
                msg += f"Temperatura: {c.get('temperatura')}°C\n"
                msg += f"Desvio: {c.get('desvio_temp',0):+.1f}°C\n"
                msg += f"Status: {c.get('status_clima','?')}\n"
                await update.message.reply_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")
                return
    
    # Buscar cidade nas coordenadas
    cidades = carregar_cidades()
    coords = None
    for c in cidades:
        if c["nome"].lower() == nome_lower:
            coords = c
            break
    if not coords:
        for c in cidades:
            if nome_lower in c["nome"].lower():
                coords = c
                break
    
    if not coords:
        await update.message.reply_text(
            f"⚠️ Cidade *{nome}* não encontrada.",
            reply_markup=menu_voltar(),
            parse_mode="Markdown"
        )
        return
    
    # Consultar Open-Meteo
    url = f"https://api.open-meteo.com/v1/forecast?latitude={coords['lat']}&longitude={coords['lon']}&current=temperature_2m,relative_humidity_2m,wind_speed_10m,precipitation,cape,lifted_index&timezone=America/Sao_Paulo"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ARCTURUS/6.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            data = json.loads(r.read().decode("utf-8")).get("current", {})
    except Exception:
        await update.message.reply_text("⚠️ Falha ao consultar dados.", reply_markup=menu_voltar())
        return
    
    msg = f"""🟣 *ARCTURUS — {coords['nome']}*

🌡️ *CONDIÇÕES ATUAIS*
• Temperatura: {data.get('temperature_2m')}°C
• Umidade: {data.get('relative_humidity_2m')}%
• Vento: {data.get('wind_speed_10m')} km/h
• Chuva: {data.get('precipitation')} mm

⚡ *INSTABILIDADE*
• CAPE: {data.get('cape')} J/kg
• Lifted Index: {data.get('lifted_index')}

📅 {datetime.now().strftime('%d/%m/%Y %H:%M')}
📡 Open-Meteo"""
    await update.message.reply_text(msg, reply_markup=menu_voltar(), parse_mode="Markdown")

def main():
    print("=" * 60)
    print("🟣 ARCTURUS CLIMATIK — BOT v6.0")
    print("=" * 60)
    app = Application.builder().token(TOKEN_BOT).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CallbackQueryHandler(click_botao))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, busca_livre))
    print("✅ Bot rodando...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
