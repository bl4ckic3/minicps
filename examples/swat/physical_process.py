"""
SWaT physical process
"""

import sqlite3
from constants import VALVE_DIAMETER
from constants import TANK_DIAMETER
from constants import PROCESS_NUMBER
from constants import GRAVITATION
from constants import TIMER
from constants import TIMEOUT
from constants import P1_PLC1_TAGS
from constants import P1_PLC2_TAGS
from constants import P1_PLC3_TAGS
from constants import STATE_DB_PATH
from constants import TABLE
from constants import T_PP_R
from constants import read_single_statedb
from constants import update_statedb
from constants import select_value
from constants import logger
from time import sleep
from time import time
from math import sqrt as sqrt
from math import pow as power
from math import pi

###################################
#   REORGANIZING CONSTANTS FROM
#          CONSTANTS.PY
###################################

P1_INPUT_FLOW = []
P1_INPUT_VALVES = []
P1_OUTPUT_VALVES = []
def init():
    for i in range (0, PROCESS_NUMBER):
        P1_INPUT_FLOW.append('AI_FIT_%d01_FLOW' % (i + 1))
        P1_INPUT_VALVES.append('DO_MV_%d01_OPEN' % (i + 1))
        P1_OUTPUT_VALVES.append('DO_P_%d01_START' % (i + 1))


###################################
#         PHYSICAL PROCESS
###################################

def flow_to_height(flow, diameter):
    """
    flow: flow value (m^3/h)
    diameter: tank diameter (m^2)

    returns: height per hour corresponding (m/h)
    """
    return flow / diameter

def speed_to_height(speed, valve_diameter, tank_diameter):
    """
    speed: speed of water in a pipe (m/s)
    valve_diameter: (m)
    tank_diamaeter: (m)

    returns: height per second corresponding in the tank (m/s)
    """
    return speed * power(valve_diameter, 2) / power(tank_diameter, 2)

def Toricelli(flow_level, valve_height):
    """
    Toricelli formula, which returns the speed of the flow (m/s) according to
    the flow level in the tank and the valve height,
    considering the speed as a constant in the Bernoulli formula.
    """
    return sqrt(2 * GRAVITATION * (flow_level - valve_height))

def compute_new_flow_level(FIT_list, MV_list, LIT, P_list, tank_diameter, valve_diameter, timer):
    """
    FIT_list: list of input flow values (int, m^3/s)
    MV_list: list of boolean which tell if the valve is open or not
    LIT: current flow level (m)
    P_list: list of output valves which tells if they are open or not
    tank_diameter: (m)
    valves: (m)
    timer: period in which the flow level is computed (s)

    returns: new flow level (m)
    """
    height = LIT
    for i in (0, len(FIT_list) - 1):
        if MV_list[i] != 0:
            # FIT_list[i] is supposed to be in m^3/h and timer in seconds => conversion
            height += (timer/3600) * flow_to_height(FIT_list[i], tank_diameter)
    for i in (0, len(P_list) - 1):
        if P_list[i] != 0:
            # Toricelli formula gives the speed in m/s => no conversion
            height -= timer * speed_to_height(Toricelli(LIT, 0), valve_diameter, tank_diameter)
    return height

###################################
#               MAIN
###################################
if __name__ == '__main__':
    """
    main thread
    """
    sleep(3)

    init()

    start_time = time()
    while(time() - start_time < TIMEOUT):
        for i in range(1, PROCESS_NUMBER + 1):
            input_flows = []
            input_valves = []
            output_valves = []
            for index in P1_INPUT_FLOW:
                value = read_single_statedb(i, index)
                if value is not None:
                    input_flows.append(select_value(value))
            for index in P1_INPUT_VALVES:
                value = read_single_statedb(i, index)
                if value is not None:
                    input_valves.append(select_value(value))
            for index in P1_OUTPUT_VALVES:
                value = read_single_statedb(i, index)
                if value is not None:
                    output_valves.append(select_value(value))

            current_flow = read_single_statedb(i, 'AI_LIT_%d01_LEVEL' % i)
            if current_flow is not None:
                logger.debug('PP - read from state db %s' % current_flow[3])
                v = Toricelli(select_value(current_flow), 0)  # m/s
                flow = v * power(VALVE_DIAMETER/2.0, 2) * pi * 3600.0  # m^3/h
                update_statedb(flow, 2, 'AI_FIT_201_FLOW')
                new_flow = compute_new_flow_level(input_flows, input_valves,
                        select_value(current_flow), output_valves,
                        TANK_DIAMETER, VALVE_DIAMETER, T_PP_R)
                logger.debug('PP - write to state db %.4f' % new_flow)
                update_statedb(new_flow, i, 'AI_LIT_%d01_LEVEL' % i)

            sleep(T_PP_R)