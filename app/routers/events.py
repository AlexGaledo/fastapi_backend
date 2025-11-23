from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import datetime as dt
from ..services.firebase import db
import logging, traceback


router = APIRouter()

class EventTiers(BaseModel):
    tierName: str
    ticketCount: int
    ticketSold: int
    price: float
    hackRewards:int

class Event(BaseModel):
    event_id: str | None = None
    event_link: str
    event_title: str
    date_start: dt.datetime
    date_end: dt.datetime
    description: str
    host_address: str
    status: str
    ticket_tiers: list[EventTiers]

class ResponseModel(BaseModel):
    message:str
    eventInfo:Event

class EventListResponse(BaseModel):
    events: list[Event]




@router.get("/listEvents")
def list_events():
    """Retrieve a list of events based on countToRetrieve."""
    try:
        query = db.collection("Events").get()
        retrieved_events = []
        for doc in query:
            data = doc.to_dict() or {}
            # Convert Firestore timestamps if they have a to_datetime() method
            start_raw = data.get("date_start")
            end_raw = data.get("date_end")
            if start_raw is not None and hasattr(start_raw, "to_datetime"):
                data["date_start"] = start_raw.to_datetime()
            if end_raw is not None and hasattr(end_raw, "to_datetime"):
                data["date_end"] = end_raw.to_datetime()

            event_dict = {
                "event_id": doc.id,
                "event_link": data.get("eventLink", ""),
                "event_title": data.get("title", ""),
                "date_start": data.get("startDate", dt.datetime.utcnow()),
                "date_end": data.get("endDate", dt.datetime.utcnow()),
                "description": data.get("description", ""),
                "host_address": data.get("hostAddress", ""),
                "status": data.get("status", ""),
                "ticket_tiers": data.get("ticketTiers", []),
            }

            # Correct instantiation: use keyword expansion, not positional argument
            retrieved_events.append(Event(**event_dict))

    except Exception as e:
        logging.error("Error retrieving events: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving events: {str(e)}")
    
    return EventListResponse(events=retrieved_events)

@router.get("/retrieveTickets/{wallet_address}")
def retrieve_tickets(wallet_address: str):
    """Retrieve tickets for a given wallet address."""
    
    if not wallet_address:
        raise HTTPException(status_code=400, detail="Wallet address is required.")
    
    try:
        query = db.collection("Tickets")\
        .where("walletAddress", "==", wallet_address)\
        .get()

        tickets = []
        for doc in query:
            data = doc.to_dict()
            if not data:
                continue
            tickets.append(data)
        return {"wallet_address": wallet_address, "tickets": tickets}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving tickets: {str(e)}")

@router.post("/create",response_model=ResponseModel)
def create_event(req: ResponseModel ):
    """Create a new event."""
    try:
        # Pydantic v2: use model_dump() instead of deprecated .dict()
        event_data = req.eventInfo.model_dump()

        db.collection("Events").add(event_data)

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error creating event: {str(e)}")
    
    return ResponseModel(message="Event created successfully", eventInfo=req.eventInfo)


@router.get("/getEventById/{event_id}")
def get_event_by_id(event_id: str):
    """Retrieve an event by its ID."""

    try:
        doc_ref = db.collection("Events").document(event_id)
        doc = doc_ref.get()
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Event not found.")
        
        data = doc.to_dict() or {}
        start_raw = data.get("date_start")
        end_raw = data.get("date_end")
        if start_raw is not None and hasattr(start_raw, "to_datetime"):
            data["date_start"] = start_raw.to_datetime()
        if end_raw is not None and hasattr(end_raw, "to_datetime"):
            data["date_end"] = end_raw.to_datetime()

        event = Event(
            event_id=doc.id,
            event_link=data.get("eventLink", ""),
            event_title=data.get("title", ""),
            date_start=data.get("startDate", dt.datetime.now()),
            date_end=data.get("endDate", dt.datetime.now()),
            description=data.get("description", ""),
            host_address=data.get("hostAddress", ""),
            status=data.get("status", ""),
            ticket_tiers=data.get("ticketTiers", []),
        )

        return ResponseModel(message="Event retrieved successfully", eventInfo=event)

    except HTTPException:
        raise  # rethrow so FastAPI handles it correctly

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving event: {str(e)}")