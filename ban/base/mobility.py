from enum import Enum

# from ban.base.positioning import Vector

# import json

# positions[PHASE_n][BODY_POSITION_k][TIME_SLOT_p] = (x, y, z)

# data, i_data = None, None
# with open("./position_0.029.json", 'r', encoding="utf8") as f:
#     data = json.load(f)

# with open("./reversed_position_0.029.json", 'r', encoding="utf8") as f:
#     i_data = json.load(f)

# positions = [data, i_data]


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
        self.body_position: BodyPosition = body_position

    def get_body_position(self):
        return self.body_position
