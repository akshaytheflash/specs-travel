PY ?= python3
.PHONY: all experiment nested intervention test paper clean
all: experiment nested intervention test paper
experiment: ; $(PY) -m src.experiment
nested:     ; $(PY) -m src.nested
intervention: ; $(PY) -m src.intervention
test:       ; $(PY) -m tests.test_miner
paper:
	cd paper && pdflatex -interaction=nonstopmode paper.tex >/dev/null && pdflatex -interaction=nonstopmode paper.tex >/dev/null && echo "paper/paper.pdf"
clean: ; rm -rf results/*.json results/nested results/intervention
