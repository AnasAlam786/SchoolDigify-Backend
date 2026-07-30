import os
from src import create_app

app = create_app()

if __name__ == "__main__":
    # app.run(port=2000, debug=True)
    port = int(os.environ.get("PORT", 5000))  # fallback for local testing
    app.run(host="localhost", port=port, debug=True)

    #app.run(debug=True)
      
    # On Windows:
    # .venv\Scripts\activate