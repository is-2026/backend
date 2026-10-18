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
                f"Línea {node.lineno}: no se permite usar {node.attr}"
            )
        self.generic_visit(node)


def _check_length(code: str) -> None:
    if len(code) > MAX_CODE_LENGTH:
        raise InvalidBehaviorCode(
            f"El código tiene más de {MAX_CODE_LENGTH} caracteres"
        )


def _syntax_error_message(e: SyntaxError) -> str:
    prefix = f"Línea {e.lineno}, columna {e.offset}: " if e.lineno is not None else ""
    text = f"sintaxis inválida -> {e.msg}"
    return prefix + text


def _check_syntax(code: str) -> ast.Module:
    try:
        parsed_tree = ast.parse(code)
    except SyntaxError as e:
        raise InvalidBehaviorCode(_syntax_error_message(e)) from e

    try:
        compile(parsed_tree, "<behavior>", "exec")
    except SyntaxError as e:
        raise InvalidBehaviorCode(_syntax_error_message(e)) from e

    return parsed_tree


def _check_contract_function(parsed: ast.Module, kind: str) -> None:
    match kind:
        case "player":
            expected_name = "decide_action"
        case "coach":
            expected_name = "decide_coach"
        case _:
            raise ValueError(f"No se reconoel ce {kind}")

    for node in parsed.body:
        if isinstance(node, ast.FunctionDef) and node.name == expected_name:
            if (
                node.args.args
                or node.args.posonlyargs
                or node.args.vararg
                or node.args.kwonlyargs
                or node.args.kwarg
            ):
                raise InvalidBehaviorCode(
                    f"Línea {node.lineno}: {expected_name}() no debe recibir parámetros"
                )
            return

    raise InvalidBehaviorCode(f"Falta la función principal {expected_name}()")
