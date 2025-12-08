import yfinance as yf
import numpy as np
import pandas as pd
import requests
import os

# --- CONFIGURACIÓN ---
# Tickers de Futuros:
# NQ=F -> Nasdaq 100 Futures
# ES=F -> S&P 500 Futures
TICKERS = ["NQ=F", "ES=F"] 
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Días a proyectar (Solo mañana = 1)
DAYS_AHEAD = 1
N_SIMS = 10000

def send_discord_embed(data_list):
    """Envía un Embed profesional a Discord con los datos calculados."""
    if not DISCORD_WEBHOOK_URL:
        print("❌ Error: No se encontró la URL del Webhook (Variable de entorno no definida).")
        return

    embeds = []
    
    for item in data_list:
        # Definir color: Verde si la proyección media es alcista, Rojo si es bajista
        color = 5763719 # Verde
        if item['expected'] < item['last_price']:
            color = 15548997 # Rojo

        embed = {
            "title": f"📊 Proyección: {item['ticker']}",
            "description": f"Percentiles institucionales para el **{item['date']}**.",
            "color": color,
            "fields": [
                {
                    "name": "Precio Cierre Hoy",
                    "value": f"**{item['last_price']:.2f}**",
                    "inline": True
                },
                {
                    "name": "Precio Esperado (Mean)",
                    "value": f"{item['expected']:.2f}",
                    "inline": True
                },
                {
                    "name": "Volatilidad Anual",
                    "value": f"{item['volatility']:.2f}%",
                    "inline": True
                },
                {
                    "name": "📉 Soporte (P1 - P5)",
                    "value": f"P1: {item['p1']}\nP5: {item['p5']}",
                    "inline": True
                },
                {
                    "name": "🎯 Rango Medio (P50)",
                    "value": f"**{item['p50']}**",
                    "inline": True
                },
                {
                    "name": "📈 Resistencia (P95 - P99)",
                    "value": f"P95: {item['p95']}\nP99: {item['p99']}",
                    "inline": True
                }
            ],
            "footer": {
                "text": "Quant Engine | Monte Carlo Simulation | Confianza: 95%"
            }
        }
        embeds.append(embed)

    payload = {
        "username": "Quant Engine Bot",
        "avatar_url": "https://i.imgur.com/4M34hi2.png", 
        "embeds": embeds
    }

    try:
        response = requests.post(DISCORD_WEBHOOK_URL, json=payload)
        response.raise_for_status()
        print("✅ Datos enviados a Discord correctamente.")
    except Exception as e:
        print(f"❌ Error enviando a Discord: {e}")

def run_simulation():
    results_to_send = []

    print("🔄 Iniciando cálculos...")
    
    for ticker in TICKERS:
        try:
            print(f"--- Procesando {ticker} ---")
            # 1. Obtener datos
            # auto_adjust=True ayuda a limpiar splits y dividendos
            df = yf.download(ticker, period="1y", interval="1d", progress=False, auto_adjust=True)
            
            if df.empty:
                print(f"⚠️ Sin datos para {ticker}")
                continue

            # Limpieza robusta de la estructura de datos de yfinance
            # A veces devuelve MultiIndex o DataFrames anidados
            try:
                if 'Close' in df.columns:
                    data = df['Close']
                else:
                    # Intento de fallback si la columna no se llama exactamente 'Close'
                    data = df.iloc[:, 0]
                
                # Si sigue siendo un DataFrame (p.ej. columnas multi-nivel), tomamos la primera serie
                if isinstance(data, pd.DataFrame):
                    data = data.iloc[:, 0]
            except Exception as e:
                print(f"❌ Error extrayendo columna Close: {e}")
                continue
            
            # Eliminar NaNs
            data = data.dropna()

            # 2. Cálculos Base (CORRECCIÓN IMPORTANTE AQUÍ)
            returns = data.pct_change().dropna()
            
            # Convertimos explícitamente a float para evitar errores de formato en Pandas Series
            mean_r = float(returns.mean())
            std_r = float(returns.std(ddof=0))
            last_price = float(data.iloc[-1])
            
            # 3. Simulación Monte Carlo
            # Generamos retornos aleatorios (Normal Distribution)
            rand_returns = np.random.normal(mean_r, std_r, size=(N_SIMS, DAYS_AHEAD))
            
            # Caminos de precio: Precio_Ultimo * (1 + retorno)
            price_paths = last_price * (1 + rand_returns) 
            
            # 4. Resultados del Día +1
            # Tomamos la columna 0 (el primer día proyectado)
            simulated_prices = price_paths[:, 0]
            
            # Percentiles
            p1 = float(np.percentile(simulated_prices, 1))
            p5 = float(np.percentile(simulated_prices, 5))
            p50 = float(np.percentile(simulated_prices, 50))
            p95 = float(np.percentile(simulated_prices, 95))
            p99 = float(np.percentile(simulated_prices, 99))
            
            expected_price = float(np.mean(simulated_prices))
            vol_annual = std_r * np.sqrt(252) * 100
            
            # Fecha objetivo (Mañana)
            target_date = pd.Timestamp.now() + pd.Timedelta(days=1)
            
            results_to_send.append({
                "ticker": ticker,
                "date": target_date.strftime('%Y-%m-%d'),
                "last_price": last_price,
                "expected": expected_price,
                "volatility": vol_annual, # Ahora esto es un float puro
                "p1": f"{p1:.2f}",
                "p5": f"{p5:.2f}",
                "p50": f"{p50:.2f}",
                "p95": f"{p95:.2f}",
                "p99": f"{p99:.2f}"
            })
            
        except Exception as e:
            print(f"❌ Error procesando {ticker}: {e}")
            # Imprimir detalle del error para debugging
            import traceback
            traceback.print_exc()
            continue

    # Enviar reporte si hay datos
    if results_to_send:
        send_discord_embed(results_to_send)
    else:
        print("⚠️ No se generaron datos para enviar.")

if __name__ == "__main__":
    run_simulation()
