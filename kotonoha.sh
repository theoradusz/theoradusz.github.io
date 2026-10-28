#!/bin/zsh
# Enrich the words in fragments/kotonoha, publish them to content/words, write 今日の言葉, check the build.
# ./kotonoha.sh            local only
# ./kotonoha.sh --deploy   then commit and push with deploy.sh
set -e
cd "$(dirname "$0")"
python3 kotonoha/kotonoha.py all
out=$(mktemp -d)
hugo --quiet -d "$out" && rm -rf "$out" && echo "build ok"
if [[ "$1" == "--deploy" ]]; then
  ./deploy.sh
fi
