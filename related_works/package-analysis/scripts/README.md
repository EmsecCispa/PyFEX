Only add three bash scripts
Due to ossf using podman to manage sandbox containers, it may conflict using concurrent script.
So all scripts are run in serial mode.
scripts are designed for static / dynamic mode
If you want directly use gcr.io ,delete nopull option;
If you want to run your modified sandbox, add nopull
