# SAM "makefile" build — assembles the Lambda artifact without Docker.
# SAM runs this in an isolated copy of CodeUri (precompute/), so src/ + config/
# must already be present HERE. They're vendored in fresh before each build by
# `make vendor` (or the deploy one-liner) and are gitignored, so no drift.
# pandas/numpy come from the managed pandas layer; only PyYAML is pip-installed.
vendor:
	rm -rf src config && cp -r ../src ./src && cp -r ../config ./config

build-PrecomputeFunction:
	mkdir -p "$(ARTIFACTS_DIR)"
	cp lambda_function.py "$(ARTIFACTS_DIR)/"
	cp -r src "$(ARTIFACTS_DIR)/src"
	cp -r config "$(ARTIFACTS_DIR)/config"
	python3 -m pip install -r requirements.txt -t "$(ARTIFACTS_DIR)"
