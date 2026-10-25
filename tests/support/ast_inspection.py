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
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if node.name.startswith('_'):
                continue
            if any(is_property_decorator(decorator) for decorator in node.decorator_list):
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
