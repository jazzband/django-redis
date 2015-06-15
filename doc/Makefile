all: doc

doc:
	mkdir -p dist/latest/
	asciidoctor -a docinfo -a stylesheet! -o dist/latest/index.html content.adoc

github: doc
	ghp-import -m "Generate documentation" -b gh-pages dist/
	git push origin gh-pages
