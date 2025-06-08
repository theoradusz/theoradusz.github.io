#!/bin/zsh

git pull origin main
git add content
git add static/images/
git commit -m "deploy"
git push origin main
