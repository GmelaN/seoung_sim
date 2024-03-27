from enum import Enum

from ban.base.positioning import Vector


class MobilityState(Enum):
    STANDING = 0
    WALKING = 1
    SITTING = 2


class BodyPosition(Enum):
    HEAD = 0
    LEFT_UPPER_TORSO = 1
    LEFT_LOWER_TORSO = 2
    RIGHT_UPPER_TORSO = 3
    RIGHT_LOWER_TORSO = 4
    LEFT_SHOULDER = 5
    RIGHT_SHOULDER = 6
    LEFT_ELBOW = 7
    LEFT_WRIST = 8
    RIGHT_ELBOW = 9
    RIGHT_WRIST = 10
    LEFT_KNEE = 11
    LEFT_ANKLE = 12
    RIGHT_KNEE = 13
    RIGHT_ANKLE = 14
    BODY = 15


class MobilityModel:
    def __init__(self, body_position: BodyPosition):
        self.position = Vector(0, 0, 0)
        self.mobility_state: MobilityState | None = None
        self.body_position: BodyPosition = body_position

    def set_position(self, position: Vector):
        self.position = position

    def get_position(self):
        return self.position

    def get_body_position(self):
        return self.body_position

    def get_distance_from(self, position):
        v = Vector(0, 0, 0)
        v.x = position.x - self.position.x
        v.y = position.y - self.position.y
        v.z = position.z - self.position.z

        return v.get_length()

    def is_los(self, position):
        if self.position.z < 1 <= position.z:
            return False
        elif self.position.z >= 1 > position.z:
            return False
        else:
            # the two nodes are on the line of sight
            return True
