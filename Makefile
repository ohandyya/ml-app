help:
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "%-30s %s\n", $$1, $$2}'


PASSWORD ?= password

build_frontend: ## Build frontend image
	@cd frontend; docker build -t frontend -f Dockerfile .

run_frontend: ## Run frontend
	@docker run --rm -d -p 8501:8501 --env PASSWORD frontend

run_frontend_dev: ## Run frontend in DEV mode
	@docker run --rm -it -p 8501:8501  --env PASSWORD=${PASSWORD} --env AWS_SECRET_ACCESS_KEY --env AWS_ACCESS_KEY_ID frontend

build_lambda: ## Build Lambda function image
	@cd lambda; docker build -t ml_app_lambda -f Dockerfile .

run_lambda:  ## Run Lambda function using Lambda emulator
	# Seend request: curl -X POST --header 'Content-Type: application/json' "http://localhost:9000/2015-03-31/functions/function/invocations" -d '{"gender": "male"}'
	@docker run --rm -v ~/.aws-lambda-rie:/aws-lambda -p 9000:8080 --env AWS_SECRET_ACCESS_KEY --env AWS_ACCESS_KEY_ID --entrypoint /aws-lambda/aws-lambda-rie ml_app_lambda /usr/local/bin/python -m awslambdaric prediction.handler

build_backend: ## Build backend image
	@cd backend; docker build -t backend -f Dockerfile .

run_backend:  ## Run backend
	@docker run --rm -it --env AWS_SECRET_ACCESS_KEY --env AWS_ACCESS_KEY_ID backend

install_lambda_emulator:  ## Install Lambda emulator locally
	bash install_lambda_emulator.sh

upload_frontend: build_frontend  ## Upload frontned image to ECR
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 381982364978.dkr.ecr.us-east-1.amazonaws.com
	docker tag frontend:latest 381982364978.dkr.ecr.us-east-1.amazonaws.com/ml_app_frontend:latest
	docker push 381982364978.dkr.ecr.us-east-1.amazonaws.com/ml_app_frontend:latest
	docker logout 381982364978.dkr.ecr.us-east-1.amazonaws.com

upload_lambda: build_lambda  ## Uplaod lambda image to ECR
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 381982364978.dkr.ecr.us-east-1.amazonaws.com
	docker tag ml_app_lambda:latest 381982364978.dkr.ecr.us-east-1.amazonaws.com/ml_app_lambda:latest
	docker push 381982364978.dkr.ecr.us-east-1.amazonaws.com/ml_app_lambda:latest
	docker logout 381982364978.dkr.ecr.us-east-1.amazonaws.com

upload_backend: build_backend  ## Upload backend image to ECR
	aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin 381982364978.dkr.ecr.us-east-1.amazonaws.com
	docker tag backend:latest 381982364978.dkr.ecr.us-east-1.amazonaws.com/ml_app_backend:latest
	docker push 381982364978.dkr.ecr.us-east-1.amazonaws.com/ml_app_backend:latest
	docker logout 381982364978.dkr.ecr.us-east-1.amazonaws.com