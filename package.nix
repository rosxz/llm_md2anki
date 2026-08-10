{
  lib,
  self,
  rich,
  google-genai,
  poetry-core,
  buildPythonApplication,
}:

buildPythonApplication rec {
  pname = "llm_md2anki";
  version = "unstable-${self.shortRev or "dirty"}";

  pyproject = true;

  src = self;
  setSourceRoot = ''
    sourceRoot="$(echo */src)"
  '';

  build-system = [
    poetry-core
  ];

  dependencies = [
    rich
    google-genai
  ];

  dontCheckRuntimeDeps = true;

  pythonImportsCheck = [
    "llm_md2anki"
  ];
}

