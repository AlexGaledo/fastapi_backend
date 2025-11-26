import os
from functools import lru_cache
import firebase_admin
from firebase_admin import credentials, firestore as fa_firestore, storage


def initialize_firebase():
	"""Initialize Firebase app once with both Firestore and Storage."""
	if not firebase_admin._apps:
		cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./firebase_key.json")
		cred = credentials.Certificate(cred_path)
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