import json
import base64
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional
import datetime as dt
from ..services.firebase import db, storage_bucket
import logging, traceback
import qrcode as qr
from io import BytesIO
import uuid


router = APIRouter()

from pydantic import Field, ConfigDict


class EventTiers(BaseModel):
    """Internal event tier representation (stored/react responses)."""
    tierName: str
    ticketCount: int
    ticketSold: int = Field(0, alias="ticketsSold")
    price: float
    model_config = ConfigDict(populate_by_name=True)

class Event(BaseModel):
    event_id: str | None = None
    event_link: str
    event_title: str
    date_start: dt.datetime
    date_end: dt.datetime
    description: str
    host_address: str
    image_url: str | None = None
    status: str
    ticket_tiers: list[EventTiers]
    created_at: dt.datetime

class ResponseModel(BaseModel):
    message: str
    eventInfo: Event

class EventListResponse(BaseModel):
    events: list[Event]

class EventCreateTier(BaseModel):
    tierName: str
    ticketCount: int
    price: float
    ticketsSold: int = 0

class EventCreate(BaseModel):
    host_address: str
    title: str
    description: str
    event_link: str | None = None
    image_url: str | None = None
    date_start: dt.datetime
    date_end: dt.datetime | None = None
    status: str
    ticket_tiers: list[EventCreateTier]

class JoinEventPayload(BaseModel):
    eventTitle: str
    priceBought: float
    tierName: str

class updateTicketStatusPayload(BaseModel):
    ticketId: str
    new_status: str


@router.get("/listEvents")
def list_events():
    """Retrieve all events with proper field mapping."""
    try:
        query = db.collection("Events").get()
        retrieved_events = []
        for doc in query:
            data = doc.to_dict() or {}
            start_raw = data.get("date_start")
            end_raw = data.get("date_end")
            if start_raw is not None and hasattr(start_raw, "to_datetime"):
                data["date_start"] = start_raw.to_datetime()
            if end_raw is not None and hasattr(end_raw, "to_datetime"):
                data["date_end"] = end_raw.to_datetime()

            tiers_raw = data.get("ticketTiers", [])
            tiers: list[EventTiers] = []
            for t in tiers_raw:
                if isinstance(t, dict):
                    tiers.append(EventTiers(**t))

            event_obj = Event(
                event_id=doc.id,
                event_link=data.get("eventLink", ""),
                event_title=data.get("title", ""),
                date_start=data.get("startDate", dt.datetime.now()),
                date_end=data.get("endDate", dt.datetime.now()),
                description=data.get("description", ""),
                host_address=data.get("hostAddress", ""),
                image_url=data.get("imageUrl"),
                status=data.get("status", ""),
                ticket_tiers=tiers,
                created_at=data.get("createdAt", dt.datetime.utcnow()),
            )
            retrieved_events.append(event_obj)

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


