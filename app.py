import os
from src import create_app

app = create_app()

if __name__ == "__main__":
    # app.run(port=2000, debug=True)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
    #app.run(debug=True)
      
    # On Windows:
    # .venv\Scripts\activate
