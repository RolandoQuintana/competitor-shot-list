.PHONY: test test-unit test-integration

test:
	pytest

test-unit:
	pytest -m "not integration"

test-integration:
	VISION_BACKEND=mock TRANSCRIPT_BACKEND=stub pytest -m integration
