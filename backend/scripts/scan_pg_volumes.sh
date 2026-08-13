#!/bin/bash
set -e
volumes=(
  01ceb262b0c5fa83750186b1618d6e41a9bad6dfa2210db83aa3edf2faef5b2f
  7a0a3177a590ffdc05d524c1b02effe5fc9f2f8526207917793923688407db87
  400fd69901c7c16d9258a81c8895633dcdc13a35d8b3e510d7e32fda275863a4
  b6de4be0909f3277b1bfc7e9330fdeacac1bdc86f96f0329d69e6b40230abcde
  b96f081fed02e1dfff2df29fd2f80f680e9804208ed3288c7077a7fd691969c0
  backend_rankify_pg_data
  rankify-image-automation_rankify_pg_data
)
for vol in "${volumes[@]}"; do
  if docker run --rm -v "$vol:/data" alpine test -f /data/PG_VERSION 2>/dev/null; then
    echo "=== PG VOLUME: $vol ==="
    docker rm -f pgscan >/dev/null 2>&1 || true
    docker run -d --name pgscan -p 0:5432 -v "$vol:/var/lib/postgresql/data" postgres:16-alpine >/dev/null
    sleep 3
    count=$(docker exec pgscan psql -U rankify -d rankify -tAc 'SELECT COUNT(*) FROM generated_images;' 2>/dev/null || echo "n/a")
    brands=$(docker exec pgscan psql -U rankify -d rankify -tAc 'SELECT COUNT(*) FROM brands;' 2>/dev/null || echo "n/a")
    echo "images=$count brands=$brands"
    docker rm -f pgscan >/dev/null
  fi
done
