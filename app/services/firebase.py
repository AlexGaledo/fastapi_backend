import os
from functools import lru_cache
import firebase_admin
from firebase_admin import credentials, firestore as fa_firestore


@lru_cache(maxsize=1)
def get_db():
	"""Return a singleton Firestore client.

	Initializes the Firebase app once. The path to the service account JSON
	can be set via the environment variable GOOGLE_APPLICATION_CREDENTIALS.
	Falls back to a local file name `firebase_key.json` if not set.
	"""
	if not firebase_admin._apps:  # Avoid re-initializing on reloads
		cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "./firebase_key.json")
		cred = credentials.Certificate(cred_path)
		firebase_admin.initialize_app(cred)
	return fa_firestore.client()


# Convenience alias if you prefer direct import usage:
db = get_db()
