"""
Frame Analysis Dashboard Launcher
Run this script to start the dashboard server
"""
from server import app

if __name__ == "__main__":
    print("Starting Frame Analysis Dashboard on http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    app.run(debug=True, host="0.0.0.0", port=5000)