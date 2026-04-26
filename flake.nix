{
  description = "Dev shell for dryvist Cribl pack template — delegates to nix-devenv's typescript shell.";

  inputs = {
    nixpkgs.url = "github:nixos/nixpkgs/nixpkgs-25.11-darwin";
    nix-devenv.url = "github:JacobPEvans/nix-devenv";
  };

  outputs =
    {
      nixpkgs,
      nix-devenv,
      ...
    }:
    let
      systems = [
        "aarch64-darwin"
        "x86_64-darwin"
        "x86_64-linux"
        "aarch64-linux"
      ];
      forAllSystems = nixpkgs.lib.genAttrs systems;
    in
    {
      devShells = forAllSystems (system: {
        default = nix-devenv.devShells.${system}.typescript;
      });
    };
}
