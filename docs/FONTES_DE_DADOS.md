# Fontes de Dados do ARCTURUS CLIMATIK

**Última atualização:** 04/11/2026

## Tabela de Fontes

| Fonte | Status | Tipo de Dado | Uso no ARCTURUS |
|-------|--------|--------------|-----------------|
| **ERAB (Tubarão Saneamento)** | ✅ Operacional | Cota (nível do rio) | P0 (fonte primária, tempo real) |
| **Open-Meteo (Archive/Forecast)** | ✅ Operacional | Chuva (bacia) | P0 (fonte primária de chuva) |
| **ANA SOAP (Telemetria1WS)** | ⚠️ Parcial | Cota histórica | P2 (fallback histórico) |
| **ANA HidroWebService** | ⚠️ Em validação | Cota histórica | P2 (fallback futuro) |
| **Epagri/Ciram** | 📧 Contato aberto | Chuva, meteorologia | Calibração futura |
| **AGR (Tubarão)** | 🔍 Investigação | Cota, chuva (regional) | Futuro (sem API pública) |
| **Amurel Conectada** | ❌ Visual (SPA) | Cota, chuva | Manual (sem API pública) |
| **Cache local** | ✅ Operacional | Última cota válida | P2 (se ERAB/ANA falharem) |

## Arquitetura de Fallback


