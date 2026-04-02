"""AI Terms & Conditions Analyzer - Flask Application."""

from src.routes import app

if __name__ == "__main__":
    app.run(debug=True, port=5000)