@router.post("/create", response_model=ResponseModel)
async def create_event(
    host_address: str = Form(...),
    title: str = Form(...),
    description: str = Form(...),
    event_link: Optional[str] = Form(None),
    date_start: str = Form(...),
    date_end: Optional[str] = Form(None),
    status: str = Form(...),
    ticket_tiers: str = Form(...),  # JSON string
    image: Optional[UploadFile] = File(None)
    ):
    """Create a new event with optional image upload."""
    try:
        # Parse date strings
        start_dt = dt.datetime.fromisoformat(date_start.replace('Z', '+00:00'))
        end_dt = dt.datetime.fromisoformat(date_end.replace('Z', '+00:00')) if date_end else start_dt
        
        # Parse ticket tiers JSON
        tiers_data = json.loads(ticket_tiers)
        tiers = [EventTiers(**t) for t in tiers_data]
        
        # Upload image to Firebase Storage if provided
        image_url = None
        if image and image.filename:
            # Read image content
            image_content = await image.read()
            
            # Generate unique filename
            file_extension = image.filename.split('.')[-1]
            unique_filename = f"{uuid.uuid4()}.{file_extension}"
            
            # Upload to Firebase Storage
            bucket = storage_bucket
            blob_path = f"events/images/{unique_filename}"
            blob = bucket.blob(blob_path)
            
            # Upload from bytes
            blob.upload_from_string(
                image_content,
                content_type=image.content_type or 'image/jpeg'
            )
            
            # Make publicly accessible
            blob.make_public()
            image_url = blob.public_url
        
        now = dt.datetime.utcnow()
        event = Event(
            event_id=None,
            event_link=event_link or "",
            event_title=title,
            date_start=start_dt,
            date_end=end_dt,
            description=description,
            host_address=host_address,
            image_url=image_url,
            status=status,
            ticket_tiers=tiers,
            created_at=now,
        )

        firestore_doc = {
            "eventLink": event.event_link,
            "title": event.event_title,
            "startDate": event.date_start,
            "endDate": event.date_end,
            "description": event.description,
            "hostAddress": event.host_address,
            "imageUrl": event.image_url,
            "status": event.status,
            "ticketTiers": [t.model_dump(by_alias=True) for t in tiers],
            "createdAt": event.created_at,
        }
        _, doc_ref = db.collection("Events").add(firestore_doc)
        event.event_id = doc_ref.id

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid ticket_tiers JSON: {str(e)}")
    except Exception as e:
        logging.error("Error creating event: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error creating event: {str(e)}")

    return ResponseModel(message="Event created successfully", eventInfo=event)


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

        tiers_raw = data.get("ticketTiers", [])
        tiers: list[EventTiers] = []
        for t in tiers_raw:
            if isinstance(t, dict):
                tiers.append(EventTiers(**t))
        event = Event(
            event_id=doc.id,
            event_link=data.get("eventLink", ""),
            event_title=data.get("title", ""),
            date_start=data.get("startDate", dt.datetime.utcnow()),
            date_end=data.get("endDate", dt.datetime.utcnow()),
            description=data.get("description", ""),
            host_address=data.get("hostAddress", ""),
            image_url=data.get("imageUrl"),
            status=data.get("status", ""),
            ticket_tiers=tiers,
            created_at=data.get("createdAt", dt.datetime.utcnow()),
        )

        return ResponseModel(message="Event retrieved successfully", eventInfo=event)

    except HTTPException:
        raise

    except Exception as e:
        logging.error("Error retrieving event by ID: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving event: {str(e)}")
    

def generate_signature(payload: dict) -> str:
    """Generate a simple signature for the QR code payload."""
    import hashlib
    payload_str = json.dumps(payload, sort_keys=True)
    return hashlib.sha256(payload_str.encode()).hexdigest()


