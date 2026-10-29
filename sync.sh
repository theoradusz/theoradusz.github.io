#!/bin/zsh
# Publish the fragments vault to the site: words (kotonoha/), blog posts (blog/), collection (collection/).
# ./sync.sh            sync and check the build
# ./sync.sh --deploy   then commit and push with deploy.sh
set -e
cd "$(dirname "$0")"
python3 vault/words.py all
python3 vault/pages.py sync
out=$(mktemp -d)
hugo --quiet -d "$out" && rm -rf "$out" && echo "build ok"
if [[ "$1" == "--deploy" ]]; then
  ./deploy.sh
fi
