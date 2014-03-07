#!/bin/sh
(cd doc; make)
cp -vr doc/index.html /tmp/index.html;
git checkout gh-pages;
rm -rf *
mv -fv /tmp/index.html .
git add --all index.html
git commit -a -m "Update doc"
