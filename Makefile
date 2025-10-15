.PHONY: install run test clean docker-build docker-up docker-down demo

install:
	pip install -r requirements.txt

run:
	python main.py

test:
	python -m pytest tests/ -v

clean:
	rm -rf __pycache__ aegis/__pycache__ logs/
	find . -type d -name __pycache__ -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

demo: docker-up
	sleep 3
	./scripts/demo.sh

hotreload-demo:
	./scripts/test-hotreload.sh

logs:
	tail -f logs/aegis.log
