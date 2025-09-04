# File: app.py
import time, hmac, hashlib, requests
from decimal import Decimal
import locale
from flask import Flask, jsonify
import os

app = Flask(__name__)

# Function format_idr 
def format_idr(amount):
    if amount == 0:
        return "0"
    try:
        return locale.format_string("%.2f", float(amount), grouping=True)
    except:
        return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Function utama untuk get portfolio data
def get_portfolio_data():
    try:
        API_KEY = "bcd058e9F7831a3B65049aBfaF275FeD61ugHSZPBR0uF5HSAEjp1eX34AFpRTEZ"
        API_SECRET = "07135804653758eBCA5424619904AFCC1FF6R9tEOWOdUyD7pcBsHs5uN4SZOvwC"
        base_url = "https://www.tokocrypto.com"

        # Set locale
        try:
            locale.setlocale(locale.LC_ALL, 'id_ID.UTF-8')
        except:
            try:
                locale.setlocale(locale.LC_ALL, 'Indonesian_Indonesia.1252')
            except:
                pass

        # Ambil saldo
        timestamp = int(time.time() * 1000)
        query = f"recvWindow=60000&timestamp={timestamp}"
        signature = hmac.new(API_SECRET.encode(), query.encode(), hashlib.sha256).hexdigest()

        url = f"{base_url}/open/v1/account/spot?{query}&signature={signature}"
        headers = {"X-MBX-APIKEY": API_KEY}
        resp = requests.get(url, headers=headers, timeout=30).json()

        rows = []
        if resp.get("code") == 0:
            for a in resp["data"]["accountAssets"]:
                free = Decimal(a["free"])
                locked = Decimal(a["locked"])
                if free > 0 or locked > 0:
                    rows.append((a["asset"], free + locked))

        # Ambil harga
        price_map = {"USDT": Decimal("1")}
        usdt_idr_price = None
        
        try:
            symbol = "USDT_IDR"
            depth_url = f"{base_url}/open/v1/market/depth?symbol={symbol}&limit=5"
            depth_resp = requests.get(depth_url, timeout=10)
            
            if depth_resp.status_code == 200:
                depth_data = depth_resp.json()
                if depth_data.get("code") == 0 and depth_data["data"]["bids"] and depth_data["data"]["asks"]:
                    best_bid = Decimal(depth_data["data"]["bids"][0][0])
                    best_ask = Decimal(depth_data["data"]["asks"][0][0])
                    usdt_idr_price = (best_bid + best_ask) / Decimal("2")
        except:
            pass

        # Process asset prices
        for asset, total in rows:
            if asset == "USDT":
                continue
                
            try:
                if asset == "IDR":
                    if usdt_idr_price:
                        idr_usdt_price = Decimal("1") / usdt_idr_price
                        price_map["IDR"] = idr_usdt_price
                    continue
                    
                symbol = f"{asset}_USDT"
                depth_url = f"{base_url}/open/v1/market/depth?symbol={symbol}&limit=5"
                depth_resp = requests.get(depth_url, timeout=10)
                
                if depth_resp.status_code == 200:
                    depth_data = depth_resp.json()
                    if depth_data.get("code") == 0 and depth_data["data"]["bids"] and depth_data["data"]["asks"]:
                        best_bid = Decimal(depth_data["data"]["bids"][0][0])
                        best_ask = Decimal(depth_data["data"]["asks"][0][0])
                        mid_price = (best_bid + best_ask) / Decimal("2")
                        price_map[asset] = mid_price
            except:
                pass

        # Prepare response data - FORMAT ARRAY SEDERHANA
        portfolio_array = []  # Array utama
        total_portfolio_usdt = Decimal("0")
        total_portfolio_idr = Decimal("0")

        # Header row sebagai index 0
        portfolio_array.append(["ASSET", "TOTAL", "PRICE", "USD VALUE", "IDR VALUE"])

        for asset, total in rows:
            if asset in price_map:
                price = price_map[asset]
                value_usdt = total * price
        
                if asset == "IDR":
                    value_idr = total
                else:
                    value_idr = value_usdt * usdt_idr_price if usdt_idr_price else Decimal("0")
        
                total_portfolio_usdt += value_usdt
                total_portfolio_idr += value_idr
        
                # TAMBAHKAN SEBAGAI ARRAY (BUKAN DICTIONARY)
                portfolio_array.append([
                    asset,                    # Index 0
                    str(total),               # Index 1  
                    str(price),               # Index 2
                    f"{value_usdt:.4f}",      # Index 3
                    format_idr(value_idr)     # Index 4
                ])

        # Return sebagai array sederhana
        return {
            'success': True,
            'data': portfolio_array,  # SEKARANG ARRAY, BUKAN DICTIONARY
            'total_usdt': f"{total_portfolio_usdt:.2f}",
            'total_idr': format_idr(total_portfolio_idr),
            'rate': f"{usdt_idr_price:.2f}" if usdt_idr_price else None
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Route untuk API
@app.route('/portfolio')
def portfolio():
    data = get_portfolio_data()
    return jsonify(data)

@app.route('/')
def home():
    return jsonify({"message": "TokoCrypto Portfolio API - Array Format", "status": "active"})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=True)