@router.post("/joinEvent/{event_id}/{wallet_address}")
def join_event(event_id: str, wallet_address: str, payload: JoinEventPayload):
    """Add a wallet address to an event's participants, generates and stores QR-code."""
    
    try:
        # Generate unique ticket ID first
        ticket_id = str(uuid.uuid4())
        
        # Create QR payload with ticket information (including ticketId)
        qr_payload = {
            "eventTitle": payload.eventTitle,
            "eventId": event_id,
            "walletAddress": wallet_address,
            "ticketId": ticket_id,
            "purchasedAt": dt.datetime.now().isoformat(),
            "priceBought": payload.priceBought,
            "tierName": payload.tierName,
            "status": "active",
        }

        # Generate signature for security
        qr_signature = generate_signature(qr_payload)
        qr_payload["signature"] = qr_signature

        # Generate QR code
        qr_string = json.dumps(qr_payload)
        qr_code = qr.QRCode(
            version=1,
            error_correction=qr.ERROR_CORRECT_H,
            box_size=10,
            border=4,
        )
        qr_code.add_data(qr_string)
        qr_code.make(fit=True)
        
        # Create QR code image (PIL Image object)
        img = qr_code.make_image(fill_color="black", back_color="white")
        
        # Convert PIL image to bytes
        img_byte_arr = BytesIO()
        img.save(img_byte_arr, 'PNG')  # PIL Image.save takes format as positional arg
        img_byte_arr.seek(0)
        
        # Generate filename
        qr_filename = f"{ticket_id}.png"
        
        # Upload to Firebase Storage
        bucket = storage_bucket
        blob_path = f"qrcodes/events/{event_id}/{wallet_address}/{qr_filename}"
        blob = bucket.blob(blob_path)
        
        blob.upload_from_file(
            img_byte_arr,
            content_type='image/png'
        )
        
        # Make the QR code publicly accessible
        blob.make_public()
        qr_url = blob.public_url
        
        # Prepare ticket document for Firestore
        ticket_doc = {
            **qr_payload,
            "ticketId": ticket_id,
            "qrCodeUrl": qr_url,
            "qrCodePath": blob_path,
            "purchasedAtTimestamp": dt.datetime.now(),  # Keep datetime for queries
            # purchasedAt from qr_payload (ISO string) is preserved for signature verification
        }
        
        # Save ticket to Firestore
        db.collection("Tickets").document(ticket_id).set(ticket_doc)

        # Update ticket tier counts
        event_ref = db.collection("Events").document(event_id)
        event_doc = event_ref.get()
        
 

        if event_doc.exists:
            event_data = event_doc.to_dict()
            if event_data is None:
                raise HTTPException(status_code=500, detail="Event data is corrupted.")
            
            ticket_tiers = event_data.get("ticketTiers", [])
            
            # Find and update the matching tier
            for tier in ticket_tiers:
                if tier.get("tierName") == payload.tierName:
                    # Decrement available tickets and increment sold count
                    tier["ticketCount"] = max(0, tier.get("ticketCount", 0) - 1)
                    tier["ticketsSold"] = tier.get("ticketsSold", 0) + 1
                    break
            
            # Update the event in Firestore
            event_ref.update({"ticketTiers": ticket_tiers})
        
        return {
            "success": True,
            "message": "Successfully joined event and generated ticket",
            "ticketId": ticket_id,
            "qrCodeUrl": qr_url,
            "eventId": event_id,
            "walletAddress": wallet_address,
            "tierName": payload.tierName,
            "priceBought": payload.priceBought
        }
        
    except Exception as e:
        logging.error("Error joining event: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error joining event: {str(e)}")


