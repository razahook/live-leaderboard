import os
from flask_sqlalchemy import SQLAlchemy

# Create the central SQLAlchemy database object.
# All other parts of your application will import this 'db' object.
db = SQLAlchemy()

# Define your database models here, right after creating the 'db' object.
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)

    def __repr__(self):
        return f'<User {self.username}>'

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email
        }

def init_app(app):
    """Initializes the database connection and creates tables."""
    # This logic uses the Vercel Postgres URL when deployed.
    postgres_url = os.environ.get('POSTGRES_URL')
    
    if postgres_url:
        # Vercel provides a URL that needs a slight tweak for SQLAlchemy
        app.config['SQLALCHEMY_DATABASE_URI'] = postgres_url.replace("postgres://", "postgresql://")
    else:
        # This is a fallback for running the app on your local computer for testing
        db_path = os.path.join(os.path.dirname(__file__), '..', '..', 'database', 'app.db')
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{db_path}"

    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    db.init_app(app)

    # Now that the models are defined in this file, db.create_all() will correctly
    # find the User table and create it in your Vercel Postgres database.
    with app.app_context():
        db.create_all()
