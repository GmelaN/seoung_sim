import logging

from simpy.core import SimTime


class SeoungSimLogger:
    def __init__(self, logger_name: str, level: int=logging.DEBUG):
        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(level)
        self.level = level

        self.loggingHandler = logging.StreamHandler()
        self.loggingHandler.setLevel(level)


        # self.default_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.default_formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
        self.newline_formatter = logging.Formatter(
            '=' * 200
            + '\n'
            # + '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            + '%(name)s - %(levelname)s - %(message)s'
            + '\n'
            + '=' * 200
        )

        self.loggingHandler.setFormatter(self.default_formatter)
        self.logger.addHandler(self.loggingHandler)


    def log(self, sim_time: SimTime, msg: str, level: int = None, newline: str = "") -> None:
        return
        full_message = f"[SimTime: {sim_time:.10f}] {msg}"

        if len(newline) != 0:
            self.loggingHandler.setFormatter(self.newline_formatter)
            self.logger.log(level=self.level if level is None else level, msg=full_message)
            self.loggingHandler.setFormatter(self.default_formatter)

            return

        self.logger.log(level=self.level if level is None else level, msg=full_message)
