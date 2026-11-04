"""AST inspection helpers shared by architecture and security tests."""

from __future__ import annotations

import ast
from pathlib import Path

# Calls that must only appear in the composition root or inside adapters.
FORBIDDEN_CONSTRUCTORS: frozenset[str] = frozenset(
    {
        'boto3.client',
        'boto3.resource',
        'httpx.Client',
        'httpx.AsyncClient',
        'litellm',
        'litellm.completion',
        'litellm.acompletion',
        'litellm.LiteLLM',
        'OpenAI',
        'Anthropic',
        'CohereClient',
        'AsyncCohereClient',
    }
)

# Method names that imply data access and therefore require company_id.
DATA_METHOD_KEYWORDS: tuple[str, ...] = (
    'get',
    'find',
    'search',
    'query',
    'fetch',
    'load',
    'list',
    'retrieve',
    'read',
    'save',
    'write',
    'create',
    'update',
    'delete',
    'upsert',
    'insert',
    'execute',
)

# Identifiers that must never be passed directly to a logger.
SENSITIVE_LOG_IDENTIFIERS: frozenset[str] = frozenset(
    {
        'answer',
        'answer_text',
        'api_key',
        'chunk_text',
        'document_text',
        'password',
        'pii',
        'prompt',
        'question',
        'question_text',
        'raw_text',
        'secret',
        'token',
    }
)

LOG_METHODS: frozenset[str] = frozenset(
    {'critical', 'debug', 'error', 'exception', 'info', 'log', 'warn', 'warning'}
)


def get_python_files(package_path: Path | str) -> list[Path]:
    """Return every Python file below a package path in stable order."""
    path = Path(package_path)
    if not path.exists():
        return []
    return sorted(path.rglob('*.py'))


def parse_python_file(filepath: Path) -> ast.Module:
    """Parse a Python file into an AST."""
    return ast.parse(filepath.read_text(), filename=str(filepath))


def get_all_imports(tree: ast.Module) -> set[str]:
    """Extract the root package of every import in an AST."""
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0])
    return imports


def get_call_name(func: ast.expr) -> str | None:
    """Return a fully dotted call name, or None when it cannot be resolved."""
    if isinstance(func, ast.Name):
        return func.id
    if isinstance(func, ast.Attribute):
        prefix = get_call_name(func.value)
        return f'{prefix}.{func.attr}' if prefix else func.attr
    return None


def get_all_calls(tree: ast.Module) -> list[tuple[str, int]]:
    """Extract every resolvable function call with its dotted name and line."""
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            name = get_call_name(node.func)
            if name is not None:
                calls.append((name, node.lineno))
    return calls


def is_property_decorator(decorator: ast.expr) -> bool:
    """Return True for @property-style decorators."""
    if isinstance(decorator, ast.Name):
        return decorator.id == 'property'
    if isinstance(decorator, ast.Attribute):
        return decorator.attr == 'property'
    if isinstance(decorator, ast.Call):
        return is_property_decorator(decorator.func)
    return False


def find_class_defs(tree: ast.Module) -> list[tuple[str, int, int]]:
    """Find all class definitions with start/end lines."""
    classes = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            end_line = node.end_lineno or node.lineno
            classes.append((node.name, node.lineno, end_line))
    return classes


def find_function_defs(tree: ast.Module) -> list[tuple[str, int, int]]:
    """Find all function definitions with start/end lines."""
    functions = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end_line = node.end_lineno or node.lineno
            functions.append((node.name, node.lineno, end_line))
    return functions


