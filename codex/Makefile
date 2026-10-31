.DEFAULT_GOAL := status

.PHONY: merge export status test

merge export status:
	uv run --no-project --script sync-config.py $@

test:
	uv run --no-project --script test_sync_config.py
