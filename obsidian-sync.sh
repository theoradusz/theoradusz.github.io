#!/bin/bash 

# copy new/updated files from obsidian to hugo 
rsync -av "/Users/wota/obsidian/notes/5 blog/blog/" "/Users/wota/Documents/Perso/website/radusz/notes/content/blog/" 
echo "blog files synced!"

