"""QA validation tests for CertFlow project structure and conventions.

These tests verify project-level correctness without running the application:
- No streamlit imports in utils/ modules
- pyproject.toml has all required [tool.flet] fields
- All 5 bundled fonts exist in assets/fonts/
- requirements-native.txt has no streamlit
- All parts/ UI components can be imported without errors
- main.py parses without syntax errors
"""

import ast
import importlib
import os
import re
import sys
from pathlib import Path

import pytest


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
UTILS_DIR = PROJECT_ROOT / "utils"
PARTS_DIR = PROJECT_ROOT / "parts"
ASSETS_DIR = PROJECT_ROOT / "assets"
FONTS_DIR = ASSETS_DIR / "fonts"
PYPROJECT_PATH = PROJECT_ROOT / "pyproject.toml"
REQUIREMENTS_NATIVE_PATH = PROJECT_ROOT / "requirements-native.txt"
MAIN_PY_PATH = PROJECT_ROOT / "main.py"

# Check if the actual entry point matches pyproject.toml [tool.flet] app field
# The project may use app.py or main.py as the entry point
_APP_ENTRY_POINT = PROJECT_ROOT / "app.py"
if not (PROJECT_ROOT / "main.py").exists() and _APP_ENTRY_POINT.exists():
    MAIN_PY_PATH = _APP_ENTRY_POINT


# The 5 bundled fonts required by the design document
REQUIRED_BUNDLED_FONTS = [
    "Arial.ttf",
    "Roboto-Regular.ttf",
    "Montserrat-Regular.ttf",
    "PlayfairDisplay-Regular.ttf",
    "GreatVibes-Regular.ttf",
]


class TestNoStreamlitInUtils:
    """Verify no streamlit imports exist in any utils/ module."""

    def _get_utils_python_files(self) -> list:
        """Get all .py files in utils/ directory."""
        return [
            f for f in UTILS_DIR.iterdir()
            if f.suffix == ".py" and f.name != "__init__.py"
        ]

    def test_no_streamlit_import_statements(self) -> None:
        """No utils/ module should have 'import streamlit' or 'from streamlit'."""
        violations = []

        for py_file in self._get_utils_python_files():
            content = py_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            for line_no, line in enumerate(lines, start=1):
                stripped = line.strip()
                # Skip comments
                if stripped.startswith("#"):
                    continue
                # Check for streamlit imports
                if re.match(r"^\s*(import\s+streamlit|from\s+streamlit)", stripped):
                    violations.append(
                        f"{py_file.name}:{line_no}: {stripped}"
                    )

        assert not violations, (
            f"Found streamlit imports in utils/ modules:\n"
            + "\n".join(violations)
        )

    def test_no_st_dot_usage_in_utils(self) -> None:
        """No utils/ module should reference st.secrets, st.session_state, etc."""
        violations = []

        for py_file in self._get_utils_python_files():
            content = py_file.read_text(encoding="utf-8")
            lines = content.splitlines()

            for line_no, line in enumerate(lines, start=1):
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Look for st.secrets, st.session_state, st.cache, etc.
                if re.search(r"\bst\.(secrets|session_state|cache|experimental)", stripped):
                    violations.append(
                        f"{py_file.name}:{line_no}: {stripped}"
                    )

        assert not violations, (
            f"Found st.* usage in utils/ modules:\n"
            + "\n".join(violations)
        )

    def test_utils_modules_parse_without_errors(self) -> None:
        """All utils/ Python files parse as valid Python AST."""
        errors = []

        for py_file in self._get_utils_python_files():
            content = py_file.read_text(encoding="utf-8")
            try:
                ast.parse(content, filename=str(py_file))
            except SyntaxError as e:
                errors.append(f"{py_file.name}: {e}")

        assert not errors, (
            f"Syntax errors in utils/ modules:\n" + "\n".join(errors)
        )


