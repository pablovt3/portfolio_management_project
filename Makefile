.PHONY: install data study dashboard quality

install:
	python -m pip install 'git+https://github.com/pablovt3/portfolio_management_module.git@main'
	python -m pip install -e '.[dev,dashboard,report]'

data:
	python scripts/build_data.py

study:
	python scripts/run_study.py

dashboard:
	streamlit run dashboard/app.py

quality:
	ruff check src tests scripts dashboard
	mypy src scripts dashboard
	pytest --cov=portfolio_management_project --cov-branch
