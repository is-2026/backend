"""Constantes de la simulación."""

# Tiempo
TICKS_PER_SECOND = 10
DT = 1 / TICKS_PER_SECOND  # segundos que dura un tick
TICKS_PER_MINUTE = TICKS_PER_SECOND * 60

# Cancha
FIELD_HALF_LENGTH = 20.0  # x va de -20 a 20
FIELD_HALF_WIDTH = 10.0  # y va de -10 a 10
GOAL_HALF_WIDTH = 1.5  # el arco ocupa -1.5 <= y <= 1.5

# Rango de los atributos PACSS
ATTR_MIN = 20
ATTR_MAX = 100

# PACSS -> física: (valor con atributo 20, valor con atributo 100)
SPEED_MAX_RANGE = (4.0, 8.0)  # m/s
CONTROL_RADIUS_RANGE = (0.5, 1.5)  # m
KICK_SPEED_RANGE = (10.0, 25.0)  # m/s, pelota al 100% de power
COOLDOWN_TICKS_RANGE = (10, 3)  # ticks, más agility = menos cooldown

# Pelota
BALL_FRICTION = 0.95  # factor por tick
BALL_BOUNCE = 0.8  # energía que conserva al rebotar
BALL_STOP_SPEED = 0.1  # m/s, por debajo se considera quieta

# Posiciones iniciales del local (formación TRIANGLE) el visitante las espeja
TRIANGLE_HOME = ((-4.0, 0.0), (-12.0, -5.0), (-12.0, 5.0))

# Cada remate se desvía al azar hasta este ángulo para cada lado
SHOT_SPREAD_DEG = 25.0
