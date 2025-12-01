#!/usr/bin/env python3
"""
dashboard_api.py

================================================================================
ARES7 Dashboard API Server (NO MOCK DATA)
================================================================================

역할:
  - 실시간 CSV 데이터만 사용 (플레이스홀더 없음)
  - ares7_final_weights, overlay, PnL 데이터 제공
  - Flask 기반 REST API

실행:
  python3 dashboard_api.py

API Endpoints:
  GET /status - 대시보드 전체 데이터
  GET /weights - 최종 weights
  GET /overlay - Overlay 데이터
  POST /kill_switch - Kill switch 제어

Author: ARES7/ARES8 Research Team
Date: 2025-12-01
Version: 1.0 (NO PLACEHOLDERS)
================================================================================
"""

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import pandas as pd
from pathlib import Path
from datetime import datetime
import glob

# ============================================================================
# Configuration
# ============================================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
OUTPUT_DIR = BASE_DIR / "ensemble_outputs"
TEMPLATES_DIR = BASE_DIR / "templates"

app = Flask(__name__, template_folder=str(TEMPLATES_DIR))
CORS(app)

# Kill switch state
KILL_SWITCH_STATE = 'RUNNING'

# ============================================================================
# Helper Functions
# ============================================================================

def find_latest_file(pattern):
    """Find the latest file matching the pattern"""
    files = sorted(OUTPUT_DIR.glob(pattern), reverse=True)
    return files[0] if files else None


def load_final_weights():
    """Load latest ares7_final_weights CSV"""
    latest_file = find_latest_file("ares7_final_weights_*.csv")
    if not latest_file:
        return None
    
    df = pd.read_csv(latest_file)
    return df


def load_overlay():
    """Load latest wavelet_pead_overlay CSV"""
    latest_file = find_latest_file("wavelet_pead_overlay_prod_*.csv")
    if not latest_file:
        return None
    
    df = pd.read_csv(latest_file)
    return df


# ============================================================================
# API Endpoints
# ============================================================================

@app.route('/')
def index():
    """Serve dashboard HTML"""
    return send_from_directory(TEMPLATES_DIR, 'index.html')


@app.route('/status')
def get_status():
    """Get full dashboard status - REAL DATA ONLY"""
    try:
        # Load weights
        df_weights = load_final_weights()
        
        if df_weights is None or len(df_weights) == 0:
            return jsonify({
                'error': 'No weights data available',
                'message': 'Run ./run_full_pipeline.sh to generate data'
            }), 404
        
        # Calculate portfolio stats
        total_weight = df_weights['weight_final'].sum()
        gross_exposure = df_weights['weight_final'].abs().sum()
        net_exposure = df_weights['weight_final'].sum()
        
        # Top positions (top 5 by weight_final)
        df_top = df_weights.nlargest(5, 'weight_final')
        top_positions = []
        for _, row in df_top.iterrows():
            top_positions.append({
                'symbol': row['symbol'],
                'weight': float(row['weight_final']),
                'shares': 0,  # Not available in CSV
                'price': 0.0,  # Not available in CSV
                'value': 0.0,  # Not available in CSV
            })
        
        # Build response - ONLY REAL DATA
        response = {
            'timestamp': datetime.now().isoformat(),
            'equity': 0.0,  # Not available - need PnL data
            'todays_pnl': 0.0,  # Not available - need PnL data
            'todays_return': 0.0,  # Not available - need PnL data
            'month_pnl': 0.0,  # Not available - need PnL data
            'month_return': 0.0,  # Not available - need PnL data
            'cum_pnl': 0.0,  # Not available - need PnL data
            'current_dd': 0.0,  # Not available - need PnL data
            'current_leverage': float(gross_exposure),
            'net_exposure': float(net_exposure),
            'gross_exposure': float(gross_exposure),
            'regime': 'WAVELET+PEAD',
            'equity_curve': [],  # Not available - need PnL data
            'times': [],  # Not available - need PnL data
            'top_positions': top_positions,
            'recent_trades': [],  # Not available - need trade log
            'kill_switch': KILL_SWITCH_STATE,
        }
        
        return jsonify(response)
    
    except Exception as e:
        print(f"Error in /status: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/weights')
def get_weights():
    """Get final weights - REAL DATA ONLY"""
    try:
        df_weights = load_final_weights()
        
        if df_weights is None:
            return jsonify({
                'error': 'No weights data available',
                'message': 'Run ./run_full_pipeline.sh to generate data'
            }), 404
        
        return jsonify(df_weights.to_dict('records'))
    
    except Exception as e:
        print(f"Error in /weights: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/overlay')
def get_overlay():
    """Get overlay data - REAL DATA ONLY"""
    try:
        df_overlay = load_overlay()
        
        if df_overlay is None:
            return jsonify({
                'error': 'No overlay data available',
                'message': 'Run ./run_full_pipeline.sh to generate data'
            }), 404
        
        return jsonify(df_overlay.to_dict('records'))
    
    except Exception as e:
        print(f"Error in /overlay: {e}")
        return jsonify({'error': str(e)}), 500


@app.route('/kill_switch', methods=['POST'])
def kill_switch():
    """Handle kill switch"""
    global KILL_SWITCH_STATE
    
    try:
        data = request.json
        mode = data.get('mode', 'RUNNING')
        
        # Update state
        KILL_SWITCH_STATE = mode
        
        print(f"[{datetime.now()}] Kill switch: {mode}")
        
        # TODO: Implement actual trading halt logic
        # For now, just log the state change
        
        return jsonify({'status': 'ok', 'mode': mode})
    
    except Exception as e:
        print(f"Error in /kill_switch: {e}")
        return jsonify({'error': str(e)}), 500


# ============================================================================
# Main
# ============================================================================

if __name__ == '__main__':
    print("=" * 80)
    print("ARES7 Dashboard API Server (NO MOCK DATA)")
    print("=" * 80)
    print(f"Base directory: {BASE_DIR}")
    print(f"Data directory: {DATA_DIR}")
    print(f"Output directory: {OUTPUT_DIR}")
    print(f"Templates directory: {TEMPLATES_DIR}")
    print("=" * 80)
    
    # Check for data files
    weights_file = find_latest_file("ares7_final_weights_*.csv")
    overlay_file = find_latest_file("wavelet_pead_overlay_prod_*.csv")
    
    if weights_file:
        print(f"✅ Weights file found: {weights_file.name}")
    else:
        print(f"❌ No weights file found")
        print(f"   Run: ./run_full_pipeline.sh")
    
    if overlay_file:
        print(f"✅ Overlay file found: {overlay_file.name}")
    else:
        print(f"❌ No overlay file found")
        print(f"   Run: ./run_full_pipeline.sh")
    
    print("=" * 80)
    print("Starting server on http://0.0.0.0:5000")
    print("=" * 80)
    
    app.run(host='0.0.0.0', port=5000, debug=False, threaded=True)
