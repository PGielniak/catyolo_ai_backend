import os
import logging

class LogService:
    def __init__(self, logger: logging.Logger):
        self.log_path = os.getenv("LOG_FILE_PATH")
        self.logger = logger
        if not self.log_path:
            os.makedirs("logs", exist_ok=True)

    def get_logs(self,n_lines: int = 100) -> list[str]:
        with open(self.log_path, 'r') as f:
            lines = f.readlines()
        return lines[-n_lines:]

    def set_log_level(self, level: str):
        self.logger.setLevel(level)

    def get_log_level(self) -> str:
        log_level = self.logger.getEffectiveLevel()
        # convert log level to string
        return logging.getLevelName(log_level)
