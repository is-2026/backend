from textwrap import dedent
from typing import NamedTuple


class DefaultBehaviorData(NamedTuple):
    name: str
    code: str

# TODO: reemplazar cuando se decida cuales van a ser los defaults
DEFAULT_BEHAVIORS: tuple[DefaultBehaviorData, ...] = (
    DefaultBehaviorData(
        name="Atacante",
        code=dedent(
            """\
            def decidir_accion():
                # placeholder
                pass
            """
        ),
    ),
    DefaultBehaviorData(
        name="Defensor",
        code=dedent(
            """\
            def decidir_accion():
                # placeholder
                pass
            """
        ),
    ),
    DefaultBehaviorData(
        name="Mediocampista",
        code=dedent(
            """\
            def decidir_accion():
                # placeholder
                pass
            """
        ),
    ),
)