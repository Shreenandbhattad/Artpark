# tabular-analytics

LLM-backed natural-language analytics over tabular data. Point it at a domain folder under `../data/` and ask questions.

Run:

```
pip install -r requirements.txt
uvicorn main:app --reload
```

API:

- `GET /health`
- `GET /version`
- `POST /query` with `{"question": "..."}`
