#!/usr/bin/env python3
"""
Daily cleanup script for GDPR compliance
Automatically removes expired candidate data and audit logs
"""

import asyncio
import os
import sys
from datetime import datetime, timedelta
import aioredis
import asyncpg
from loguru import logger

# Configure logging
logger.add("/cleanup/logs/cleanup.log", rotation="1 week", retention="4 weeks")

class GDPRCleanupService:
    def __init__(self):
        self.redis_url = os.getenv('REDIS_URL', 'redis://redis:6379')
        self.database_url = os.getenv('DATABASE_URL')

    async def run_cleanup(self):
        """Run complete GDPR cleanup process"""
        logger.info("Starting GDPR cleanup process")

        try:
            # Cleanup Redis data
            redis_cleaned = await self._cleanup_redis()

            # Cleanup PostgreSQL data
            postgres_cleaned = await self._cleanup_postgres()

            # Log summary
            logger.info(f"Cleanup completed: Redis={redis_cleaned}, Postgres={postgres_cleaned}")

        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            sys.exit(1)

    async def _cleanup_redis(self):
        """Cleanup expired Redis data"""
        try:
            redis = aioredis.from_url(self.redis_url)

            # Find all GDPR data keys
            keys = await redis.keys("gdpr_data:*")
            cleaned_count = 0

            for key in keys:
                ttl = await redis.ttl(key)
                if ttl <= 0:  # Expired
                    await redis.delete(key)
                    cleaned_count += 1

            # Cleanup old notifications
            notification_keys = await redis.keys("notification:*")
            for key in notification_keys:
                ttl = await redis.ttl(key)
                if ttl <= 0:
                    await redis.delete(key)
                    cleaned_count += 1

            await redis.close()
            logger.info(f"Redis cleanup: removed {cleaned_count} expired entries")
            return cleaned_count

        except Exception as e:
            logger.error(f"Redis cleanup error: {e}")
            return 0

    async def _cleanup_postgres(self):
        """Cleanup expired PostgreSQL data"""
        try:
            conn = await asyncpg.connect(self.database_url)

            # Delete expired candidates and related data
            result = await conn.execute("""
                DELETE FROM candidates
                WHERE expires_at < CURRENT_TIMESTAMP
            """)
            candidates_deleted = int(result.split()[-1])

            # Delete old audit logs (30 days retention)
            result = await conn.execute("""
                DELETE FROM audit_logs
                WHERE retention_until < CURRENT_TIMESTAMP
            """)
            audit_deleted = int(result.split()[-1])

            # Delete old notifications (7 days retention)
            week_ago = datetime.now() - timedelta(days=7)
            result = await conn.execute("""
                DELETE FROM notifications
                WHERE created_at < $1
            """, week_ago)
            notifications_deleted = int(result.split()[-1])

            await conn.close()

            total_deleted = candidates_deleted + audit_deleted + notifications_deleted
            logger.info(f"Postgres cleanup: candidates={candidates_deleted}, audit={audit_deleted}, notifications={notifications_deleted}")

            return total_deleted

        except Exception as e:
            logger.error(f"Postgres cleanup error: {e}")
            return 0

async def main():
    """Main cleanup function"""
    cleanup_service = GDPRCleanupService()
    await cleanup_service.run_cleanup()

if __name__ == "__main__":
    asyncio.run(main())
