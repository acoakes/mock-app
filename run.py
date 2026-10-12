import os
os.environ.setdefault('FLASK_SECRET_KEY', 'dev-secret-key-change-in-production')
from app import app
if __name__ == '__main__':
    app.run(debug=True, port=5000)
