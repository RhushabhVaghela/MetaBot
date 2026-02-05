import sqlite3
import os
import shutil
import zlib
import logging
from typing import Optional
from datetime import datetime
from cryptography.fernet import Fernet  # type: ignore

logger = logging.getLogger("megabot.memory.backup")


class MemoryBackupManager:
    """Handles database backup and restore operations with encryption and compression."""

    def __init__(self, db_path: str, backup_dir: Optional[str] = None):
        self.db_path = db_path
        self.backup_dir = backup_dir or os.path.join(
            os.path.dirname(db_path), "backups"
        )
        os.makedirs(self.backup_dir, exist_ok=True)

    async def create_backup(self, encryption_key: Optional[str] = None) -> str:
        """Create a compressed and encrypted backup of the memory database."""
        try:
            key = encryption_key or os.environ.get("MEGABOT_BACKUP_KEY")
            if not key:
                return "Error: No encryption key provided or found in environment."

            fernet = Fernet(key.encode() if isinstance(key, str) else key)

            # 1. Create a temporary copy to avoid locking issues
            temp_db = f"{self.db_path}.tmp"
            shutil.copy2(self.db_path, temp_db)

            # 2. Read and compress
            with open(temp_db, "rb") as f:
                data = f.read()

            compressed_data = zlib.compress(data)
            encrypted_data = fernet.encrypt(compressed_data)

            # 3. Save to backup dir
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_file = os.path.join(
                self.backup_dir, f"memory_backup_{timestamp}.enc"
            )

            with open(backup_file, "wb") as f:
                f.write(encrypted_data)

            os.remove(temp_db)
            logger.info(f"Database backup created: {backup_file}")
            return f"Backup created successfully: {os.path.basename(backup_file)}"
        except Exception as e:
            logger.error(f"Backup failed: {e}")
            return f"Error: Backup failed: {e}"

    async def restore_backup(
        self, backup_file: str, encryption_key: Optional[str] = None
    ) -> str:
        """Restore database from an encrypted backup."""
        try:
            key = encryption_key or os.environ.get("MEGABOT_BACKUP_KEY")
            if not key:
                return "Error: No encryption key provided or found in environment."

            fernet = Fernet(key.encode() if isinstance(key, str) else key)

            # 1. Read and decrypt backup
            backup_path = os.path.join(self.backup_dir, backup_file)
            if not os.path.exists(backup_path):
                return f"Error: Backup file not found: {backup_file}"

            with open(backup_path, "rb") as f:
                encrypted_data = f.read()

            decrypted_data = fernet.decrypt(encrypted_data)
            decompressed_data = zlib.decompress(decrypted_data)

            # 2. Create temporary restored database
            temp_db = f"{self.db_path}.restored"
            with open(temp_db, "wb") as f:
                f.write(decompressed_data)

            # 3. Validate the restored database
            try:
                with sqlite3.connect(temp_db) as conn:
                    # Test basic queries
                    conn.execute("SELECT COUNT(*) FROM memories").fetchone()
                    conn.execute("SELECT COUNT(*) FROM chat_history").fetchone()
                    conn.execute("SELECT COUNT(*) FROM user_identities").fetchone()
            except Exception as e:
                os.remove(temp_db)
                return f"Error: Restored database is corrupted: {e}"

            # 4. Replace current database
            backup_current = f"{self.db_path}.bak"
            shutil.move(self.db_path, backup_current)
            shutil.move(temp_db, self.db_path)

            logger.info(f"Database restored from backup: {backup_file}")
            return f"Database restored successfully from {backup_file}. Previous database backed up as .bak"
        except Exception as e:
            logger.error(f"Restore failed: {e}")
            return f"Error: Restore failed: {e}"

    async def list_backups(self) -> list:
        """List all available backup files."""
        try:
            if not os.path.exists(self.backup_dir):
                return []

            files = []
            for filename in os.listdir(self.backup_dir):
                if filename.startswith("memory_backup_") and filename.endswith(".enc"):
                    filepath = os.path.join(self.backup_dir, filename)
                    stat = os.stat(filepath)
                    files.append(
                        {
                            "filename": filename,
                            "size": stat.st_size,
                            "created": datetime.fromtimestamp(
                                stat.st_ctime
                            ).isoformat(),
                        }
                    )
            return sorted(files, key=lambda x: x["created"], reverse=True)
        except Exception as e:
            logger.error(f"Error listing backups: {e}")
            return []

    async def cleanup_old_backups(self, keep_days: int = 30) -> int:
        """Remove backup files older than specified days."""
        try:
            cutoff_time = datetime.now().timestamp() - (keep_days * 24 * 60 * 60)
            removed_count = 0

            for filename in os.listdir(self.backup_dir):
                if filename.startswith("memory_backup_") and filename.endswith(".enc"):
                    filepath = os.path.join(self.backup_dir, filename)
                    if os.path.getctime(filepath) < cutoff_time:
                        os.remove(filepath)
                        removed_count += 1
                        logger.info(f"Removed old backup: {filename}")

            return removed_count
        except Exception as e:
            logger.error(f"Error cleaning up old backups: {e}")
            return 0

    async def get_backup_stats(self) -> dict:
        """Get statistics about backup files."""
        try:
            backups = await self.list_backups()
            if not backups:
                return {
                    "total_backups": 0,
                    "total_size": 0,
                    "oldest": None,
                    "newest": None,
                }

            total_size = sum(b["size"] for b in backups)
            return {
                "total_backups": len(backups),
                "total_size": total_size,
                "oldest": backups[-1]["created"] if backups else None,
                "newest": backups[0]["created"] if backups else None,
            }
        except Exception as e:
            logger.error(f"Error getting backup stats: {e}")
            return {"error": str(e)}
