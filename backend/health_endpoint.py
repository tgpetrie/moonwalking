# Health check endpoint
@app.route('/api/health')
def health_check():
    """Health check endpoint for monitoring"""
    try:
        # Quick validation that APIs are reachable
        test_url = "https://api.exchange.coinbase.com/products"
        response = requests.get(test_url, timeout=5)
        
        return jsonify({
            "status": "healthy",
            "timestamp": datetime.now().isoformat(),
            "version": "3.0.0",
            "uptime": time.time() - app.start_time if hasattr(app, 'start_time') else 0,
            "external_apis": {
                "coinbase": "up" if response.status_code == 200 else "down"
            }
        }), 200
    except Exception as e:
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }), 503

# Add startup time tracking
app.start_time = time.time()

if __name__ == '__main__':
    # Production-ready server startup
    port = CONFIG.get('PORT', 5001)
    host = CONFIG.get('HOST', '0.0.0.0')
    debug = CONFIG.get('DEBUG', False)
    
    logging.info(f"Starting CBMo4ers API server on {host}:{port}")
    logging.info(f"Debug mode: {debug}")
    logging.info(f"CORS origins: {cors_origins}")
    
    app.run(
        host=host,
        port=port,
        debug=debug,
        threaded=True
    )