def find_methods_without_company_id(package_path: Path) -> list[tuple[str, str, int]]:
    """Find public data methods that do not accept company_id."""
    violations = []
    for filepath in get_python_files(package_path):
        tree = parse_python_file(filepath)
        parent_map: dict[ast.AST, ast.AST] = {}
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                parent_map[child] = parent

        def enclosing_class_name(
            node: ast.AST, parent_lookup: dict[ast.AST, ast.AST]
        ) -> str | None:
            current = parent_lookup.get(node)
            while current is not None:
                if isinstance(current, ast.ClassDef):
                    return current.name
                current = parent_lookup.get(current)
            return None

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith('_'):
                continue
            if any(is_property_decorator(decorator) for decorator in node.decorator_list):
                continue

            class_name = enclosing_class_name(node, parent_map)
            # Private or value-object helper classes (e.g. stream chunks) are not
            # tenant data accessors; their dict-style helpers are false positives.
            if class_name is not None and (
                class_name.startswith('_') or class_name.endswith(('Chunk', 'Result'))
            ):
                continue

            method_name = node.name.lower()
            if not any(keyword in method_name for keyword in DATA_METHOD_KEYWORDS):
                continue

            args = node.args
            param_names = [arg.arg for arg in args.posonlyargs]
            param_names += [arg.arg for arg in args.args]
            param_names += [arg.arg for arg in args.kwonlyargs]
            if args.vararg:
                param_names.append(args.vararg.arg)
            if args.kwarg:
                param_names.append(args.kwarg.arg)

            if 'company_id' not in param_names:
                violations.append((str(filepath), node.name, node.lineno))
    return violations


def find_forbidden_constructor_calls(package_path: Path) -> list[tuple[str, str, int]]:
    """Find direct constructions of forbidden external clients."""
    violations = []
    for filepath in get_python_files(package_path):
        tree = parse_python_file(filepath)
        for name, lineno in get_all_calls(tree):
            if name in FORBIDDEN_CONSTRUCTORS:
                violations.append((str(filepath), name, lineno))
    return violations


def find_folders_missing_readme(root: Path) -> list[str]:
    """Find package folders, including root, that have no README.md."""
    missing = []
    directories = [root, *sorted(path for path in root.rglob('*') if path.is_dir())]
    for directory in directories:
        if directory.name == '__pycache__' or directory.name.startswith('.'):
            continue
        if (directory / 'README.md').exists():
            continue
        has_py = any(directory.glob('*.py'))
        has_subdirs = any(
            child.is_dir() and not child.name.startswith('.') for child in directory.iterdir()
        )
        if has_py or has_subdirs:
            relative = directory.relative_to(root)
            missing.append('.' if str(relative) == '.' else str(relative))
    return missing


def find_sensitive_log_calls(package_path: Path) -> list[tuple[str, str, int]]:
    """Find logger calls that pass sensitive identifiers to the logger."""
    violations = []
    for filepath in get_python_files(package_path):
        tree = parse_python_file(filepath)
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            call_name = get_call_name(node.func)
            if call_name is None:
                continue
            if call_name.rsplit('.', 1)[-1] not in LOG_METHODS:
                continue

            sensitive: set[str] = set()
            for argument in node.args:
                sensitive |= _sensitive_names_in(argument)
            for keyword in node.keywords:
                sensitive |= _sensitive_names_in(keyword.value)

            for name in sorted(sensitive):
                violations.append((str(filepath), name, node.lineno))
    return violations


def _sensitive_names_in(expr: ast.expr) -> set[str]:
    """Collect sensitive identifiers used directly in an expression."""
    if isinstance(expr, ast.Name):
        return {expr.id} & SENSITIVE_LOG_IDENTIFIERS
    if isinstance(expr, ast.Attribute):
        return {expr.attr} & SENSITIVE_LOG_IDENTIFIERS
    if isinstance(expr, ast.JoinedStr):
        names: set[str] = set()
        for value in expr.values:
            if isinstance(value, ast.FormattedValue):
                names |= _sensitive_names_in(value.value)
        return names
    if isinstance(expr, ast.Call):
        # Logging a length is safe; the value itself never reaches the log.
        if isinstance(expr.func, ast.Name) and expr.func.id == 'len':
            return set()
        names = set()
        for argument in expr.args:
            names |= _sensitive_names_in(argument)
        for keyword in expr.keywords:
            names |= _sensitive_names_in(keyword.value)
        return names
    return set()


