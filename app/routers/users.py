from fastapi import APIRouter, HTTPException
from ..services.firebase import db
from pydantic import BaseModel
from datetime import datetime
import logging, traceback


class WalletInfoResponse(BaseModel):
    walletAddress: str
    createdAt: datetime
    eventsJoined: int
    reputation: int
    username: str
    message: str | None = None

class WalletRequest(BaseModel):
    walletAddress: str | None


router = APIRouter()

COLLECTION_NAME = "Wallets"


def create_user(wallet_address) -> WalletInfoResponse:
    """Create a new user document using wallet address as ID."""
    
    user_data = {
        "walletAddress": wallet_address,
        "createdAt": datetime.now(),
        "eventsJoined": 0,
        "reputation": 0,
        "username": wallet_address[:6] + "...",
    }

    db.collection(COLLECTION_NAME).add(user_data)
    return WalletInfoResponse(**user_data)
    

@router.post("/retrieveWalletInfo", response_model=WalletInfoResponse)
def retrieve_wallet_info(req: WalletRequest):
    """Retrieve wallet info; create new user if not found."""
    if not req.walletAddress:
        raise HTTPException(status_code=400, detail="Wallet address is required.")
    
    try:
        query = db.collection("Wallets") \
          .where("walletAddress", "==", req.walletAddress) \
          .limit(1) \
          .get()

        # If user does not exist, create it
        if not query:
            return create_user(req.walletAddress)

        data = query[0].to_dict()

        if data is None:
            raise HTTPException(status_code=500, detail="Corrupted user data.")

        # Ensure Firestore timestamp is converted to datetime
        created_at = data.get("createdAt")
        if not isinstance(created_at, datetime):
            created_at = datetime.now()

        return WalletInfoResponse(
            walletAddress=data.get("walletAddress", req.walletAddress),
            createdAt=created_at,
            eventsJoined=data.get("eventsJoined", 0),
            reputation=data.get("reputation", 0),
            username=data.get("username", req.walletAddress[:6] + "..."),
        )

    except HTTPException:
        raise  # rethrow so FastAPI handles it correctly

    except Exception as e:
        logging.error(f"Error retrieving wallet info for {req.walletAddress}: {e}")
        logging.error(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail="Internal error while retrieving wallet information."
        )


@router.post("/getUserInfo")
def get_user_info(request: WalletRequest):
    """Simple endpoint to check if user exists."""
    if not request.walletAddress:
        raise HTTPException(status_code=400, detail="Wallet address is required.")
    
    try:
        query = db.collection("Users") \
          .where("wallet_address","==", request.walletAddress) \
          .limit(1) \
          .get()

        if not query:
            return {"exists": False}

        data = query[0].to_dict()  # just to ensure data integrity

        return {"userInfo": data, "exists": True}

    except Exception as e:
        logging.error(f"Error checking user existence for {request.walletAddress}: {e}")
        logging.error(traceback.format_exc())

        raise HTTPException(
            status_code=500,
            detail="Internal error while checking user existence."
        )