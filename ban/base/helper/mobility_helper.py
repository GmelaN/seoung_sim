import dataclasses
import enum
import math
import random

from ban.base.mobility import MobilityModel, BodyPosition
from ban.base.positioning import Vector

MOVEMENT_CYCLE = 0.5                # seconds
RANGE = 0.1


class MovementPhase(enum.Enum):
    PHASE_0: int = 0
    PHASE_1: int = 1
    # PHASE_2: int = 2


@dataclasses.dataclass
class MovementInfo:
    # Phase의 수 -> 전체 페이즈의 수도 알 수 있음
    phases: tuple[MovementPhase] = tuple(MovementPhase)

    # 각 페이즈의 기간 정보 -> 한 전체 주기의 정보도 알 수 있음 (seconds)
    phase_duration: tuple[float] = tuple(MOVEMENT_CYCLE + random.random() for _ in range(len(phases)))


class MobilityHelper:
    def __init__(self, env):
        self.env = env

        self.left_hand_direction = 1
        self.left_hand_degree = -160
        self.right_hand_direction = -1
        self.right_hand_degree = 170

        self.left_leg_direction = -1
        self.left_leg_degree = 110
        self.right_leg_direction = 1
        self.right_leg_degree = -100

        self.movement_cycle = MOVEMENT_CYCLE     # seconds
        self.velocity = 0.5                      # m/s

        # static position
        self.head = Vector(1.1, 1.8, 1)                 # x, y, z
        self.left_upper_torso = Vector(1, 1.3, 1)
        self.left_lower_torso = Vector(1, 1, 1)         # base position
        self.right_upper_torso = Vector(1.2, 1.3, 1)
        self.right_lower_torso = Vector(1.2, 1, 1)
        self.left_shoulder = Vector(1, 1.6, 1)
        self.right_shoulder = Vector(1.2, 1.6, 1)

        # mobile position
        self.left_elbow = Vector(0, 0, 0)
        self.left_wrist = Vector(0, 0, 0)
        self.right_elbow = Vector(0, 0, 0)
        self.right_wrist = Vector(0, 0, 0)
        self.left_knee = Vector(0, 0, 0)
        self.left_ankle = Vector(0, 0, 0)
        self.right_knee = Vector(0, 0, 0)
        self.right_ankle = Vector(0, 0, 0)

        self.mobility_list = list()

        # 모빌리티의 페이즈 정보
        self.phase_info = MovementInfo()

        # 현재 모빌리티 정보
        self.current_phase = MovementPhase.PHASE_0


    def add_mobility_list(self, mobility: MobilityModel):
        self.mobility_list.append(mobility)
        self.update_position()

    def do_walking(self, event):
        self.move_left_hand()
        self.move_right_hand()
        self.move_left_leg()
        self.move_right_leg()

        self.update_position()

        # 현재 페이즈 정보 업데이트
        self.current_phase = MovementPhase.PHASE_1 if self.current_phase == MovementPhase.PHASE_0 else MovementPhase.PHASE_0

        event = self.env.event()
        event._ok = True
        event.callbacks.append(self.do_walking)
        self.env.schedule(event, priority=0, delay=self.movement_cycle)

    def move_left_hand(self):
        if self.left_hand_direction == 1:
            if self.left_hand_degree + self.velocity > 180:
                self.left_hand_degree = -180
            elif self.left_hand_degree < 0 and self.left_hand_degree + self.velocity > -90:
                self.left_hand_direction = -1
            else:
                self.left_hand_degree += self.velocity
        elif self.left_hand_direction == -1:
            if self.left_hand_degree - self.velocity < -180:
                self.left_hand_degree = 180
            elif self.left_hand_degree > 0 and self.left_hand_degree + self.velocity < 90:
                self.left_hand_direction = 1
            else:
                self.left_hand_degree -= self.velocity

        # left elbow movement
        a = math.radians(self.left_hand_degree)

        direction_x = random.randint(0, 1)
        if direction_x == 0:
            direction_x = -1    # left direction
        elif direction_x == 1:
            direction_x = 1     # right direction

        new_position = Vector(0, 0, 0)
        new_position.x = random.uniform(0, RANGE) * direction_x
        new_position.y = math.cos(-a) * 0.25    # 0.25 m => distance from left shoulder to left elbow
        new_position.z = math.sin(-a) * 0.25

        self.left_elbow.x = self.left_shoulder.x + new_position.x
        self.left_elbow.y = self.left_shoulder.y + new_position.y
        self.left_elbow.z = self.left_shoulder.z + new_position.z

        # left wrist movement
        self.left_wrist.x = self.left_elbow.x + new_position.x
        self.left_wrist.y = self.left_elbow.y + new_position.y
        self.left_wrist.z = self.left_elbow.z + new_position.z

    def move_right_hand(self):
        if self.right_hand_direction == 1:
            if self.right_hand_degree + self.velocity > 180:
                self.right_hand_degree = -180
            elif self.right_hand_degree < 0 and self.right_hand_degree + self.velocity > -90:
                self.right_hand_direction = -1
            else:
                self.right_hand_degree += self.velocity
        elif self.right_hand_direction == -1:
            if self.right_hand_degree - self.velocity < -180:
                self.right_hand_degree = 180
            elif self.right_hand_degree > 0 and self.right_hand_degree + self.velocity < 90:
                self.right_hand_direction = 1
            else:
                self.right_hand_degree -= self.velocity

        # right elbow movement
        a = math.radians(self.right_hand_degree)

        direction_x = random.randint(0, 1)
        if direction_x == 0:
            direction_x = -1    # left direction
        elif direction_x == 1:
            direction_x = 1     # right direction

        new_position = Vector(0, 0, 0)
        new_position.x = random.uniform(0, RANGE) * direction_x
        new_position.y = math.cos(-a) * 0.25    # 0.25 m => distance from right shoulder to right elbow
        new_position.z = math.sin(-a) * 0.25

        self.right_elbow.x = self.right_shoulder.x + new_position.x
        self.right_elbow.y = self.right_shoulder.y + new_position.y
        self.right_elbow.z = self.right_shoulder.z + new_position.z

        # right wrist movement
        self.right_wrist.x = self.right_elbow.x + new_position.x
        self.right_wrist.y = self.right_elbow.y + new_position.y
        self.right_wrist.z = self.right_elbow.z + new_position.z

    def move_left_leg(self):
        if self.left_leg_direction == 1:
            if self.left_leg_degree + self.velocity > 180:
                self.left_leg_degree = -180
            elif self.left_leg_degree < 0 and self.left_leg_degree + self.velocity > -50:
                self.left_leg_direction = -1
            else:
                self.left_leg_degree += self.velocity
        elif self.left_leg_direction == -1:
            if self.left_leg_degree - self.velocity < -180:
                self.left_leg_degree = 180
            elif self.left_leg_degree > 0 and self.left_leg_degree + self.velocity < 50:
                self.left_leg_direction = 1
            else:
                self.left_leg_degree -= self.velocity

        # left knee movement
        a = math.radians(self.left_leg_degree)

        new_position = Vector(0, 0, 0)
        new_position.x = 0
        new_position.y = math.cos(-a) * 0.25    # 0.25 m => distance from left knee to left ankle
        new_position.z = math.sin(-a) * 0.25

        self.left_knee.x = self.left_lower_torso.x + new_position.x
        self.left_knee.y = self.left_lower_torso.y + new_position.y
        self.left_knee.z = self.left_lower_torso.z + new_position.z

        # left ankle movement
        self.left_ankle.x = self.left_knee.x + new_position.x
        self.left_ankle.y = self.left_knee.y + new_position.y
        self.left_ankle.z = self.left_knee.z + new_position.z

    def move_right_leg(self):
        if self.right_leg_direction == 1:
            if self.right_leg_degree + self.velocity > 180:
                self.right_leg_degree = -180
            elif self.right_leg_degree < 0 and self.left_leg_degree + self.velocity > -50:
                self.right_leg_direction = -1
            else:
                self.right_leg_degree += self.velocity
        elif self.right_leg_direction == -1:
            if self.right_leg_degree - self.velocity < -180:
                self.right_leg_degree = 180
            elif self.right_leg_degree > 0 and self.left_leg_degree + self.velocity < 50:
                self.right_leg_direction = 1
            else:
                self.right_leg_degree -= self.velocity

        # right knee movement
        a = math.radians(self.right_leg_degree)

        new_position = Vector(0, 0, 0)
        new_position.x = 0
        new_position.y = math.cos(-a) * 0.25    # 0.25 m => distance from right lower torso to left knee
        new_position.z = math.sin(-a) * 0.25

        self.right_knee.x = self.right_lower_torso.x + new_position.x
        self.right_knee.y = self.right_lower_torso.y + new_position.y
        self.right_knee.z = self.right_lower_torso.z + new_position.z

        # right ankle movement
        self.right_ankle.x = self.right_knee.x + new_position.x
        self.right_ankle.y = self.right_knee.y + new_position.y
        self.right_ankle.z = self.right_knee.z + new_position.z

    def do_stand(self, event):
        self.update_position()

    def do_sitting(self, event):
        self.update_position()

    def update_position(self):
        for mob_list in self.mobility_list:
            if mob_list.get_body_position() == BodyPosition.HEAD:
                mob_list.set_position(self.head)
            elif mob_list.get_body_position() == BodyPosition.LEFT_UPPER_TORSO:
                mob_list.set_position(self.left_upper_torso)
            elif mob_list.get_body_position() == BodyPosition.LEFT_LOWER_TORSO:
                mob_list.set_position(self.left_lower_torso)
            elif mob_list.get_body_position() == BodyPosition.RIGHT_UPPER_TORSO:
                mob_list.set_position(self.right_upper_torso)
            elif mob_list.get_body_position() == BodyPosition.RIGHT_LOWER_TORSO:
                mob_list.set_position(self.right_lower_torso)
            elif mob_list.get_body_position() == BodyPosition.LEFT_SHOULDER:
                mob_list.set_position(self.left_shoulder)
            elif mob_list.get_body_position() == BodyPosition.RIGHT_SHOULDER:
                mob_list.set_position(self.right_shoulder)
            elif mob_list.get_body_position() == BodyPosition.LEFT_ELBOW:
                mob_list.set_position(self.left_elbow)
            elif mob_list.get_body_position() == BodyPosition.LEFT_WRIST:
                mob_list.set_position(self.left_wrist)
            elif mob_list.get_body_position() == BodyPosition.RIGHT_ELBOW:
                mob_list.set_position(self.right_elbow)
            elif mob_list.get_body_position() == BodyPosition.RIGHT_WRIST:
                mob_list.set_position(self.right_wrist)
            elif mob_list.get_body_position() == BodyPosition.LEFT_KNEE:
                mob_list.set_position(self.left_knee)
            elif mob_list.get_body_position() == BodyPosition.LEFT_ANKLE:
                mob_list.set_position(self.left_ankle)
            elif mob_list.get_body_position() == BodyPosition.RIGHT_KNEE:
                mob_list.set_position(self.right_knee)
            elif mob_list.get_body_position() == BodyPosition.RIGHT_ANKLE:
                mob_list.set_position(self.right_ankle)
