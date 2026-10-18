import ast

MAX_CODE_LENGTH = 10000


class InvalidBehaviorCode(Exception):
    """Comportamiento con código inválido"""


# orden de las validaciones
# largo -> sintaxis -> construcciones prohibidas -> función del contrato

PROHIBITED_NAMES = [
    "eval",
    "exec",
    "compile",
    "open",
    "input",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "breakpoint",
    "exit",
    "quit",
    "help",
]


class BehaviorValidator(ast.NodeVisitor):
    def visit_Import(self, node):
        raise InvalidBehaviorCode(f"Línea {node.lineno}: está prohibido importar")

    def visit_ImportFrom(self, node):
        raise InvalidBehaviorCode(
            f"Línea {node.lineno}: está prohibido importar desde {node.module}"
        )

    def visit_Name(self, node):
        if node.id in PROHIBITED_NAMES or node.id.startswith("__"):
            raise InvalidBehaviorCode(
                f"Línea {node.lineno}: no se permite usar {node.id}"
            )

    def visit_Attribute(self, node):
        if node.attr.startswith("__"):
            raise InvalidBehaviorCode(
                f"Línea {node.lineno}: no se permite usar ({node.attr})"
            )
        self.generic_visit(node)


def _check_length(code: str) -> bool:
    if len(code) > MAX_CODE_LENGTH:
        raise InvalidBehaviorCode(
            f"El código tiene más de {MAX_CODE_LENGTH} caracteres"
        )

def _check_syntax(code: str) -> bool: ...

def validate_behavior_code(code: str, kind: str) -> None: ...
