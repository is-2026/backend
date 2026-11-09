"""Constantes de la simulación."""

# Tiempo
TICKS_PER_SECOND = 10
DT = 1 / TICKS_PER_SECOND  # segundos que dura un tick
TICKS_PER_MINUTE = TICKS_PER_SECOND * 60

# Duracion de un amistoso
FRIENDLY_MINUTES = 5
FRIENDLY_TOTAL_TICKS = FRIENDLY_MINUTES * TICKS_PER_MINUTE

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

# Distancia de separación mínima entre jugadores (no es colisión, es más un forcefield)
SOCIAL_DISTANCING = 1.0

# Cantidad de pasadas a la hora de separar jugadores
SEPARATION_PASSES = 3


# Para la sandbox
# Cuánto tiempo le doy a cada decide_action().
# Cada hijo tiene 3 jugadores: 3 x 10 ms = 30 ms en el peor caso,
# y los dos equipos corren en paralelo, así que sobra lugar en el tick de 100 ms.
CALL_TIMEOUT = 0.01  # (segundos)

# Cuanto puede tardar en cargarse el código (segundos)
CODE_LOAD_TIMEOUT = 0.1

# Memoria del proceso hijo entero
MEMORY_LIMIT_MB = 256

# Cuantos timeouts seguidos aguanta un jugador antes de quedar afuera por el resto del
# partido
MAX_CONSECUTIVE_TIMEOUTS = 3

# Del padre de sandbox
TICK_DEADLINE = 0.08  # cuánto espera el padre en cada tick.
STARTUP_DEADLINE = 2.0  # el primer decide incluye el arranque del hijo
CLOSE_TIMEOUT = 0.1  # cuanto espera para el join
