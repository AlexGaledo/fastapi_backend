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

class taskResponse(BaseModel):
    eventId: str | None
    taskDescription: str | None
    taskId: str | None
    taskTitle: str | None
    taskRewards: int | None
    claimed: bool | None
    walletAddress: str | None
    identifier: str | None


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


@router.get("/retrieveTasks/{wallet_address}")
def get_task_logs(wallet_address: str):
    """Return list of tasks for user."""
    if not wallet_address:
        raise HTTPException(status_code=404, detail="missing wallet_address")

    try:
        query = db.collection('Task_logs') \
            .where("walletAddress", "==", wallet_address) \
            .get()

        # If Firestore returns None (unexpected), treat as not found
        if query is None:
            raise HTTPException(status_code=404, detail="user/task not found")

        tasks = []
        for doc in query:
            data = doc.to_dict()
            if not data:
                raise HTTPException(status_code=500, detail="corrupted task data")

            # Use a simple dict format matching frontend expectations
            tasks.append({
                "eventId": data.get("eventId"),
                "taskId": doc.id,
                "taskTitle": data.get("taskTitle"),
                "taskDescription": data.get("taskDescription"),
                "taskRewards": data.get("taskRewards"),
                "claimed": data.get("claimed"),
                "walletAddress": data.get("walletAddress"),
                "identifier": data.get("identifier")
            })

        # Return tasks under `tasks` key (frontend expects `response.data.tasks`)
        return {"tasks": tasks}

    except HTTPException:
        raise
    except Exception as e:
        logging.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving task logs: {str(e)}")


@router.post("/createTasks/{wallet_address}")
def create_task(wallet_address: str):
    """Create a new task for user."""
    # TODO: implement task creation
    raise HTTPException(status_code=501, detail="Not implemented")