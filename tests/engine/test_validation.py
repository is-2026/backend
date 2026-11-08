from textwrap import dedent

import pytest

from app.behaviors.defaults import DEFAULT_BEHAVIORS
from app.engine.validation import (
    MAX_CODE_LENGTH,
    InvalidBehaviorCode,
    validate_behavior_code,
)

VALID = "def decide_action():\n    pass\n"


# --- comportamientos default son válidos ---
@pytest.mark.parametrize("behavior", DEFAULT_BEHAVIORS)
def test_default_behaviors_are_valid(behavior):
    validate_behavior_code(behavior.code, "player")


# --- código de no más de 10000 caracteres ---
def test_code_max_length_accepted():
    code = VALID + "#" * (MAX_CODE_LENGTH - len(VALID))

    validate_behavior_code(code, "player")


def test_code_over_max_length_is_rejected():
    code = VALID + "#" * (MAX_CODE_LENGTH - len(VALID) + 1)

    with pytest.raises(InvalidBehaviorCode):
        validate_behavior_code(code, "player")


# --- sintaxis ---
@pytest.mark.parametrize(
    "code",
    [
        "def decide_action():\n    x = 1\n    if x\n        pass\n",
        # ast.parse lo acepta, recién falla al compilar
        "def decide_action():\n    pass\nreturn 1\n",
        "def decide_action():\n    x = 1\n    break",
    ],
    ids=["parse", "compile", "compile2"],
)
def test_syntax_error_reports_its_line(code):
    with pytest.raises(InvalidBehaviorCode) as exc:
        validate_behavior_code(code, "player")

    assert "Línea 3" in str(exc.value)


def test_syntax_error_without_line():
    # el SyntaxError de un byte nulo no trae lineno
    with pytest.raises(InvalidBehaviorCode) as exc:
        validate_behavior_code(VALID + "\x00", "player")

    assert "Línea" not in str(exc.value)


# --- import prohibidos ---
def test_math_import_is_accepted():
    code = "import math\n" + VALID
    validate_behavior_code(code, "player")


@pytest.mark.parametrize(
    "prohibited_import",
    [
        "import os",
        "import math, sys",
        "from sys import path",
        "from . import math",
        "from ..math import sqrt",
        "from . import algo",
    ],
)
def test_prohibited_imports_are_rejected(prohibited_import):
    code = f"{prohibited_import}\n" + VALID
    with pytest.raises(InvalidBehaviorCode) as exc:
        validate_behavior_code(code, "player")

    assert "Línea 1" in str(exc.value)


# --- prohibición de nombres ---
@pytest.mark.parametrize(
    "line",
    [
        "open('x')",
        "eval('1')",
        "getattr(x, 'y')",
        "__import__('os')",
        "x = ().__class__",
        # el dunder no es el último atributo: hay que bajar a los hijos
        "x = y.__class__.real",
    ],
)
def test_forbidden_names_and_attributes_are_rejected(line):
    code = f"def decide_action():\n    {line}\n"
    with pytest.raises(InvalidBehaviorCode) as exc:
        validate_behavior_code(code, "player")

    assert "Línea 2" in str(exc.value)


# --- función del contrato ---
def test_missing_decide_action_is_rejected():
    with pytest.raises(InvalidBehaviorCode):
        validate_behavior_code("def other():\n    pass\n", "player")


def test_decide_action_inside_another_function_is_rejected():
    # la busca en el módulo, entonces no la encuentra
    code = "def helper():\n    def decide_action():\n        pass\n"

    with pytest.raises(InvalidBehaviorCode):
        validate_behavior_code(code, "player")


@pytest.mark.parametrize("params", ["a", "a, /", "*a", "*, a", "**a"])
def test_decide_action_with_params_is_rejected(params):
    code = f"def decide_action({params}):\n    pass\n"

    with pytest.raises(InvalidBehaviorCode):
        validate_behavior_code(code, "player")


def test_coach_needs_decide_coach():
    validate_behavior_code("def decide_coach():\n    pass\n", "coach")

    with pytest.raises(InvalidBehaviorCode):
        validate_behavior_code(VALID, "coach")


# --- except ---
def test_bare_except_is_rejected():
    code = dedent(
        """\
        def decide_action():
            try:
                x = 1
            except:
                pass
        """
    )
    with pytest.raises(InvalidBehaviorCode) as exc:
        validate_behavior_code(code, "player")

    assert "Línea 4" in str(exc.value)


def test_except_exception_is_accepted():
    code = dedent(
        """\
        def decide_action():
            try:
                x = 1
            except Exception:
                pass
        """
    )
    validate_behavior_code(code, "player")
