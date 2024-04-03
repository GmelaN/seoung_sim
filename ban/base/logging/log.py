import logging

from simpy.core import SimTime

from ban.config.JSONConfig import JSONConfig


class SeoungSimLogger:
    def __init__(self, logger_name: str, level: int=logging.INFO):
        level = JSONConfig.get_config("log_level").lower()

        if level == "debug":
            self.level = logging.DEBUG
        elif level == "info":
            self.level = logging.INFO
        elif level == "warn" or level == "warning":
            self.level = logging.WARN
        elif level == "critical":
            self.level = logging.CRITICAL
        else:
            self.level = 999_999


        self.logger = logging.getLogger(logger_name)
        self.logger.setLevel(self.level)

        self.loggingHandler = logging.StreamHandler()
        self.loggingHandler.setLevel(self.level)




        # self.default_formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        self.default_formatter = logging.Formatter('%(name)-10s%(levelname)-10s%(message)s')
        self.newline_formatter = logging.Formatter(
            '\n' + '=' * 200
            + '\n'
            # + '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            + '%(name)-10s%(levelname)-10s%(message)s'
            + '\n'
            + '=' * 200
        )

        self.loggingHandler.setFormatter(self.default_formatter)
        self.logger.addHandler(self.loggingHandler)


    def log(self, sim_time: SimTime, msg: str, level: int = logging.NOTSET, newline: str = "") -> None:
        # if level is None or level != logging.CRITICAL:
        #     return

        if level < self.level:
            return


        full_message = f"+{sim_time:.6f} {msg}"

        if len(newline) != 0:
            self.loggingHandler.setFormatter(self.newline_formatter)
            self.logger.log(level=self.level if level is None else level, msg=full_message)
            self.loggingHandler.setFormatter(self.default_formatter)

            return

        self.logger.log(level=self.level if level is None else level, msg=full_message)