@router.get("/getTicket/{ticket_id}")
def get_ticket(ticket_id: str):
    """Retrieve a ticket by its ID."""
    try:
        doc_ref = db.collection("Tickets").document(ticket_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        
        ticket_data = doc.to_dict()
        return {
            "success": True,
            "ticket": ticket_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error retrieving ticket: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error retrieving ticket: {str(e)}")


@router.post("/verifyTicket/{event_id}")
def verify_ticket(event_id: str, qr_data: dict):
    """Verify a ticket's authenticity using its signature and check it in."""
    try:
        # Handle nested qr_data if sent from frontend
        if "qr_data" in qr_data:
            qr_data = qr_data["qr_data"]
        
        signature = qr_data.get("signature")
        if not signature:
            raise HTTPException(status_code=400, detail="Missing signature")
        
        # Get ticket ID first to fetch original data
        ticket_id = qr_data.get("ticketId")
        if not ticket_id:
            raise HTTPException(status_code=400, detail="Missing ticket ID")
        
        doc_ref = db.collection("Tickets").document(ticket_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Ticket not found")
        
        ticket_data = doc.to_dict()
        if not ticket_data:
            raise HTTPException(status_code=500, detail="Ticket data is corrupted")
        
        # Verify ticket belongs to this event
        ticket_event_id = ticket_data.get("eventId")
        if ticket_event_id != event_id:
            raise HTTPException(
                status_code=400,
                detail="Ticket does not belong to this event."
            )
        
        # Handle purchasedAt field (might be string or Firestore timestamp for old tickets)
        purchased_at = ticket_data.get("purchasedAt")
        if isinstance(purchased_at, str):
            # New tickets - already ISO string
            purchased_at_str = purchased_at
        elif purchased_at and hasattr(purchased_at, "isoformat"):
            # Old tickets - datetime object
            purchased_at_str = purchased_at.isoformat()
        elif purchased_at and hasattr(purchased_at, "to_datetime"):
            # Old tickets - Firestore timestamp
            purchased_at_str = purchased_at.to_datetime().isoformat()
        else:
            # Fallback
            purchased_at_str = str(purchased_at) if purchased_at else ""
        
        # Build the original payload from stored ticket data
        original_payload = {
            "eventTitle": ticket_data.get("eventTitle"),
            "eventId": ticket_data.get("eventId"),
            "walletAddress": ticket_data.get("walletAddress"),
            "ticketId": ticket_data.get("ticketId"),
            "purchasedAt": purchased_at_str,
            "priceBought": ticket_data.get("priceBought"),
            "tierName": ticket_data.get("tierName"),
            "status": ticket_data.get("status"),
        }
        
        # Generate expected signature from original data
        expected_signature = generate_signature(original_payload)
        
        if signature != expected_signature:
            raise HTTPException(status_code=400, detail="Invalid ticket signature")
        
        current_status = ticket_data.get("status")
        
        if current_status == "checkedIn":
            raise HTTPException(status_code=400, detail="Ticket has already been checked in")
        
        if current_status != "active":
            raise HTTPException(status_code=400, detail=f"Ticket is not active. Current status: {current_status}")
        
        # Update status to checkedIn and add timestamp
        doc_ref.update({
            "status": "checkedIn",
            "checkedInAt": dt.datetime.now()
        })

        return {
            "status": "checkedIn",
            "valid": True,
            "message": "Ticket is valid and checked in successfully",
            "data": qr_data
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error verifying ticket: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error verifying ticket: {str(e)}")


@router.post("/verifyTicketById/{ticket_id}/{event_id}")
def verify_ticket_by_id(ticket_id: str, event_id: str):
    """Manually verify a ticket using its ticket ID, ensuring it belongs to the specified event."""

    if ticket_id is None or ticket_id.strip() == "":
        raise HTTPException(status_code=400, detail="Ticket ID is required.")
    
    if event_id is None or event_id.strip() == "":
        raise HTTPException(status_code=400, detail="Event ID is required.")
    
    try:
        # Check if event exists
        event_check = db.collection("Events").document(event_id).get()
        if not event_check.exists:
            raise HTTPException(status_code=404, detail="Event not found.")

        # Get ticket
        doc_ref = db.collection("Tickets").document(ticket_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        
        ticket_data = doc.to_dict()
        if not ticket_data:
            raise HTTPException(status_code=500, detail="Ticket data is corrupted.")
        
        # Verify ticket belongs to this event
        ticket_event_id = ticket_data.get("eventId")
        if ticket_event_id != event_id:
            raise HTTPException(
                status_code=400,
                detail="Ticket does not belong to this event."
            )
        
        current_status = ticket_data.get("status")
        
        # Check if already checked in
        if current_status == "checkedIn":
            raise HTTPException(
                status_code=400,
                detail="Ticket has already been checked in"
            )
        
        # Check if ticket is active
        if current_status != "active":
            raise HTTPException(
                status_code=400,
                detail=f"Ticket is not active. Current status: {current_status}"
            )
        
        # Update status to checkedIn and add timestamp
        doc_ref.update({
            "status": "checkedIn",
            "checkedInAt": dt.datetime.now()
        })
        
        # Get updated ticket data
        updated_ticket = doc_ref.get().to_dict()
        
        return {
            "valid": True,
            "message": "Ticket verified and checked in successfully",
            "ticketId": ticket_id,
            "eventId": event_id,
            "status": "checkedIn",
            "ticket": updated_ticket
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error verifying ticket by ID: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error verifying ticket by ID: {str(e)}")
    

@router.post("/setImage-url")
async def set_event_image_url(file:UploadFile = File(...)):
    """Set or update the image URL for an event by uploading a new image."""
    try:
        image_bytes = await file.read()
        time_now = dt.datetime.now().strftime("%Y%m%d%H%M%S")
        filepath = f"uploads/{time_now}_{file.filename}"

        blob = storage_bucket.blob(filepath)

        if not file.content_type:
            return {"error": "file content type is missing."}
        blob.upload_from_string(image_bytes, content_type=file.content_type)
        blob.make_public()
        image_url = blob.public_url

        return {
            "imageUrl": image_url
        }
    except Exception as e:
        logging.error("Error setting event image URL: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error setting event image URL: {str(e)}")
    

@router.get("/attendees/{eventId}")
def get_event_attendees(eventId: str):
    """Retrieve all attendees for a given event ID."""
    try:
        query = db.collection("Tickets")\
        .where("eventId", "==", eventId)\
        .get()

        attendees = []
        for doc in query:
            data = doc.to_dict()
            if not data:
                continue
            attendees.append(data)
        return {"event_id": eventId, "attendees": attendees}

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving attendees: {str(e)}")


@router.post("/updateTicketStatus/{ticketId}")
def update_ticket_status(ticketId: str, ticket_payload: updateTicketStatusPayload):
    """Update the status of a ticket."""
    try:
        ticket_ref = db.collection("Tickets").document(ticketId)
        ticket_doc = ticket_ref.get()
        
        if not ticket_doc.exists:
            raise HTTPException(status_code=404, detail="Ticket not found.")
        
        ticket_ref.update({"status": ticket_payload.new_status})
        
        return {
            "success": True,
            "message": f"Ticket status updated to {ticket_payload.new_status}",
            "ticketId": ticketId,
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error updating ticket status: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error updating ticket status: {str(e)}")
    

@router.get("/downloadTicketQr/{ticket_id}")
def download_ticket_qr(ticket_id: str):
    """Download the QR code image for a given ticket ID."""
    try:
        doc_ref = db.collection("Tickets").document(ticket_id)
        doc = doc_ref.get()
        
        if not doc.exists:
            raise HTTPException(status_code=404, detail="Ticket not found.")    
        
        ticket_data = doc.to_dict()
        if not ticket_data:
            raise HTTPException(status_code=500, detail="Ticket data is corrupted.")
        
        qr_code_path = ticket_data.get("qrCodePath")
        if not qr_code_path:
            raise HTTPException(status_code=404, detail="QR code path not found for this ticket.")
        
        bucket = storage_bucket
        blob = bucket.blob(qr_code_path)
        
        if not blob.exists():
            raise HTTPException(status_code=404, detail="QR code image not found in storage.")
        
        qr_image_url = blob.public_url
        
        return {
            "ticketId": ticket_id,
            "qrCodeUrl": qr_image_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error downloading ticket QR code: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error downloading ticket QR code: {str(e)}")


@router.get("/downloadAttendeesList/{event_id}")
def download_attendees_list(event_id: str):
    """Generate and provide a download link for the attendees list of a given event (xlsx)."""
    try:
        import pandas as pd
        from io import BytesIO

        query = db.collection("Tickets")\
        .where("eventId", "==", event_id)\
        .get()

        attendees = []
        for doc in query:
            data = doc.to_dict()
            if not data:
                continue
            
            # Convert Firestore timestamps to timezone-unaware datetime objects
            for key, value in data.items():
                if hasattr(value, 'to_datetime'):
                    # Firestore timestamp - convert to timezone-unaware datetime
                    data[key] = value.to_datetime().replace(tzinfo=None)
                elif isinstance(value, dt.datetime) and value.tzinfo is not None:
                    # Timezone-aware datetime - convert to timezone-unaware
                    data[key] = value.replace(tzinfo=None)
            
            attendees.append(data)
        
        if not attendees:
            raise HTTPException(status_code=404, detail="No attendees found for this event.")
        
        df = pd.DataFrame(attendees)
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='openpyxl') as writer:
            df.to_excel(writer, index=False, sheet_name='Attendees')
        
        excel_buffer.seek(0)
        
        # Upload to Firebase Storage
        bucket = storage_bucket
        blob_path = f"events/{event_id}/attendees_list.xlsx"
        blob = bucket.blob(blob_path)
        
        blob.upload_from_file(
            excel_buffer,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        )
        
        blob.make_public()
        download_url = blob.public_url
        
        return {
            "eventId": event_id,
            "attendeesCount": len(attendees),
            "downloadUrl": download_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logging.error("Error downloading attendees list: %s", traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"Error downloading attendees list: {str(e)}")