install:
	python -m pip install -r requirements.txt
auth:
	python scripts/notion_auth.py
run:
	uvicorn app.main:app --reload
test:
	pytest -q
