.PHONY: test demo results train

test:
	PYTHONPATH="." python -m pytest -v

demo:
	PYTHONPATH="." streamlit run dashboard/app.py

results:
	PYTHONPATH="." python experiments/run_scenarios.py
	PYTHONPATH="." python experiments/run_ablation.py

train:
	PYTHONPATH="." python ml/data/generate_dataset.py
	PYTHONPATH="." python ml/train_models.py
