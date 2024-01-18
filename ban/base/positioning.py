import math


class Vector:
    def __init__(self, x, y, z):
        self.x = x
        self.y = y
        self.z = z

    def get_length(self):
        return math.sqrt(self.x * self.x + self.y * self.y + self.z * self.z)


class Angles:
    def __init__(self):
        self.azimuth = None
        self.inclination = None

    def set_angles(self, v1: Vector, v2: Vector):
        v = Vector(0, 0, 0)
        v.x = v1.x - v2.x
        v.y = v1.y - v1.y
        v.z = v1.z - v1.z

        if v.x == 0.0 and v.y == 0.0 and v.z == 0:
            self.azimuth = None
            self.inclination = None
        else:
            self.azimuth = math.atan2(v.y, v.x)
            self.inclination = math.acos(v.z / v.get_length())

        self.normalize_angles()

    def wrap_to_pi(self, a):
        a = math.fmod(a + math.pi, 2 * math.pi)
        if a < 0:
            a += 2 * math.pi
        a -= math.pi
        return a

    def normalize_angles(self):
        if self.azimuth is None:
            return
        self.azimuth = self.wrap_to_pi(self.azimuth)