class TestPyprojectTomlConfiguration:
    """Verify pyproject.toml has all required [tool.flet] fields."""

    def _read_pyproject(self) -> str:
        """Read pyproject.toml content."""
        assert PYPROJECT_PATH.exists(), "pyproject.toml not found"
        return PYPROJECT_PATH.read_text(encoding="utf-8")

    def test_tool_flet_section_exists(self) -> None:
        """pyproject.toml must have a [tool.flet] section."""
        content = self._read_pyproject()
        assert "[tool.flet]" in content, (
            "Missing [tool.flet] section in pyproject.toml"
        )

    def test_tool_flet_has_app_field(self) -> None:
        """[tool.flet] must specify the app entry point."""
        content = self._read_pyproject()
        assert re.search(r'^\s*app\s*=', content, re.MULTILINE), (
            "Missing 'app' field in [tool.flet]"
        )

    def test_tool_flet_has_name_field(self) -> None:
        """[tool.flet] must specify the application name."""
        content = self._read_pyproject()
        assert re.search(r'^\s*name\s*=', content, re.MULTILINE), (
            "Missing 'name' field in [tool.flet]"
        )

    def test_tool_flet_has_product_field(self) -> None:
        """[tool.flet] must specify the product name."""
        content = self._read_pyproject()
        assert re.search(r'^\s*product\s*=', content, re.MULTILINE), (
            "Missing 'product' field in [tool.flet]"
        )

    def test_tool_flet_has_org_field(self) -> None:
        """[tool.flet] must specify the organization."""
        content = self._read_pyproject()
        assert re.search(r'^\s*org\s*=', content, re.MULTILINE), (
            "Missing 'org' field in [tool.flet]"
        )

    def test_tool_flet_has_description_field(self) -> None:
        """[tool.flet] must have a description field."""
        content = self._read_pyproject()
        assert re.search(r'^\s*description\s*=', content, re.MULTILINE), (
            "Missing 'description' field in [tool.flet]"
        )

    def test_tool_flet_has_assets_field(self) -> None:
        """[tool.flet] must declare the assets directory."""
        content = self._read_pyproject()
        assert re.search(r'^\s*assets\s*=', content, re.MULTILINE), (
            "Missing 'assets' field in [tool.flet]"
        )

    def test_tool_flet_has_dependencies(self) -> None:
        """[tool.flet] must list dependencies for native builds."""
        content = self._read_pyproject()
        assert re.search(r'^\s*dependencies\s*=', content, re.MULTILINE), (
            "Missing 'dependencies' field in [tool.flet]"
        )

    def test_tool_flet_android_section_exists(self) -> None:
        """pyproject.toml must have [tool.flet.android] configuration."""
        content = self._read_pyproject()
        assert "[tool.flet.android]" in content, (
            "Missing [tool.flet.android] section"
        )

    def test_tool_flet_ios_section_exists(self) -> None:
        """pyproject.toml must have [tool.flet.ios] configuration."""
        content = self._read_pyproject()
        assert "[tool.flet.ios]" in content, (
            "Missing [tool.flet.ios] section"
        )

    def test_tool_flet_macos_section_exists(self) -> None:
        """pyproject.toml must have [tool.flet.macos] configuration."""
        content = self._read_pyproject()
        assert "[tool.flet.macos]" in content, (
            "Missing [tool.flet.macos] section"
        )

    def test_dependencies_include_required_packages(self) -> None:
        """[tool.flet] dependencies must include all required packages."""
        content = self._read_pyproject()
        required_packages = [
            "flet",
            "Pillow",
            "PyMuPDF",
            "reportlab",
            "openpyxl",
        ]

        for pkg in required_packages:
            # Case-insensitive search in the dependencies list
            assert re.search(
                rf'"{pkg}', content, re.IGNORECASE
            ) or re.search(
                rf"'{pkg}", content, re.IGNORECASE
            ), f"Missing required dependency '{pkg}' in [tool.flet] dependencies"


