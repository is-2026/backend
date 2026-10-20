import uuid

import pytest

from app.fixture.generator import generate_fixture


def test_fixture_generator_fails_with_less_than_3_teams():
    club_ids = [uuid.uuid4(), uuid.uuid4()]

    with pytest.raises(ValueError) as exc_info:
        generate_fixture(club_ids)

    assert "Se necesitan al menos 3 equipos" in str(exc_info.value)


def test_fixture_generator_even_teams():
    # 4 equipos (Par)
    # N = 4. deberia haber:
    #   - N-1 fechas = 3 fechas.
    #   - en cada fecha N/2 partidos = 2 partidos.
    #   - total partidos = (4 * 3) / 2 = 6.
    #   - nadie queda libre.
    equipos = [uuid.uuid4() for _ in range(4)]

    # generamos el fixture
    fixture = generate_fixture(equipos)

    assert len(fixture) == 3  # 3 fechas

    partidos_totales = []
    for fecha in fixture:
        assert len(fecha) == 2  # 2 partidos por fecha (nadie libre)
        partidos_totales.extend(fecha)

    assert len(partidos_totales) == 6  # 6 partidos en total

    # verificar que ningun equipo juegue dos veces en la misma fecha
    for fecha in fixture:
        equipos_en_fecha = set()
        for local, visitante in fecha:
            equipos_en_fecha.add(local)
            equipos_en_fecha.add(visitante)
        assert len(equipos_en_fecha) == 4  # los 4 equipos jugaron esta fecha


def test_fixture_generator_odd_teams():
    # 3 equipos (Impar)
    # N = 3. deberia haber:
    #   - N fechas = 3 fechas.
    #   - en cada fecha 1 equipo queda libre (1 partido por fecha).
    #   - total partidos = (3 * 2) / 2 = 3.
    equipos = [uuid.uuid4() for _ in range(3)]

    # generamos el fixture
    fixture = generate_fixture(equipos)

    assert len(fixture) == 3  # 3 fechas

    partidos_totales = []
    equipos_que_jugaron = {eq: 0 for eq in equipos}

    for fecha in fixture:
        assert len(fecha) == 1  # 1 partido (2 juegan, 1 queda libre)
        partidos_totales.extend(fecha)

        # contamos cuantos partidos jugó cada uno en toda la liga
        for local, visitante in fecha:
            equipos_que_jugaron[local] += 1
            equipos_que_jugaron[visitante] += 1

    assert len(partidos_totales) == 3  # 3 partidos en total

    # verificar que todos los equipos jugaron exactamente 2 partidos (contra los otros dos)
    for partidos_jugados in equipos_que_jugaron.values():
        assert partidos_jugados == 2


def test_fixture_generator_no_repeated_matches():
    # 6 equipos
    equipos = [uuid.uuid4() for _ in range(6)]

    # generamos el fixture
    fixture = generate_fixture(equipos)

    # juntamos todos los cruces, normalizando el orden (A vs B es lo mismo que B vs A)
    # para asegurarnos de que ningun enfrentamiento se repita.
    todos_los_cruces = set()

    for fecha in fixture:
        for local, visitante in fecha:
            # ordenamos la tupla para que (A, B) y (B, A) resulten en la misma representacion
            cruce = tuple(sorted([local, visitante]))

            # si el cruce ya estaba en el set, significa que estan jugando dos veces
            assert cruce not in todos_los_cruces, f"El cruce {cruce} está repetido."
            todos_los_cruces.add(cruce)

    # Con N=6, (N*(N-1))/2 = 15. Deben haber 15 cruces unicos.
    assert len(todos_los_cruces) == 15


def test_fixture_generator_max_teams():
    # 20 equipos
    # N = 20. como es par, deberia haber:
    #   - N-1 fechas = 19 fechas.
    #   - en cada fecha N/2 partidos = 10 partidos.
    #   - total partidos = (20 * 19) / 2 = 190.
    #   - nadie queda libre.
    equipos = [uuid.uuid4() for _ in range(20)]

    # generamos el fixture
    fixture = generate_fixture(equipos)

    assert len(fixture) == 19  # 19 fechas exactas

    partidos_totales = []
    todos_los_cruces = set()
    equipos_que_jugaron = {eq: 0 for eq in equipos}

    for fecha in fixture:
        # cada fecha debe tener exactamente 10 partidos (nadie libre)
        assert len(fecha) == 10
        partidos_totales.extend(fecha)

        equipos_en_fecha = set()
        for local, visitante in fecha:
            # verificamos que ningun equipo juegue dos veces en la misma fecha
            assert local not in equipos_en_fecha
            assert visitante not in equipos_en_fecha
            equipos_en_fecha.add(local)
            equipos_en_fecha.add(visitante)

            # contamos cuantos partidos jugo cada uno en toda la liga
            equipos_que_jugaron[local] += 1
            equipos_que_jugaron[visitante] += 1

            # verificamos que no haya cruces repetidos en todo el torneo
            cruce = tuple(sorted([local, visitante]))
            assert cruce not in todos_los_cruces
            todos_los_cruces.add(cruce)

    # verificamos la cantidad partidos y cruces
    assert len(partidos_totales) == 190  # 190 partidos en total
    assert len(todos_los_cruces) == 190  # 190 cruces unicos

    # verificamos que todos los equipos jugaron exactamente 19 partidos (contra todos los demas)
    for partidos_jugados in equipos_que_jugaron.values():
        assert partidos_jugados == 19
