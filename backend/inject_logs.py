import requests
import time


def inject_test_logs():
    base_url = "http://localhost:8000"
    print("Injetando logs de teste para validar dinamismo...")

    # Vamos usar os endpoints de toggle que chamam add_operational_log
    endpoints = [
        ("/config/filters/news?enabled=true", "Filtro de Notícias ATIVADO"),
        ("/config/filters/news?enabled=false", "Filtro de Notícias DESATIVADO"),
        ("/config/autonomous?enabled=true", "Modo Autônomo: ATIVO"),
        ("/config/autonomous?enabled=false", "Modo Autônomo: INATIVO"),
    ]

    for url, description in endpoints:
        print(f"Chamando: {description}...")
        try:
            response = requests.post(f"{base_url}{url}")
            if response.status_code == 200:
                print(f"Sucesso: {response.json()}")
            else:
                print(f"Erro: {response.status_code}")
        except Exception as e:
            print(f"Falha na requisição: {e}")
        time.sleep(2)  # Espera para ver o log no outro script


if __name__ == "__main__":
    inject_test_logs()