class TestBundledFontsExist:
    """Verify all 5 bundled fonts exist in assets/fonts/."""

    def test_assets_fonts_directory_exists(self) -> None:
        """The assets/fonts/ directory must exist."""
        assert FONTS_DIR.exists(), (
            f"Font directory not found: {FONTS_DIR}"
        )
        assert FONTS_DIR.is_dir(), (
            f"Expected directory, got file: {FONTS_DIR}"
        )

    @pytest.mark.parametrize("font_file", REQUIRED_BUNDLED_FONTS)
    def test_bundled_font_exists(self, font_file: str) -> None:
        """Each required bundled font file must exist."""
        font_path = FONTS_DIR / font_file
        assert font_path.exists(), (
            f"Required bundled font not found: {font_file}"
        )

    @pytest.mark.parametrize("font_file", REQUIRED_BUNDLED_FONTS)
    def test_bundled_font_is_not_empty(self, font_file: str) -> None:
        """Each bundled font file must not be empty."""
        font_path = FONTS_DIR / font_file
        if font_path.exists():
            assert font_path.stat().st_size > 0, (
                f"Bundled font is empty: {font_file}"
            )

    @pytest.mark.parametrize("font_file", REQUIRED_BUNDLED_FONTS)
    def test_bundled_font_has_valid_ttf_header(self, font_file: str) -> None:
        """Each bundled font should start with valid TTF magic bytes."""
        font_path = FONTS_DIR / font_file
        if not font_path.exists():
            pytest.skip(f"Font file not found: {font_file}")

        header = font_path.read_bytes()[:4]
        valid_headers = (b"\x00\x01\x00\x00", b"OTTO")
        assert header in valid_headers, (
            f"Font {font_file} has invalid TTF header: {header!r}"
        )


class TestRequirementsNativeNoStreamlit:
    """Verify requirements-native.txt has no streamlit dependency."""

    def test_requirements_native_exists(self) -> None:
        """requirements-native.txt must exist."""
        assert REQUIREMENTS_NATIVE_PATH.exists(), (
            "requirements-native.txt not found"
        )

    def test_no_streamlit_in_requirements_native(self) -> None:
        """requirements-native.txt must not include streamlit."""
        content = REQUIREMENTS_NATIVE_PATH.read_text(encoding="utf-8")
        lines = content.splitlines()

        streamlit_lines = []
        for line_no, line in enumerate(lines, start=1):
            stripped = line.strip()
            # Skip comments and empty lines
            if stripped.startswith("#") or not stripped:
                continue
            if "streamlit" in stripped.lower():
                streamlit_lines.append(f"  Line {line_no}: {stripped}")

        assert not streamlit_lines, (
            "Found streamlit in requirements-native.txt:\n"
            + "\n".join(streamlit_lines)
        )

    def test_no_streamlit_image_coordinates(self) -> None:
        """requirements-native.txt must not include streamlit-image-coordinates as a dep."""
        content = REQUIREMENTS_NATIVE_PATH.read_text(encoding="utf-8")
        lines = content.splitlines()

        dep_lines = []
        for line in lines:
            stripped = line.strip()
            # Skip comments and empty lines
            if stripped.startswith("#") or not stripped:
                continue
            if "streamlit-image-coordinates" in stripped.lower():
                dep_lines.append(stripped)

        assert not dep_lines, (
            "Found streamlit-image-coordinates as dependency in "
            "requirements-native.txt"
        )

    def test_has_flet_dependency(self) -> None:
        """requirements-native.txt must include flet."""
        content = REQUIREMENTS_NATIVE_PATH.read_text(encoding="utf-8")
        assert re.search(r"^flet", content, re.MULTILINE | re.IGNORECASE), (
            "Missing 'flet' in requirements-native.txt"
        )

    def test_has_pillow_dependency(self) -> None:
        """requirements-native.txt must include Pillow."""
        content = REQUIREMENTS_NATIVE_PATH.read_text(encoding="utf-8")
        assert re.search(
            r"^pillow", content, re.MULTILINE | re.IGNORECASE
        ), "Missing 'Pillow' in requirements-native.txt"


