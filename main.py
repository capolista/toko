# File: app.py
import time, hmac, hashlib, requests
from decimal import Decimal
import locale
from flask import Flask, jsonify, render_template
import os
from datetime import datetime

app = Flask(__name__)

# Function untuk load data modal dari file
#def load_modal_data(file_path="modal.txt"):
def load_modal_data(file_path="modal.txt"):
    modal_data = {}
    print(f"🔍 Mencari file modal di: {os.path.abspath(file_path)}")
    
    try:
        if os.path.exists(file_path):
            print("✅ File modal.txt ditemukan!")
            with open(file_path, 'r', encoding='utf-8') as file:
                content = file.read()
                print(f"📄 Isi file:\n{content}")
                
                file.seek(0)  # Kembali ke awal file
                for line_num, line in enumerate(file, 1):
                    line = line.strip()
                    print(f"📝 Line {line_num}: '{line}'")
                    
                    # Skip empty lines and comments
                    if not line or line.startswith('#'):
                        print(f"⏩ Skip line {line_num} (empty/comment)")
                        continue
                    
                    # Support multiple formats
                    if '=' in line:
                        parts = line.split('=', 1)
                        asset, modal = parts[0].strip(), parts[1].strip()
                        print(f"📊 Parsed: {asset} = {modal}")
                    elif ',' in line:
                        parts = line.split(',')
                        if len(parts) >= 2:
                            asset, modal = parts[0].strip(), parts[1].strip()
                            print(f"📊 Parsed: {asset} = {modal}")
                        else:
                            continue
                    else:
                        print(f"❌ Format tidak dikenali di line {line_num}")
                        continue
                    
                    asset = asset.upper()  # Pastikan UPPERCASE
                    try:
                        modal_value = Decimal(modal)
                        modal_data[asset] = modal_value
                        print(f"✅ Added: {asset} -> {modal_value}")
                    except Exception as e:
                        print(f"❌ Error converting modal value: {e}")
                        modal_data[asset] = Decimal("0")
        else:
            print("❌ File modal.txt TIDAK ditemukan!")
            
    except Exception as e:
        print(f"❌ Error loading modal data: {e}")
    
    print(f"📦 Final modal data: {modal_data}")
    return modal_data

# Function format_idr
def format_idr(amount):
    if amount == 0:
        return "-"
    try:
        return locale.format_string("%.2f", float(amount), grouping=True)
    except:
        return f"{amount:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

# Function utama untuk get portfolio data
def get_portfolio_data():
    try:
        # Load modal data from file
        modal_data = load_modal_data("modal.txt")
        
        # --- KODE ANDA DIMULAI DI SINI ---
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

        # Prepare response data
        portfolio_data = []
        total_portfolio_usdt = Decimal("0")
        total_portfolio_idr = Decimal("0")
        total_modal_usdt = Decimal("0")
        total_profit_usdt = Decimal("0")
        total_profit_idr = Decimal("0")

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
                
                # Hitung modal dan profit per aset
                modal_amount = modal_data.get(asset, Decimal("0"))
                profit_usdt = value_usdt - modal_amount
                profit_idr = profit_usdt * usdt_idr_price if usdt_idr_price else Decimal("0")
                
                total_modal_usdt += modal_amount
                total_profit_usdt += profit_usdt
                total_profit_idr += profit_idr
                
                portfolio_data.append({
                    'asset': asset,
                    'total': str(total),
                    'price': str(price),
                    'usdt_value': f"{value_usdt:.4f}",
                    'idr_value': format_idr(value_idr),
                    'modal': f"{modal_amount:.2f}",
                    'profit_usdt': f"{profit_usdt:.2f}",
                    'profit_idr': format_idr(profit_idr)
                })
        
        # Hitung total profit global (sebagai double check)
        global_profit_usdt = total_portfolio_usdt - total_modal_usdt
        global_profit_idr = global_profit_usdt * usdt_idr_price if usdt_idr_price else Decimal("0")
        
        return {
            'success': True,
            'data': portfolio_data,
            'total_usdt': f"{total_portfolio_usdt:.2f}",
            'total_idr': format_idr(total_portfolio_idr),
            'total_modal': f"{total_modal_usdt:.2f}",
            'total_profit_usdt': f"{total_profit_usdt:.2f}",
            'total_profit_idr': format_idr(total_profit_idr),
            'global_profit_usdt': f"{global_profit_usdt:.2f}",
            'global_profit_idr': format_idr(global_profit_idr),
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
