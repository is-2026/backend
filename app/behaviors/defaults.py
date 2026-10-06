from textwrap import dedent
from typing import NamedTuple


class DefaultBehaviorData(NamedTuple):
    name: str
    code: str


# Comportamientos que recibe cada club nuevo. Solo usan las primitivas del
# contrato (comportamientosApi.md): siempre se ve la cancha atacando hacia +x,
# el arco rival está en x = 20 y el propio en x = -20.
DEFAULT_BEHAVIORS: tuple[DefaultBehaviorData, ...] = (
    DefaultBehaviorData(
        name="Atacante",
        code=dedent(
            """\
            # Va siempre a buscar la pelota y cuando la tiene remata al arco.

            def decide_action():
                x, y = my_pos()
                bx, by = ball_pos()

                if has_ball():
                    shoot_arco()
                else:
                    move(bx - x, by - y, 100)
            """
        ),
    ),
    DefaultBehaviorData(
        name="Defensor",
        code=dedent(
            """\
            # Sale a buscar la pelota solo cuando se acerca.

            def decide_action():
                x, y = my_pos()
                bx, by = ball_pos()

                if has_ball():
                    shoot_arco()  # la despeja hacia el arco rival
                elif bx < -8:
                    move(bx - x, by - y, 100)
                elif abs(x + 15) + abs(y) > 0.5:
                    move(-15 - x, -y, 100)  # vuelve a su lugar, frente al arco
            """
        ),
    ),
    DefaultBehaviorData(
        name="Mediocampista",
        code=dedent(
            """\
            # Si tiene la pelota se la pasa a un compañero que esté más adelante,
            # si no hay ninguno, remata.

            def decide_action():
                x, y = my_pos()
                bx, by = ball_pos()

                if has_ball():
                    for teammate_id, teammate_x, teammate_y in team_pos():
                        if teammate_x > x + 3:
                            pass_to(teammate_id)
                            return
                    shoot_arco()
                elif -8 <= bx <= 8:
                    move(bx - x, by - y, 100)
                elif abs(x) + abs(y) > 0.5:
                    move(-x, -y, 100)  # vuelve al centro de la cancha
            """
        ),
    ),
     DefaultBehaviorData(
        name="Extremo",
        code=dedent(
            """\
            # Juega pegado a una banda. Busca la pelota cuando pasa por su lado
            # y, si no, la acompaña corriendo por la banda.

            lane = None  # la banda se elige en el primer tick y se recuerda


            def decide_action():
                global lane
                x, y = my_pos()
                bx, by = ball_pos()
                if lane is None:
                    lane = 7 if y >= 0 else -7

                if has_ball():
                    if bx > 10:
                        shoot_arco()
                    else:
                        shoot(1, 0, 60)  # avanza por la banda
                elif abs(by - lane) < 5:
                    move(bx - x, by - y, 100)
                else:
                    move(bx - x, lane - y, 100)
            """
        ),
    ),
    DefaultBehaviorData(
        name="Marcador",
        code=dedent(
            """\
            # Marca al rival que está más cerca de la pelota: se le pone delante,
            # del lado del arco propio.

            def decide_action():
                x, y = my_pos()
                bx, by = ball_pos()

                if has_ball():
                    shoot_arco()
                    return

                closest = None
                for rival_id, rx, ry in enemy_pos():
                    d = abs(rx - bx) + abs(ry - by)
                    if closest is None or d < closest[0]:
                        closest = (d, rx, ry)
                _, rx, ry = closest
                move(rx - 1.5 - x, ry - y, 100)
            """
        ),
    ),
)
