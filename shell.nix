{ pkgs ? import <nixpkgs> {} }:

let
  pythonEnv = pkgs.python311.withPackages (ps: with ps; [
    pip
    virtualenv
    python-dotenv
  ]);
in
pkgs.mkShell {
  name = "actual-email-scraper";

  buildInputs = [
    pythonEnv
    pkgs.docker
    pkgs.docker-compose
  ];

  shellHook = ''
    export PYTHONPATH="$PWD/src:$PYTHONPATH"

    if [ ! -d .venv ]; then
      echo "[shell.nix] Creating .venv ..."
      python -m venv .venv
    fi
    source .venv/bin/activate

    if [ -f requirements.txt ]; then
      pip install -q --upgrade pip
      pip install -q -r requirements.txt
    fi

    echo "actual-email-scraper dev shell ready (python $(python --version))."
  '';
}
