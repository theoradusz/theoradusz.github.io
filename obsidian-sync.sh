#!/bin/bash

# copy only markdown files to content
rsync -av "/Users/wota/obsidian/notes/5 blog/blog/" "/Users/wota/Documents/Perso/website/radusz/notes/content/blog/" --include="*.md" --exclude="*"

# copy only images to static folder  
rsync -av "/Users/wota/obsidian/notes/5 blog/blog/" "/Users/wota/Documents/Perso/website/radusz/notes/static/images/blog/" --include="*.png" --include="*.jpg" --include="*.jpeg" --include="*.gif" --include="*.webp" --exclude="*"

find "/Users/wota/Documents/Perso/website/radusz/notes/content/blog/" -name "*.md" -exec sed -i '' 's|!\[\[\([^/][^]]*\)\]\]|![[\1]]|g; s|!\[\[\([^]]*\)\]\]|![](/images/blog/\1)|g' {} \;

echo "blog files synced!"