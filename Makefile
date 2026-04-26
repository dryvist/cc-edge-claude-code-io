SHELL := /bin/bash

PACK_NAME := $(shell jq -r '.name // "unknown-pack"' package.json 2>/dev/null)
PACK_VERSION := $(shell jq -r '.version // "0.0.0"' package.json 2>/dev/null)
CRBL_FILE := $(PACK_NAME)-$(PACK_VERSION).crbl

.PHONY: help install build docker-up docker-down test typecheck lint format validate clean

help: ## Show this help
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install Node test dependencies (pnpm)
	cd tests && pnpm install

build: ## Build .crbl artifact (mirrors what release.yml does in CI)
	@INCLUDE="data default package.json README.md"; \
	[[ -f LICENSE ]] && INCLUDE="$$INCLUDE LICENSE"; \
	tar -czf "$(CRBL_FILE)" $$INCLUDE
	@echo "Built: $(CRBL_FILE)"
	@du -h "$(CRBL_FILE)"

docker-up: ## Start cribl/cribl Docker container (Stream supports both Edge and Stream packs)
	docker compose up -d
	@echo "Waiting for Cribl to be ready..."
	@for i in $$(seq 1 30); do \
		if curl -fsS http://localhost:9000/api/v1/health >/dev/null 2>&1; then \
			echo "Cribl is ready"; exit 0; \
		fi; \
		sleep 2; \
	done; \
	echo "ERROR: Cribl did not become ready in 60s"; \
	docker compose logs cribl; \
	exit 1

docker-down: ## Stop and remove the Docker container
	docker compose down -v

test: ## Run Vitest test suite (requires Docker; run 'make docker-up' first)
	cd tests && pnpm run test

typecheck: ## Type-check TypeScript
	cd tests && pnpm run typecheck

lint: ## Lint with Biome (lint + format check)
	cd tests && pnpm run lint

format: ## Auto-format with Biome
	cd tests && pnpm run format

validate: build ## Build pack and instruct on validator usage
	@echo ""
	@echo "Pack built: $(CRBL_FILE)"
	@echo ""
	@echo "To run vct-cribl-pack-validator (27+ structural checks), from the validator repo:"
	@echo "  cd ~/git/vct-cribl-pack-validator/main && claude /validate-pack $$PWD/$(CRBL_FILE)"

clean: ## Remove build artifacts, node_modules, and stop Docker
	rm -f *.crbl
	rm -rf tests/node_modules tests/dist
	-docker compose down -v 2>/dev/null