def _assign_allowed(value: ast.expr | None, targets: list[ast.expr]) -> bool:
    if not targets or any(not isinstance(target, ast.Name) for target in targets):
        return False
    if any(isinstance(target, ast.Name) and target.id == '__all__' for target in targets):
        return True
    if value is None:
        return False
    if isinstance(value, (ast.Name, ast.Attribute)):
        return True
    if isinstance(value, (ast.List, ast.Tuple)):
        return all(isinstance(element, (ast.Name, ast.Attribute)) for element in value.elts)
    return False


def _is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == 'TYPE_CHECKING') or (
        isinstance(test, ast.Attribute) and test.attr == 'TYPE_CHECKING'
    )


def _statement_allowed(node: ast.stmt, *, type_checking: bool = False) -> bool:  # noqa: PLR0911
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        return True
    if (
        isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    ):
        return True
    if isinstance(node, ast.Assign):
        return _assign_allowed(node.value, node.targets)
    if isinstance(node, ast.AnnAssign):
        if not isinstance(node.target, ast.Name):
            return False
        if node.target.id == '__all__':
            return True
        return node.value is not None and isinstance(node.value, (ast.Name, ast.Attribute))
    if isinstance(node, ast.AugAssign):
        return isinstance(node.target, ast.Name) and node.target.id == '__all__'
    if isinstance(node, ast.If):
        if type_checking or not _is_type_checking(node.test):
            return False
        return (
            all(_statement_allowed(child, type_checking=True) for child in node.body)
            and not node.orelse
        )
    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return node.name == '__getattr__'
    return False


def is_passthrough_module(filepath: Path | str) -> bool:
    """Return True for behavior-free re-export modules (excluding __init__)."""
    path = Path(filepath)
    if path.name == '__init__.py':
        return False
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'))
    except (OSError, SyntaxError, UnicodeError):
        return False
    if any(isinstance(node, ast.ClassDef) for node in tree.body):
        return False
    functions = [
        node for node in tree.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    if len(functions) > 1 or (functions and functions[0].name != '__getattr__'):
        return False
    return all(_statement_allowed(node) for node in tree.body)


def find_passthrough_modules(root: Path | str) -> list[Path]:
    base = Path(root)
    if base.is_file():
        return [base] if is_passthrough_module(base) else []
    if not base.exists():
        return []
    return [
        path
        for path in sorted(base.rglob('*.py'))
        if path.name != '__init__.py' and is_passthrough_module(path)
    ]


def find_pass_through_modules(root: Path | str) -> list[Path]:
    return find_passthrough_modules(root)


def find_passthroughs(root: Path | str) -> list[Path]:
    return find_passthrough_modules(root)


def count_passthrough_modules(root: Path | str) -> int:
    return len(find_passthrough_modules(root))


def count_pass_through_modules(root: Path | str) -> int:
    return count_passthrough_modules(root)


def count_passthroughs(root: Path | str) -> int:
    return count_passthrough_modules(root)


is_passthrough = is_passthrough_module
is_pass_through = is_passthrough_module
is_pass_through_module = is_passthrough_module


def find_variadic_constructors(package_path: Path | str) -> list[tuple[str, str, int]]:
    """Find ``__init__`` methods with any variadic parameter (``*`` / ``**``)."""
    violations: list[tuple[str, str, int]] = []
    for filepath in get_python_files(package_path):
        tree = parse_python_file(filepath)
        for node in ast.walk(tree):
            if not isinstance(node, ast.ClassDef):
                continue
            for item in node.body:
                if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if item.name != '__init__':
                    continue
                if item.args.vararg is None and item.args.kwarg is None:
                    continue
                violations.append((str(filepath), node.name, item.lineno))
    return violations


# Alias names some callers may expect.
find_bare_kwargs_constructors = find_variadic_constructors
find_bare_variadic_constructors = find_variadic_constructors
find_variadic_init = find_variadic_constructors
