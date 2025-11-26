import os, json
from functools import lru_cache
import firebase_admin
from firebase_admin import credentials, firestore as fa_firestore, storage
from dotenv import load_dotenv

load_dotenv()

def initialize_firebase():
    """Initialize Firebase app once with both Firestore and Storage."""
    if not firebase_admin._apps:
        cred_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

        if cred_json is None:
            raise Exception("Missing GOOGLE_APPLICATION_CREDENTIALS env variable")

        cred_dict = json.loads(cred_json)  # convert JSON string → Python dict
        cred = credentials.Certificate(cred_dict)

        firebase_admin.initialize_app(cred, {
            'storageBucket': 'hackconnect-v2.firebasestorage.app'
        })



@lru_cache(maxsize=1)
def get_db():
	"""Return a singleton Firestore client."""
	initialize_firebase()
	return fa_firestore.client()


@lru_cache(maxsize=1)
def get_storage_bucket():
	"""Return the Firebase Storage bucket."""
	initialize_firebase()
	return storage.bucket()


# Convenience aliases
db = get_db()
storage_bucket = get_storage_bucket()