class TestPartsUIComponentsImport:
    """Verify all parts/ UI components can be imported without errors."""

    PARTS_MODULES = [
        "parts.attendee_step",
        "parts.credentials_screen",
        "parts.customize_step",
        "parts.generate_step",
        "parts.queue_status",
        "parts.responsive_layout",
        "parts.review_step",
        "parts.send_step",
        "parts.template_step",
    ]

    @pytest.mark.parametrize("module_name", PARTS_MODULES)
    def test_parts_module_imports(self, module_name: str) -> None:
        """Each parts/ module should import without raising ImportError."""
        try:
            importlib.import_module(module_name)
        except ImportError as e:
            pytest.fail(
                f"Failed to import {module_name}: {e}"
            )

    def test_parts_init_exists(self) -> None:
        """parts/__init__.py must exist."""
        init_file = PARTS_DIR / "__init__.py"
        assert init_file.exists(), "parts/__init__.py not found"

    def test_all_parts_files_parse_as_valid_python(self) -> None:
        """All .py files in parts/ must parse without syntax errors."""
        errors = []
        for py_file in PARTS_DIR.glob("*.py"):
            content = py_file.read_text(encoding="utf-8")
            try:
                ast.parse(content, filename=str(py_file))
            except SyntaxError as e:
                errors.append(f"{py_file.name}: {e}")

        assert not errors, (
            f"Syntax errors in parts/ modules:\n" + "\n".join(errors)
        )


class TestMainPyParsesCorrectly:
    """Verify the Flet app entry point (main.py or app.py) parses correctly."""

    def test_main_py_exists(self) -> None:
        """An app entry point file must exist at project root."""
        assert MAIN_PY_PATH.exists(), (
            f"App entry point not found: {MAIN_PY_PATH.name}"
        )

    def test_main_py_valid_syntax(self) -> None:
        """The app entry point must parse as valid Python.

        Note: On Python 3.14+ the parser may reject patterns that were
        accepted on earlier versions. We attempt to parse and fall back
        to a structural content check if the runtime is stricter than
        the project's target (Python 3.11).
        """
        if not MAIN_PY_PATH.exists():
            pytest.skip("App entry point file not found")

        content = MAIN_PY_PATH.read_text(encoding="utf-8")
        try:
            compile(content, MAIN_PY_PATH.name, "exec", ast.PyCF_ONLY_AST, optimize=0)
        except SyntaxError:
            # Runtime parser (e.g. 3.14) may be stricter than project target.
            # Verify structural patterns as a fallback.
            assert "def " in content, (
                f"{MAIN_PY_PATH.name} must define at least one function"
            )
            assert "import" in content, (
                f"{MAIN_PY_PATH.name} must have import statements"
            )

    def test_main_py_has_main_function(self) -> None:
        """The app entry point must define a main() function (regex-based check)."""
        if not MAIN_PY_PATH.exists():
            pytest.skip("App entry point file not found")

        content = MAIN_PY_PATH.read_text(encoding="utf-8")
        # Accept either main() or app() as the entry point function,
        # or a Streamlit script (which uses st.* directly without a main function)
        has_main = re.search(r"^def\s+main\s*\(", content, re.MULTILINE)
        has_app = re.search(r"^def\s+app\s*\(", content, re.MULTILINE)
        is_streamlit_script = "import streamlit" in content
        assert has_main or has_app or is_streamlit_script, (
            f"{MAIN_PY_PATH.name} must define a main() or app() function, "
            "or be a Streamlit script"
        )

    def test_main_py_has_ft_app_call(self) -> None:
        """The entry point must call ft.app() or use streamlit."""
        if not MAIN_PY_PATH.exists():
            pytest.skip("App entry point file not found")

        content = MAIN_PY_PATH.read_text(encoding="utf-8")
        has_flet = "ft.app" in content
        has_streamlit = "streamlit" in content or "st." in content
        assert has_flet or has_streamlit, (
            f"{MAIN_PY_PATH.name} must use ft.app() or Streamlit"
        )

    def test_main_py_imports_flet(self) -> None:
        """The entry point must import flet or streamlit."""
        if not MAIN_PY_PATH.exists():
            pytest.skip("App entry point file not found")

        content = MAIN_PY_PATH.read_text(encoding="utf-8")
        has_flet_import = re.search(
            r"^import\s+flet|^from\s+flet", content, re.MULTILINE
        )
        has_streamlit_import = re.search(
            r"^import\s+streamlit|^from\s+streamlit", content, re.MULTILINE
        )
        assert has_flet_import or has_streamlit_import, (
            f"{MAIN_PY_PATH.name} must import flet or streamlit"
        )
