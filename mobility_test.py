import simpy
from simpy.events import NORMAL

from ban.base.helper.mobility_helper import MobilityHelper
from ban.base.mobility import MobilityModel, BodyPosition


env = simpy.Environment()

mob = MobilityModel(BodyPosition.LEFT_ELBOW)

mob_helper = MobilityHelper(env)
mob_helper.add_mobility_list(mob)

mob_helper.do_walking(env)

def print_info(ev):
    print(mob.get_position().x, ", ", end="")#, mob.get_position().y, mob.get_position().z)

    event = simpy.Event(env)
    event.env = env
    event._ok = True
    event.callbacks.append(print_info)

    env.schedule(event, priority=NORMAL, delay=0.1)


print_info(env)
env.run(until=100)

for model in mob_helper.mobility_list:
    x = model.get_position().x
    y = model.get_position().y
    z = model.get_position().z
