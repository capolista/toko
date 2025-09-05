# File: app.py
import time, hmac, hashlib, requests
from decimal import Decimal
import locale
from flask import Flask, jsonify, render_template
import os
from datetime import datetime

app = Flask(__name__)

# Function untuk load data modal dari file
def load_modal_data(file_path="modal.txt"):
    modal_data = {}
    try:
        if os.path.exists(file_path):
            with open(file_path, 'r', encoding='utf-8') as file:
                for line in file:
                    line = line.strip()
                    if not line or line.startswith('#'):
                        continue
                    
                    if '=' in line:
                        asset, modal = line.split('=', 1)
                        asset = asset.strip().upper()
                        modal = modal.strip()
                    elif ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            asset, modal = parts[0].strip().upper(), parts[1].strip()
                        else:
                            continue
                    else:
                        continue
                    
                    try:
                        modal_data[asset] = Decimal(modal)
                    except:
                        modal_data[asset] = Decimal("0")
                        
    except Exception as e:
        print(f"Error loading modal data: {e}")
    
    return modal_data

# Function format_idr
def format_idr(amount):
    if amount == 0:
        return "-"
    
    try:
        amount_float = float(amount)
        if amount_float == 0:
            return "-"
            
        amount_str = f"{amount_float:.2f}"
        
        if '.' in amount_str:
            integer_part, decimal_part = amount_str.split('.')
        else:
            integer_part, decimal_part = amount_str, "00"
        
        # Format integer part with thousand separators
        integer_formatted = ""
        for i, char in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                integer_formatted = '.' + integer_formatted
            integer_formatted = char + integer_formatted
        
        return f"{integer_formatted},{decimal_part}"
    except:
        return str(amount)

# Function format_asset    
def format_asset(amount):
    if amount == 0:
        return "-"
    
    try:
        amount_float = float(amount)
        if amount_float == 0:
            return "-"
            
        amount_str = f"{amount_float:.2f}"
        
        if '.' in amount_str:
            integer_part, decimal_part = amount_str.split('.')
        else:
            integer_part, decimal_part = amount_str, "00"
        
        # Format integer part with thousand separators
        integer_formatted = ""
        for i, char in enumerate(reversed(integer_part)):
            if i > 0 and i % 3 == 0:
                integer_formatted = '.' + integer_formatted
            integer_formatted = char + integer_formatted
        
        return f"{integer_formatted},{decimal_part}"
    except:
        return str(amount)

# Function format_price_asset    
def format_price(price: float) -> str:
    digits_before = len(str(int(price)))
    digits_after = max(0, 11 - digits_before)  # sisanya untuk koma
    format_str = "{:." + str(digits_after) + "f}"
    return format_str.format(price)

