
import uvicorn
from app import create_app

# Expose the ASGI application instance at module level so
# running `uvicorn main:app --reload` works. Previously it
# was only defined inside the __main__ guard causing
# "Attribute 'app' not found" when Uvicorn imported it.
app = create_app()

if __name__ == "__main__":
    # Direct invocation: `python main.py`
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")