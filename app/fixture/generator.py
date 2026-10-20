import uuid


# toma una list[club_ids] y retorna list[fechas],
# donde fechas=list[partidos] y partidos=[local,visitante]
# el mapeo a las entidades de la BD lo manejamos en los repositorios (single responsability principle)
def generate_fixture(
    club_ids: list[uuid.UUID],
) -> list[list[tuple[uuid.UUID, uuid.UUID]]]:
    """
    Genera un fixture Round-Robin (todos contra todos).

    Args:
        club_ids: Lista de UUIDs de los clubes inscriptos.

    Returns:
        Una lista de fechas (jornadas).
        Cada fecha es una lista de partidos, representados como una tupla (local, visitante).
        Si un equipo queda libre en una fecha, simplemente no aparece en la lista de partidos de esa fecha.
    """
    # esta excepcion se podria manejar en la implementacion del endpoint
    if len(club_ids) < 3:
        raise ValueError("Se necesitan al menos 3 equipos para generar un fixture.")

    # si es impar agregamos un equipo "LIBRE" para que alguien quede libre
    teams = list(club_ids)
    if len(teams) % 2 != 0:
        teams.append("LIBRE")

    n = len(teams)
    total_matchdays = n - 1
    half = n // 2  # cantidad de partidos por fecha (division entera)

    fixture = []

    for matchday in range(total_matchdays):
        matchs = []  # partidos de la fecha actual

        for i in range(half):
            local = teams[i]
            away = teams[n - 1 - i]

            # solo agregamos el partido si ninguno de los dos es el equipo "LIBRE"
            if local != "LIBRE" and away != "LIBRE":
                # se intercala la localia segun la fecha para que sea parejo
                if matchday % 2 == 0:
                    matchs.append((local, away))
                else:
                    matchs.append((away, local))

        fixture.append(matchs)  # agrega la fecha al fixture

        # rota los equipos para la siguiente fecha (dejando el indice 0 fijo)
        # saca el ultimo (pop) y lo inserta en la posicion 1
        teams.insert(1, teams.pop())

    return fixture