# Function utama untuk get portfolio data
def get_portfolio_data():
    try:
        modal_data = load_modal_data("modal.txt")
        
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
                        price_map["IDR"] = Decimal("1") / usdt_idr_price
                    continue
                    
                symbol = f"{asset}_USDT"
                depth_url = f"{base_url}/open/v1/market/depth?symbol={symbol}&limit=5"
                depth_resp = requests.get(depth_url, timeout=10)
                
                if depth_resp.status_code == 200:
                    depth_data = depth_resp.json()
                    if depth_data.get("code") == 0 and depth_data["data"]["bids"] and depth_data["data"]["asks"]:
                        best_bid = Decimal(depth_data["data"]["bids"][0][0])
                        best_ask = Decimal(depth_data["data"]["asks"][0][0])
                        price_map[asset] = (best_bid + best_ask) / Decimal("2")
                        time.sleep(0.03)
            except:
                continue

        # Prepare response data
        portfolio_data = []
        total_portfolio_usdt = Decimal("0")
        total_portfolio_idr = Decimal("0")
        total_modal_usdt = Decimal("0")

        for asset, total in rows:
            if asset in price_map:
                price = price_map[asset]
                value_usdt = total * price
                
                if asset == "IDR":
                    value_idr = total
                else:
                    value_idr = value_usdt * usdt_idr_price if usdt_idr_price else Decimal("0")
                
                # Hitung modal dan profit per aset
                modal_amount = modal_data.get(asset, Decimal("0"))
                
                # Abaikan aset dengan modal 0
                if modal_amount == 0:
                    continue
                
                profit_usdt = value_usdt - modal_amount
                profit_idr = profit_usdt * usdt_idr_price if usdt_idr_price else Decimal("0")
                
                total_portfolio_usdt += value_usdt
                total_portfolio_idr += value_idr
                total_modal_usdt += modal_amount
                
                portfolio_data.append({
                    'asset': asset,
                    'total': total,  # Simpan nilai asli untuk sorting
                    'total_formatted': format_asset(total),
                    'price': format_price(price),
                    'usdt_value': value_usdt,  # Simpan nilai asli untuk sorting
                    'usdt_value_formatted': f"{value_usdt:.4f}",
                    'idr_value': value_idr,  # Simpan nilai asli untuk sorting
                    'idr_value_formatted': format_idr(value_idr),
                    'modal': modal_amount,  # Simpan nilai asli untuk sorting
                    'modal_formatted': f"{modal_amount:.2f}",
                    'profit_usdt': profit_usdt,  # Simpan nilai asli untuk sorting
                    'profit_usdt_formatted': f"{profit_usdt:.2f}",
                    'profit_idr': profit_idr,  # Simpan nilai asli untuk sorting
                    'profit_idr_formatted': format_idr(profit_idr)
                })
        
        # MODIFIKASI: Urutkan berdasarkan total asset terbanyak (nilai USDT)
        portfolio_data.sort(key=lambda x: x['usdt_value'], reverse=True)
        
        # Kembalikan data yang diformat untuk response
        formatted_portfolio_data = []
        for item in portfolio_data:
            formatted_portfolio_data.append({
                'asset': item['asset'],
                'total': item['total_formatted'],
                'price': item['price'],
                'usdt_value': item['usdt_value_formatted'],
                'idr_value': item['idr_value_formatted'],
                'modal': item['modal_formatted'],
                'profit_usdt': item['profit_usdt_formatted'],
                'profit_idr': item['profit_idr_formatted']
            })
        
        # Hitung total profit
        total_profit_usdt = total_portfolio_usdt - total_modal_usdt
        total_profit_idr = total_profit_usdt * usdt_idr_price if usdt_idr_price else Decimal("0")
        
        return {
            'success': True,
            'data': formatted_portfolio_data,
            'total_usdt': f"{total_portfolio_usdt:.2f}",
            'total_idr': format_idr(total_portfolio_idr),
            'total_modal': f"{total_modal_usdt:.2f}",
            'total_profit_usdt': f"{total_profit_usdt:.2f}",
            'total_profit_idr': format_idr(total_profit_idr),
            'rate': f"{usdt_idr_price:.2f}" if usdt_idr_price else None
        }
        
    except Exception as e:
        return {'success': False, 'error': str(e)}

# Route untuk JSON API
@app.route('/portfolio')
def portfolio():
    data = get_portfolio_data()
    return jsonify(data)

# Route untuk HTML Template
@app.route('/')
def home():
    data = get_portfolio_data()
    if data['success']:
        return render_template('main.html', 
                             data=data['data'],
                             total_usdt=data['total_usdt'],
                             total_idr=data['total_idr'],
                             total_modal=data['total_modal'],
                             total_profit_usdt=data['total_profit_usdt'],
                             total_profit_idr=data['total_profit_idr'],
                             rate=data.get('rate'),
                             now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    else:
        return render_template('main.html', 
                             data=[],
                             total_usdt="0",
                             total_idr="0",
                             total_modal="0",
                             total_profit_usdt="0",
                             total_profit_idr="0",
                             rate=None,
                             now=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                             error=data['error'])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=os.environ.get('PORT', 5000), debug=False)
