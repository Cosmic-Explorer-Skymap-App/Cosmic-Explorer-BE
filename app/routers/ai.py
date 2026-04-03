import os
import datetime
from google import genai
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import User
from ..schemas import AstrologyAIRequest, AstrologyAIResponse
from ..dependencies import get_current_user

router = APIRouter(prefix="/api/ai", tags=["AI"])

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

VALID_SIGNS = {
    "Koç", "Boğa", "İkizler", "Yengeç", "Aslan", "Başak",
    "Terazi", "Akrep", "Yay", "Oğlak", "Kova", "Balık",
    "Aries", "Taurus", "Gemini", "Cancer", "Leo", "Virgo",
    "Libra", "Scorpio", "Sagittarius", "Capricorn", "Aquarius", "Pisces",
}

@router.post("/astrology", response_model=AstrologyAIResponse)
def get_astrology_reading(
    request: AstrologyAIRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if request.sign not in VALID_SIGNS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Geçersiz burç adı.",
        )

    now = datetime.datetime.now(datetime.timezone.utc)
    last_query = current_user.last_ai_query_at
    if last_query:
        if last_query.tzinfo is None:
            last_query = last_query.replace(tzinfo=datetime.timezone.utc)
        if last_query.date() == now.date():
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Günlük burç yorumunuzu zaten aldınız. Yarın tekrar gelin!",
            )

    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI servisi şu an kullanılamıyor.",
        )

    prompt = (
        f"Sen profesyonel bir astrolog ve gökbilimcisin.\n"
        f"Kullanıcının burcu: {request.sign}.\n"
        + (f"Doğum tarihi: {request.birth_date}\n" if request.birth_date else "")
        + (
            f"Kullanıcının sorusu: {request.question}\n"
            if request.question
            else "Günlük genel burç yorumu talep ediyor.\n"
        )
        + "\nLütfen bu kullanıcıya DETAYLI, TATMIN EDICI ve samimi bir astroloji yorumu yap. "
        "Gezegenlerin konumları, enerjiler ve günün getireceği fırsatlar hakkında bilgi ver. "
        "Cevabın en az 3 paragraf olsun ve okuyucuyu motive etsin. "
        "Dili Türkçe kullan."
    )

    try:
        client = genai.Client(api_key=GEMINI_API_KEY)
        response = client.models.generate_content(model=GEMINI_MODEL, contents=prompt)
        prediction_text = response.text.strip()

        if not prediction_text:
            raise ValueError("Gemini boş yanıt döndürdü.")

        current_user.last_ai_query_at = now
        db.commit()

        return AstrologyAIResponse(prediction=prediction_text, success=True)

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"AI servisi hatası: {str(e)}",
        )
