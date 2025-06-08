#!/bin/bash

# copy only markdown files to content (only if they don't exist)
rsync -av --ignore-existing "/Users/wota/obsidian/notes/5 blog/blog/" "/Users/wota/Documents/Perso/website/radusz/notes/content/blog/" --include="*.md" --exclude="*"

# copy only images to static folder (only if they don't exist)
rsync -av --ignore-existing "/Users/wota/obsidian/notes/5 blog/blog/" "/Users/wota/Documents/Perso/website/radusz/notes/static/images/blog/" --include="*.png" --include="*.jpg" --include="*.jpeg" --include="*.gif" --include="*.webp" --exclude="*"

# only process markdown files that were actually copied (new files)
find "/Users/wota/Documents/Perso/website/radusz/notes/content/blog/" -name "*.md" -newer "/tmp/sync_marker" -exec sed -i '' 's|!\[\[\([^/][^]]*\)\]\]|![[\1]]|g; s|!\[\[\([^]]*\)\]\]|![](/images/blog/\1)|g' {} \; 2>/dev/null

# create marker file for next run
touch "/tmp/sync_marker"

echo "blog files synced!"