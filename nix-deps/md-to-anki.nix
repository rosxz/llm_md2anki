{
  lib,
  buildPythonApplication,
  setuptools,
  soupsieve,
  rich,
  pygments,
  markdown-it-py,
  markdown,
  beautifulsoup4,
  fetchFromGitHub,
}:

buildPythonApplication rec {
  pname = "md-to-anki";
  version = "unstable-${src.rev}";

  pyproject = true;
  build-system = [ setuptools ];

  src = fetchFromGitHub {
    owner = "blueputty01";
    repo = "md-to-anki";
    rev = "e5f9584dfe40c05d12e12c2b44e6b87011e3f9d2";
    hash = "sha256-vO3uybxCIWWs0m80CAHgT7h+2zOpNSTOSMSLoUZt5PM=";
  };

  postUnpack = ''
    rm $sourceRoot/src/__init__.py
    cat > $sourceRoot/src/deck_consts.py << 'EOF'
  """Runtime configuration loader for the Nix-packaged md-to-anki.

  The upstream project expects a user-edited deck_consts.py with absolute paths.
  For packaging, we look for a local deck_consts.py in the current working
  directory first, then fall back to harmless defaults.
  """

  from __future__ import annotations

  from importlib import util
  from pathlib import Path
  import os


  def _load_local_config():
    local_config = Path.cwd() / "deck_consts.py"
    package_file = Path(__file__).resolve()
    if not local_config.exists() or local_config.resolve() == package_file:
      return None

    spec = util.spec_from_file_location("md_to_anki_user_config", local_config)
    if spec is None or spec.loader is None:
      return None

    module = util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


  _local = _load_local_config()

  if _local is not None:
    ROOT = getattr(_local, "ROOT", os.getcwd())
    DECKS = getattr(_local, "DECKS", {})
    IGNORE_KEYWORDS = getattr(_local, "IGNORE_KEYWORDS", "discussion")
    OUTPUT_DIR = getattr(_local, "OUTPUT_DIR", "")
  else:
    ROOT = os.environ.get("MD_TO_ANKI_ROOT", os.getcwd())
    DECKS = {}
    IGNORE_KEYWORDS = "discussion"
    OUTPUT_DIR = ""
  EOF
    cat > $sourceRoot/setup.py << 'EOF'
  from setuptools import setup

  setup(
    name="md-to-anki",
    version="0.0.1",
    package_dir={"": "src"},
    packages=["md_mathjax", "utils"],
    py_modules=["main", "parser", "deck_consts"],
    entry_points={"console_scripts": ["md-to-anki=main:main"]},
    python_requires=">=3.8",
  )
  EOF
  '';

  dependencies = [
    beautifulsoup4
    markdown
    markdown-it-py
    pygments
    rich
    soupsieve
  ];

  pythonImportsCheck = [
    "utils"
    "md_mathjax"
  ];

  meta.mainProgram = "md-to-anki";
}
