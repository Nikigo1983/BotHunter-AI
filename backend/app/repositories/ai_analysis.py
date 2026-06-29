from sqlalchemy.ext.asyncio import AsyncSession

from app.models.ai_analysis import AIAnalysis
from app.repositories.base import BaseRepository


class AIAnalysisRepository(BaseRepository[AIAnalysis]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session, AIAnalysis)
