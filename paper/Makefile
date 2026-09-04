.PHONY: all clean check
all: main.pdf
main.pdf: main.tex sections/*.tex references.bib
	latexmk -pdf -interaction=nonstopmode -halt-on-error main.tex >/dev/null
clean:
	latexmk -C
check:
	bash $(HOME)/.claude/skills/academic-paper-style/scripts/check_style.sh . main.tex
