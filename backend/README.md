# SoundVector backend

See the project's [README](../README.md) for local setup, the required trained artifacts, optional API keys, provider behavior, troubleshooting, and tests.

Run the web app from the **project root**, not this directory:

```bash
python backend/app.py --web --port 8000
```

The same process serves the browser UI at `http://localhost:8000/#/home` and the FastAPI documentation at `http://localhost:8000/docs`. It reads the project-root `.env`. The root `requirements.txt` is the dependency list used by the documented setup.

Without `--web`, `backend/app.py` starts the interactive terminal interface. Use `python backend/app.py --help` to see the CLI options.
