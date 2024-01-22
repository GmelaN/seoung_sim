import logging

from simpy.core import SimTime


class SeoungSimLogger:
    def __init__(self, logger_name: str, level: int=logging.DEBUG):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(level)
        self.level = level

        loggingHandler = logging.StreamHandler()
        loggingHandler.setLevel(level)

        loggingHandler.setFormatter(
            logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        )

        self.logger.addHandler(loggingHandler)

    def log(self, sim_time: SimTime, msg: str, level: int = None, newline: str = ""):

        full_message = f"{newline}[SimTime: {sim_time:.10f}] {msg}"
        self.logger.log(level=self.level if level is None else level, msg=full_message)
