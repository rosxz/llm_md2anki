{
  description = "LLM MD2 to ANKI DECK";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
  };

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};
      python = pkgs.python3.withPackages (ps: [ps.poetry-core ps.rich ps.google-genai]);
      package = pkgs.python3Packages.callPackage ./package.nix { inherit self; };
    in
    {
      devShells.${system}.default = pkgs.mkShell {
        buildInputs = [
          python
          package
        ];

        shellHook = ''
          echo "NIX Dev Environment"
        '';
      };
    };
}
