# RouteLab workspace

Use skills/ai-model-router/SKILL.md for routing tasks.
Use the project .venv Python.
All generation uses real DeepSeek API. Run only when the user's request authorizes sending the task and API costs; plan makes no generation call.
Never place API keys in command arguments, source, reports, audit or video.
SettingsStore reads the local protected key; never print its key() result.
Never execute model-generated code.
Run python -m pytest -q after changes to routing, settings or billing.
