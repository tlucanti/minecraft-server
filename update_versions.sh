
rm -rf gist
git clone --depth=1 https://gist.github.com/77a982a7503669c3e1acb0a0cf6127e9.git gist

tail -n +3 gist/minecraft-server-jar-downloads.md | python3 parse.py > versions.json

rm -rf gist
