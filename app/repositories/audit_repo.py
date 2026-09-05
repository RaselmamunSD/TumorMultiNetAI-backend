from typing import List, Tuple
from sqlalchemy import select, desc, func
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    def __init__(self, db: AsyncSession):
        super().__init__(AuditLog, db)

    async def get_logs_paginated(self, limit: int = 50, offset: int = 0) -> Tuple[List[AuditLog], int]:
        count_query = select(func.count(AuditLog.id))
        count_res = await self.db.execute(count_query)
        total = count_res.scalar() or 0

        query = select(AuditLog).order_by(desc(AuditLog.created_at)).limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all()), total
