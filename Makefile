.PHONY: test refs ingest

test:
	pytest -q

refs:
	pangan refs

ingest:
	pangan ingest --start 2020-01-01 --end $(shell date +%Y-%m-%d)
