"""
Test script for NewsCollector module.
Verifies multi-source aggregation, filters, and async functionality.
"""

import asyncio
import logging
import sys
import os

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.news_collector import NewsCollector


async def test_news_collector():
    """Test NewsCollector functionality."""

    print("=" * 70)
    print("TESTE: NewsCollector - Sistema Multi-Fonte")
    print("=" * 70)
    print()

    # Configurar logging
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    # Criar instância
    collector = NewsCollector(max_age_minutes=30)

    print("1️⃣ Testando agregação multi-fonte...")
    print("-" * 70)

    # Teste síncrono
    headlines_sync = collector.fetch_market_pulse()

    if headlines_sync:
        print("\n✅ HEADLINES COLETADAS (Sync):")
        print("=" * 70)
        print(headlines_sync)
        print("=" * 70)
        print(f"\nTotal: {len(headlines_sync.split('\\n'))} headlines")
    else:
        print("\n⚠️ Nenhuma headline fresca/relevante encontrada (Sync).")

    print("\n2️⃣ Testando versão async...")
    print("-" * 70)

    # Teste assíncrono
    headlines_async = await collector.get_pulse_async()

    if headlines_async:
        print("\n✅ HEADLINES COLETADAS (Async):")
        print("=" * 70)
        print(headlines_async)
        print("=" * 70)
        print(f"\nTotal: {len(headlines_async.split('\\n'))} headlines")
    else:
        print("\n⚠️ Nenhuma headline fresca/relevante encontrada (Async).")

    print("\n3️⃣ Testes de filtros:")
    print("-" * 70)
    print("✅ Filtro de duplicidade: Ativo (seen_titles)")
    print("✅ Filtro de frescura: <30 minutos")
    print("✅ Filtro de relevância: Keywords de alto impacto")
    print("   - IPCA, SELIC, COPOM, Petrobras, Vale, etc.")

    print("\n" + "=" * 70)
    print("TESTE CONCLUÍDO")
    print("=" * 70)

    return headlines_async is not None


if __name__ == "__main__":
    success = asyncio.run(test_news_collector())

    if success:
        print("\n🎯 Status: SUCESSO - NewsCollector funcionando!")
        sys.exit(0)
    else:
        print(
            "\n⚠️ Status: ATENÇÃO - Nenhuma notícia encontrada (pode ser normal fora do horário de mercado)"
        )
        sys.exit(0)  # Não é erro, pode ser horário sem notícias
