import yfinance as yf
import numpy as np
import pandas as pd
import requests
import os
import sys

# --- CONFIGURACIÓN ---
# Tickers de Futuros en Yahoo Finance:
# ES=F -> S&P 500 Futures
# NQ=F -> Nasdaq 100 Futures
TICKERS = ["NQ=F", "ES=F"] 
DISCORD_WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")

# Días a proyectar (Solo mañana)
DAYS_AHEAD = 1
N_SIMS = 10000

def send_discord_embed(data_list):
    """Envía un Embed profesional a Discord con los datos calculados."""
    if not DISCORD_WEBHOOK_URL:
        print("❌ Error: No se encontró la URL del Webhook.")
        return

    embeds = []
    
    for item in data_list:
        # Definir color basado en si la proyección es alcista o bajista (vs precio actual)
        color = 5763719 # Verde (bullish)
        if item['expected'] < item['last_price']:
            color = 15548997 # Rojo (bearish)

        embed = {
            "title": f"📊 Proyección Cuantitativa: {item['ticker']}",
            "description": f"Análisis de volatilidad y percentiles para el **{item['date']}**.",
            "color": color,
            "fields": [
                {
                    "name": "Precio Actual",
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
                    "name": "📉 Soporte Extremo (P1 - P5)",
                    "value": f"P1: {item['p1']}\nP5: {item['p5']}",
                    "inline": True
                },
                {
                    "name": "🎯 Rango Central (P50)",
                    "value": f"**{item['p50']}**",
                    "inline": True
                },
                {
                    "name": "📈 Resistencia Extrema (P95 - P99)",
                    "value": f"P95: {item['p95']}\nP99: {item['p99']}",
                    "inline": True
                }
            ],
            "footer": {
                "text": "Quant Engine | Monte Carlo Simulation | Nivel de Confianza: 95%"
            }
        }
        embeds.append(embed)

    payload = {
        "username": "Quant Engine Bot",
        "avatar_url": "https://i.imgur.com/4M34hi2.png", # Puedes poner un logo aquí
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
            # 1. Obtener datos
            data = yf.download(ticker, period="1y", interval="1d", progress=False)
            
            # Ajuste por si yfinance devuelve MultiIndex
            if isinstance(data.columns, pd.MultiIndex):
                data = data["Close"]
            else:
                data = data["Close"]
            
            data = data.dropna()
            
            if data.empty:
                print(f"⚠️ Sin datos para {ticker}")
                continue

            # 2. Cálculos Base
            returns = data.pct_change().dropna()
            mean_r = returns.mean()
            std_r = returns.std(ddof=0) # ddof=0 para población, 1 para muestra. 
            
            # Usamos el último precio REAL (no media)
            last_price = float(data.iloc[-1]) 
            
            # 3. Monte Carlo Vectorizado
            # Generamos retornos aleatorios
            rand_returns = np.random.normal(mean_r, std_r, size=(N_SIMS, DAYS_AHEAD))
            
            # Caminos de precio: Precio_Ultimo * (1 + retorno)
            price_paths = last_price * (1 + rand_returns) # Para 1 día es simple
            
            # 4. Resultados del Día +1 (Columna 0 porque es 1 solo día)
            simulated_prices = price_paths[:, 0]
            
            # Percentiles
            p1 = np.percentile(simulated_prices, 1)
            p5 = np.percentile(simulated_prices, 5)
            p50 = np.percentile(simulated_prices, 50)
            p95 = np.percentile(simulated_prices, 95)
            p99 = np.percentile(simulated_prices, 99)
            
            expected_price = np.mean(simulated_prices)
            vol_annual = std_r * np.sqrt(252) * 100
            
            # Fecha objetivo (Mañana)
            target_date = pd.Timestamp.now() + pd.Timedelta(days=1)
            
            results_to_send.append({
                "ticker": ticker,
                "date": target_date.strftime('%Y-%m-%d'),
                "last_price": last_price,
                "expected": expected_price,
                "volatility": vol_annual,
                "p1": f"{p1:.2f}",
                "p5": f"{p5:.2f}",
                "p50": f"{p50:.2f}",
                "p95": f"{p95:.2f}",
                "p99": f"{p99:.2f}"
            })
            
        except Exception as e:
            print(f"❌ Error procesando {ticker}: {e}")
            continue

    # Enviar reporte si hay datos
    if results_to_send:
        send_discord_embed(results_to_send)
    else:
        print("⚠️ No se generaron datos para enviar.")

if __name__ == "__main__":
    run_simulation()
