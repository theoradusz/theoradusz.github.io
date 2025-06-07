#!/bin/zsh

git pull origin main
git add content
git commit -m "deploy"
git push origin main


