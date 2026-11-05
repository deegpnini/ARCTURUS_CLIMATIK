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



---
## Atualização: Defesa Civil de SC (04/11/2026)

A Defesa Civil de SC (`monitoramento.defesacivil.sc.gov.br`) usa a API da Qualle Control (`tile-service.quallecontrol.com.br`), que retorna **TileJSON (Mapbox Vector Tiles)** em vez de dados tabulares (JSON/CSV). A extração dos dados exigiria decodificar tiles `.pbf`/`.mvt` com protobuf, o que é **frágil e complexo**. 

**Decisão:** A Defesa Civil de SC é **fonte visual** (consulta manual pelo operador). Não é integrada automaticamente ao ARCTURUS.

**Alternativa:** A ERAB (P0) continua sendo a fonte primária de cota (tempo real). A ANA (P1) fica como histórico/validação.
