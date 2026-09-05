import subprocess
import sys


def test_kernel_imports_and_has_version() -> None:
    import pravrudhi_kernel

    assert pravrudhi_kernel.__version__ == "0.1.0"


def test_kernel_runs_on_python_313() -> None:
    assert sys.version_info[:2] == (3, 13)


def test_kernel_import_pulls_in_neither_torch_nor_engine() -> None:
    code = "import sys, pravrudhi_kernel.schema; assert 'torch' not in sys.modules; assert 'pravrudhi' not in sys.modules"
    subprocess.run([sys.executable, "-c", code], check=True)
