import dataclasses
import enum
import logging
import math
import random
from typing import List

import simpy

from ban.base.mobility import BodyPosition, MobilityModel

random.seed(42)

from ban.base.logging.log import SeoungSimLogger

MOVEMENT_CYCLE = 0.5

class MovementPhase(enum.Enum):
    PHASE_0: int = 0
    PHASE_1: int = 1

@dataclasses.dataclass
class MovementInfo:
    # Phase의 수 -> 전체 페이즈의 수도 알 수 있음
    phases: tuple[MovementPhase, ...] = tuple(MovementPhase)

    # 각 페이즈의 기간 정보 -> 한 전체 주기의 정보도 알 수 있음 (seconds)
    phase_duration: tuple[float, ...] = tuple(MOVEMENT_CYCLE for _ in range(len(phases)))


class MobilityHelper:
    logger = SeoungSimLogger(logger_name="MOBILITY", level=logging.DEBUG)

    transaction_ablility = {
        MovementPhase.PHASE_0: {
            BodyPosition.BODY: (True, True, True, True, True, True, True, True), # coordinator

            BodyPosition.LEFT_ELBOW: (True, True, True, True, True, True, True, False),
            BodyPosition.LEFT_WRIST: (True, True, True, True, True, True, True, False),
            BodyPosition.RIGHT_ANKLE: (True, True, True, True, True, True, True, False),
            BodyPosition.RIGHT_KNEE: (True, True, True, True, True, True, True, False),

            BodyPosition.RIGHT_ELBOW: (False, False, False, False, False, False, False, True),
            BodyPosition.RIGHT_WRIST: (False, False, False, False, False, False, False, True),
            BodyPosition.LEFT_ANKLE: (False, False, False, False, False, False, False, True),
            BodyPosition.LEFT_KNEE: (False, False, False, False, False, False, False, True),
        },
        MovementPhase.PHASE_1: {
            BodyPosition.BODY: (True, True, True, True, True, True, True, True), # coordinator
            
            BodyPosition.LEFT_ELBOW: (False, False, False, False, False, False, False, True),
            BodyPosition.LEFT_WRIST: (False, False, False, False, False, False, False, True),
            BodyPosition.RIGHT_ANKLE: (False, False, False, False, False, False, False, True),
            BodyPosition.RIGHT_KNEE: (False, False, False, False, False, False, False, True),

            BodyPosition.RIGHT_ELBOW: (True, True, True, True, True, True, True, False),
            BodyPosition.RIGHT_WRIST: (True, True, True, True, True, True, True, False),
            BodyPosition.LEFT_ANKLE: (True, True, True, True, True, True, True, False),
            BodyPosition.LEFT_KNEE: (True, True, True, True, True, True, True, False),
        }
    }


    def __init__(self, env):
        self.env:simpy.Environment = env

        self.movement_cycle = MOVEMENT_CYCLE     # seconds
        self.mobility_list: List[MobilityModel] = list()

        # 현재 모빌리티 정보
        self.current_phase = MovementPhase.PHASE_0
        self.phase_info = MovementInfo()


    def can_transaction(self, sender_id: int, time_slot: int) -> bool:
        return MobilityHelper.transaction_ablility[self.current_phase][self.mobility_list[sender_id].get_body_position()][time_slot]

    def change_cycle(self, env):
        if self.current_phase == MovementPhase.PHASE_0:
            MobilityHelper.logger.log(
                sim_time=self.env.now,
                msg=f"Mobility Phase is now PHASE_1",
                level=logging.INFO
            )
            self.current_phase = MovementPhase.PHASE_1

        else:
            MobilityHelper.logger.log(
                sim_time=self.env.now,
                msg=f"Mobility Phase is now PHASE_0",
                level=logging.INFO
            )
            self.current_phase = MovementPhase.PHASE_0

        ev = self.env.event()
        ev.callbacks.append(self.change_cycle)
        ev._ok = True

        self.env.schedule(ev, delay=0.5 - 0.000001)

    def add_mobility_list(self, mob: MobilityModel):
        self.mobility_list.append(mob)