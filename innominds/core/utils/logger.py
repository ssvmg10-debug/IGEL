###########################################################
# Title        : Logging & Allure Reporting Utilities
# Description  : Centralized logging factory providing
#                rotating file and console log handlers,
#                environment-driven configuration, and
#                helper utilities to attach log messages
#                into Allure test reports.
#
# Prerequisites:
#   - Python 3.10+
#   - logging (standard library)
#   - allure-pytest
#   - Pytest execution environment
#
# Author       : Sai Arokala
# Email        : Sai.Arakala_ext@igel.com
# Created On   : Feb-2026
# Version      : 1.2
############################################################


import logging
import os
import datetime
import allure

# =========================================================
# CONFIG
# =========================================================

LOG_DIR = os.getenv("LOG_DIR", "reports/logs")
os.makedirs(LOG_DIR, exist_ok=True)

RUN_TIMESTAMP = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
LOG_PATH = os.path.join(LOG_DIR, f"{RUN_TIMESTAMP}.log")

FILE_LOG_LEVEL = logging.DEBUG  # always capture everything
CONSOLE_PASS_LEVEL = logging.INFO  # show only info during normal run

LOG_FORMAT = (
    "%(asctime)s | %(levelname)-8s | %(name)s | "
    "%(filename)s:%(funcName)s:%(lineno)d | %(message)s"
)

# =========================================================
# ROOT LOGGER INIT
# =========================================================

_root_initialized = False


def _init_root_logger():
    global _root_initialized
    if _root_initialized:
        return

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    formatter = logging.Formatter(LOG_FORMAT)

    # -------- FILE HANDLER (FULL TRACE) ----------
    file_handler = logging.FileHandler(LOG_PATH, mode="w", encoding="utf-8")
    file_handler.setLevel(FILE_LOG_LEVEL)
    file_handler.setFormatter(formatter)

    # -------- CONSOLE HANDLER (CLEAN OUTPUT) ----------
    console_handler = logging.StreamHandler()
    console_handler.setLevel(CONSOLE_PASS_LEVEL)
    console_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(console_handler)

    _root_initialized = True


def get_logger(name: str):
    _init_root_logger()
    return logging.getLogger(name)


# =========================================================
# STEP LOG CAPTURE (SMART FILTER)
# =========================================================

class StepLogBuffer(logging.Handler):
    """
    Captures logs for ONE step.
    Shows different levels based on pass/fail.
    """

    def __init__(self):
        super().__init__()
        self.records = []

        self.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        ))

    def emit(self, record):
        self.records.append((record.levelno, self.format(record)))

    def attach(self, step_name, failed: bool):

        if not self.records:
            return

        if failed:
            # show everything
            logs = [msg for lvl, msg in self.records]
        else:
            # show only INFO
            logs = [msg for lvl, msg in self.records if lvl == logging.INFO]

        if not logs:
            return

        allure.attach(
            "\n".join(logs),
            name=f"{step_name} Logs",
            attachment_type=allure.attachment_type.TEXT
        )

        self.records.clear()


# =========================================================
# STEP CONTEXT MANAGER (USE THIS)
# =========================================================
class StepLogCapture(logging.Handler):
    """
    Collect logs generated during one step
    and attach them to Allure.
    """

    def __init__(self, step_name: str):
        super().__init__()
        self.step_name = step_name
        self.records = []

        self.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)s | %(message)s"
        ))

    def emit(self, record):
        self.records.append(self.format(record))

    def attach(self, status: str):
        if not self.records:
            return

        allure.attach(
            "\n".join(self.records),
            name=f"{self.step_name} Logs ({status})",
            attachment_type=allure.attachment_type.TEXT
        )


class step_log_context:
    """
    Capture logs during a step and attach to Allure.
    Uses ROOT logger automatically.
    """

    def __init__(self, step_name: str):
        self.step_name = step_name
        self.logger = logging.getLogger()   # auto root logger
        self.handler = StepLogCapture(step_name)

    def __enter__(self):
        self.logger.addHandler(self.handler)
        return self.handler

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.logger.removeHandler(self.handler)

        status = "FAILED" if exc_type else "PASSED"
        self.handler.attach(status)


# =========================================================
# FULL LOG ATTACH PER TEST
# =========================================================

def attach_current_log_file(test_name: str):
    try:
        if not os.path.exists(LOG_PATH):
            return

        with open(LOG_PATH, "r", encoding="utf-8") as f:
            content = f.read()

        if content.strip():
            allure.attach(
                content,
                name=f"{test_name} - Full Execution Log",
                attachment_type=allure.attachment_type.TEXT
            )
    except Exception as e:
        print("Failed attaching log:", e)
