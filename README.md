# ARCTURUS CLIMATIK

**Plataforma de observação, alerta e aprendizado contínuo da Bacia do Rio Tubarão (SC).**

O ARCTURUS não é um modelo. É uma plataforma de monitoramento hidrológico que combina:
- **Camada 1 (física):** alerta em tempo real baseado em Vz/Az (regras físicas).
- **Camada 2 (científica):** modelo LightGBM em modo sombra (aprende sem alertar).
- **Camada 3 (territorial):** Atlas de Impacto (edificações, escolas, UBS).

**Princípio:** Evidência Primeiro. Modelos podem falhar. Evidências permanecem.

---

## Arquitetura


---
## Descoberta: Lag Chuva-Rio na Bacia do Tubarão (08/11/2026)

Medimos o lag (tempo entre o pico da chuva na cabeceira e o pico da cota em Tubarão) para 5 eventos:

| Evento | Pico da Chuva | Lag (h) |
|--------|---------------|---------|
| 27/10 11:30 | 26/10 13:00 | 33.7 |
| 30/10 16:45 | 29/10 21:00 | 31.0 |
| 03/11 17:45 | 03/11 13:00 | 16.0 |
| **04/11 08:30** | **04/11 07:00** | **13.5** |
| 07/11 21:30 | 07/11 12:00 | 16.0 |

**Conclusão:** A chuva da cabeceira (Orleans, Lauro Müller, Braço do Norte) leva ~13-16h para fazer o rio atingir o pico em Tubarão. O modelo v10 (que usa o lag de 15h) está fisicamente correto. O v8 (que não usa o lag) está errado.

**Próximo passo:** Acumular mais eventos (o El Niño está vindo) para refinar o lag e validar o modelo.
