#!/bin/sh
VERSION="latest"
(cd doc; make)

rm -rf /tmp/index.html
mv doc/index.html /tmp/index.html;
git checkout gh-pages;

rm -rf ./$VERSION
mkdir -p ./$VERSION/
mv -fv /tmp/index.html ./$VERSION/

git add --all ./$VERSION/index.html
git commit -a -m "Update ${VERSION} doc"
